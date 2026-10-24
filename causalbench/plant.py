"""A small explicitly labelled gate/queue model, with independent feedback trajectories."""
from .provenance import loaded_source, register_source
_LOADED_SOURCE=register_source(__file__)
import copy
import random
from .engine import integer
from .faults import settings, apply_faults, stream_value, configuration
from .controllers import evaluate, registry


def simulate(spec, ticks=60, step_ms=200, speed_mm_s=180, gate_rate_deg_s=150):
    integer(ticks,'plant ticks',5,200)
    integer(step_ms,'plant step',10,1000)
    integer(speed_mm_s,'object speed',1,1000)
    integer(gate_rate_deg_s,'gate angular speed',1,1000)
    if not isinstance(spec,dict):
        raise ValueError('Plant specification must be an object')
    identities=spec.get('controllers',['baseline-v1','guarded-v1'])
    if not isinstance(identities,list) or not 2<=len(identities)<=3 or len(set(identities))!=len(identities):
        raise ValueError('Choose 2..3 controllers for plant simulation')
    if any(p not in registry() or registry()[p]['kind']=='native' for p in identities):
        raise ValueError('Closed-loop model supports built-in/declarative controllers; native plugins are open-loop only')
    seed=spec.get('seed',42)
    integer(seed,'seed',0,4294967295)
    faults=settings(spec.get('faults'))
    trajectories={}
    for identity in identities:
        rng=random.Random(seed)
        angle=0.0
        position=None
        history=[]
        states=[]
        passed=0
        blocked_ms=0
        exposure_ms=0
        trace={'schema_version':1,'mode':'simulation','scenario':'closed-loop-gate','seed':seed,'events':[],
            'controller_configs':spec.get('configs',{}),'controllers':identities,'fault_settings':faults}
        for i in range(ticks):
            now=i*step_ms
            if position is None and i % 30 == 0:
                position=250.0
            # Input is produced from this controller's own plant state.
            distance=min(10000,round(abs(position))) if position is not None else 1000
            present=position is not None and abs(position)<100
            original={'id':f'plant-{i}','sample_ms':now,'distance_mm':distance,'device_id':'plant-distance','sequence':i,'units':'mm'}
            observation,audit=apply_faults(original,history,now,faults,[rng.random() for _ in range(5)],rng.uniform(-1,1))
            e={'time_ms':now,'observation':observation,'fixture_present':present,'applied_faults':audit,
                'streams':{name:stream_value(name,now,i,distance) for name in ('proximity','imu','temperature')}}
            trace['events'].append(e)
            history.append(original)
            result=evaluate(trace,identity)
            command=result['rows'][-1]['command']
            target=90 if command=='PULSE' else 0
            delta=gate_rate_deg_s*step_ms/1000
            angle=max(target,angle-delta) if target<angle else min(target,angle+delta)
            if angle>=60 and not present:
                exposure_ms+=step_ms
            if position is not None:
                next_position=position-speed_mm_s*step_ms/1000
                # A closed gate stops an approaching object 35 mm before the gate plane.
                if position>=35 and next_position<35 and angle<60:
                    next_position=35.0
                    blocked_ms+=step_ms
                if position>=0 and next_position<0:
                    passed+=1
                position=next_position
                if position < -250:
                    position=None
            states.append({'time_ms':now,'gate_angle_deg':round(angle,3),'object_position_mm':None if position is None else round(position,3),
                'command':command,'reason':result['rows'][-1]['reason']})
        trajectories[identity]={'trace':trace,'replay':result,'plant_states':states,
            'metrics':{'objects_passed':passed,'blocked_duration_ms':blocked_ms,'open_without_near_object_ms':exposure_ms}}
    return {'kind':'closed-loop','seed':seed,'faults':faults,'parameters':{'ticks':ticks,'step_ms':step_ms,'speed_mm_s':speed_mm_s,'gate_rate_deg_s':gate_rate_deg_s},
        'trajectories':trajectories,'scope':'Independent model trajectories: controller outputs change future sensor inputs. Not identical-input replay and not physical validation.',
        'assumptions':['PULSE targets 90 degrees; HOLD targets 0 degrees.','Objects move at constant speed; gate passable at 60 degrees.','Closed gate queues approaching objects at 35 mm; no collision, torque, or acceleration model.','At most one object, spawned every 30 ticks when the scene is empty.']}
