"""Bounded background analysis jobs; completed results persist as verified artifacts."""
from .provenance import loaded_source, register_source
_LOADED_SOURCE=register_source(__file__)
import threading
import uuid
from .studies import batch, minimize, frontier
from .plant import simulate


class Jobs:
    def __init__(self,store):
        self.store=store
        self.lock=threading.Lock()
        self.items={}
        self.slots=threading.BoundedSemaphore(2)

    def submit(self,kind,body):
        if kind not in ('batch','minimize','frontier','plant'):
            raise ValueError('Unknown analysis kind')
        if not self.slots.acquire(blocking=False):
            raise ValueError('Two analyses are already running; wait for a result')
        identity=uuid.uuid4().hex
        with self.lock:
            if len(self.items)>=100:
                finished=next((k for k,v in self.items.items() if v['status'] in ('complete','failed')),None)
                if finished:
                    self.items.pop(finished)
            self.items[identity]={'id':identity,'kind':kind,'status':'running'}
        threading.Thread(target=self._run,args=(identity,kind,body),daemon=True).start()
        return self.get(identity)

    def _run(self,identity,kind,body):
        try:
            if kind=='batch':
                result=batch(body.get('spec',{}),body.get('seeds',[42]),body.get('variations'))
            elif kind=='frontier':
                result=frontier(body.get('spec',{}),body.get('parameter','delay_ms'),body.get('values'),body.get('seeds'),body.get('predicate','baseline-incorrect'))
            elif kind=='plant':
                result=simulate(body.get('spec',{}),body.get('ticks',60),body.get('step_ms',200),body.get('speed_mm_s',180),body.get('gate_rate_deg_s',150))
            else:
                run=self.store.get(body.get('run_id',''))
                result=minimize(run['bundle']['manifest']['trace'],body.get('predicate','divergence'),body.get('budget',150))
                result['run_id']=self.store.create(result['trace'])['id']
            result['reproduction_input']=dict(body)
            if kind=='minimize':
                result['reproduction_input']['trace']=run['bundle']['manifest']['trace']
            artifact=self.store.save_artifact(kind,result)
            with self.lock:
                self.items[identity].update(status='complete',artifact_id=artifact['id'],result=artifact['payload'])
        except Exception as exc:
            with self.lock:
                self.items[identity].update(status='failed',error=str(exc)[:300])
        finally:
            self.slots.release()

    def get(self,identity):
        with self.lock:
            if identity not in self.items:
                raise KeyError('Job not found')
            return dict(self.items[identity])
