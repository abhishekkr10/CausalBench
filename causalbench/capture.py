"""Background bounded recording and failure-trigger snapshots. No physical output."""
from .provenance import loaded_source, register_source
_LOADED_SOURCE=register_source(__file__)
import copy
import json
import threading
import time
import urllib.request
from urllib.parse import urlparse
from .engine import integer, validate_trace, canonical
from .faults import validate_streams, stream_value


def read_http(url, origin, capture_sequence):
    start=(time.monotonic_ns()-origin)//1000000
    obs=None
    raw=None
    streams={}
    error=None
    raw_text=None
    try:
        with urllib.request.urlopen(url,timeout=2) as response:
            data=response.read(16385)
        if len(data)>16384:
            raise ValueError('Sensor response exceeds 16 KB')
        raw_text=data.decode('utf-8')
        def reject_nonfinite(token):
            raise ValueError('Non-standard nonfinite JSON value: '+token)
        raw=json.loads(raw_text,parse_constant=reject_nonfinite)
        if not isinstance(raw,dict):
            raise ValueError('Sensor response must be an object')
        if raw.get('valid') is True:
            distance=raw.get('distance_mm')
            sequence=raw.get('sequence')
            integer(distance,'device distance',0,10000)
            integer(sequence,'device sequence',0,4294967295)
            session=str(raw.get('boot_id','unknown'))
            if len(session)>50:
                raise ValueError('Device boot ID too long')
            obs={'id':session+':'+str(sequence),'sample_ms':start,'distance_mm':distance,'device_id':'http-sensor','session_id':session,
                'sequence':sequence,'units':'mm','source_timestamp_ms':raw.get('uptime_ms'),'source_clock':'device uptime, unsynchronized'}
        else:
            error='Device reported invalid/partial input'
        auxiliary=raw.get('streams',{})
        if not isinstance(auxiliary,dict):
            raise ValueError('Device streams must be an object')
        for name,value in auxiliary.items():
            if value is None:
                streams[name]=None
            elif isinstance(value,dict):
                streams[name]={'id':f'{name}:{capture_sequence}','sample_ms':start,**value}
                # Never silently treat a device-domain timestamp as a host-domain time.
                streams[name]['source_sample_ms']=value.get('sample_ms')
                streams[name]['sample_ms']=start
            else:
                raise ValueError('Each stream must be an observation object')
        validate_streams({'time_ms':start,'streams':streams})
    except (OSError,ValueError,KeyError,TypeError) as exc:
        obs=None
        streams={}
        error=str(exc)[:200]
        if raw is None and raw_text is not None:
            raw={'invalid_json_text':raw_text}
    now=(time.monotonic_ns()-origin)//1000000
    return {'time_ms':now,'observation':obs,'streams':streams,'raw_observation':raw,'capture_error':error,
            'capture_sequence':capture_sequence,'request_start_ms':start,'receive_ms':now,'uncertainty_ms':now-start}


class Recorder:
    def __init__(self):
        self.lock=threading.RLock()
        self.stop_event=threading.Event()
        self.thread=None
        self.events=[]
        self.options={}
        self.state='idle'
        self.total=0
        self.gaps=0
        self.errors=0
        self.evicted=0
        self.retained_bytes=0
        self.last_sequence=None
        self.last_session=None

    def start(self, options):
        with self.lock:
            if self.state=='recording' or self.thread and self.thread.is_alive():
                raise ValueError('Capture already running')
            if not isinstance(options,dict):
                raise ValueError('Capture options must be an object')
            adapter=options.get('adapter','mock')
            if adapter not in ('mock','http'):
                raise ValueError('Adapter must be mock or http')
            interval=options.get('interval_ms',200)
            capacity=options.get('capacity',200)
            integer(interval,'capture interval',20,60000)
            integer(capacity,'capture buffer',10,1000)
            url=options.get('url','')
            if not isinstance(url,str) or len(url)>4096:
                raise ValueError('Sensor URL must be a string of at most 4096 characters')
            if adapter=='http':
                parsed=urlparse(url)
                if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password:
                    raise ValueError('Supply an HTTP sensor URL without embedded credentials')
            self.options={'adapter':adapter,'interval_ms':interval,'capacity':capacity,'url':url}
            self.events=[]
            self.error=None
            self.total=self.gaps=self.errors=self.evicted=0
            self.retained_bytes=0
            self.last_sequence=self.last_session=None
            self.stop_event=threading.Event()
            self.state='recording'
            self.thread=threading.Thread(target=self._run,daemon=True,name='causalbench-capture')
            self.thread.start()
        return self.snapshot()

    def _run(self):
        origin=time.monotonic_ns()
        try:
            while not self.stop_event.is_set():
                with self.lock:
                    i=self.total
                    options=copy.deepcopy(self.options)
                if options['adapter']=='http':
                    event=read_http(options['url'],origin,i)
                else:
                    now=(time.monotonic_ns()-origin)//1000000
                    distance=70 if i%12 in (3,4,5,8,9) else 250
                    event={'time_ms':now,'observation':{'id':f'mock:{i}','sample_ms':now,'distance_mm':distance,
                        'device_id':'mock-sensor','session_id':'mock','sequence':i,'units':'mm'},
                        'streams':{name:stream_value(name,now,i,distance) for name in ('temperature','imu','proximity')},
                        'receive_ms':now,'capture_sequence':i,'uncertainty_ms':0,'capture_error':None}
                with self.lock:
                    if self.events:
                        event['time_ms']=max(event['time_ms'],self.events[-1]['time_ms']+1)
                    obs=event['observation']
                    if obs:
                        session=obs.get('session_id')
                        seq=obs.get('sequence')
                        if session==self.last_session and self.last_sequence is not None and seq>self.last_sequence+1:
                            self.gaps+=seq-self.last_sequence-1
                        if session!=self.last_session or self.last_sequence is None or seq>self.last_sequence:
                            self.last_sequence,self.last_session=seq,session
                    self.errors+=int(event.get('capture_error') is not None)
                    self.events.append(event)
                    self.retained_bytes+=len(canonical(event).encode())
                    self.total+=1
                    while len(self.events)>options['capacity'] or self.retained_bytes>1500000:
                        removed=self.events.pop(0)
                        self.retained_bytes-=len(canonical(removed).encode())
                        self.evicted+=1
                self.stop_event.wait(options['interval_ms']/1000)
        except Exception as exc:
            with self.lock:
                self.state='error'
                self.error=str(exc)[:200]
        finally:
            with self.lock:
                if self.state!='error':
                    self.state='stopped'

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=3)
        return self.snapshot()

    def snapshot(self):
        with self.lock:
            return {'state':self.state,'options':copy.deepcopy(self.options),'total_received':self.total,'retained':len(self.events),
                'evicted':self.evicted,'sequence_gaps':self.gaps,'error_events':self.errors,'error':getattr(self,'error',None),
                'retained_bytes':self.retained_bytes,
                'latest':copy.deepcopy(self.events[-1]) if self.events else None,'synthetic':self.options.get('adapter')=='mock'}

    def trace(self):
        with self.lock:
            if not self.events:
                raise ValueError('Capture has no observations yet')
            trace={'schema_version':1,'mode':'captured-input','scenario':'live-'+self.options['adapter'],
                'source_kind':'synthetic-mock' if self.options['adapter']=='mock' else 'device-http',
                'clock':'host monotonic; sample time estimated at request start; device time retained separately',
                'capture_options':copy.deepcopy(self.options),'evicted_events':self.evicted,
                'events':copy.deepcopy(self.events),'controllers':['baseline-v1','guarded-v1']}
        validate_trace(trace)
        return trace
