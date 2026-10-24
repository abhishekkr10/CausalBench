"""Built-in and declarative controllers. Native execution requires an installed, trusted adapter."""
from .provenance import loaded_source, register_source
_LOADED_SOURCE=register_source(__file__)
import copy
import hashlib
import json
import subprocess
import os
from functools import lru_cache
from pathlib import Path
from .engine import replay, digest
from .faults import configuration

ROOT = Path(__file__).resolve().parent.parent
NATIVE_NAME='native_guarded.exe' if os.name=='nt' else 'native_guarded'
BUILTINS = {
    'baseline-v1': {'description': 'Naive threshold and repeat-last on missing input', 'kind': 'builtin'},
    'guarded-v1': {'description': 'Freshness, identity, ordering and hysteresis', 'kind': 'builtin'},
    'fusion-v1': {'description': 'Guarded policy with fresh proximity corroboration and IMU veto', 'kind': 'fusion'},
}


def registry():
    files=sorted(p for p in (ROOT/'controllers').glob('*') if p.is_file())
    signature=tuple((str(p),p.stat().st_mtime_ns,p.stat().st_size) for p in files)
    return copy.deepcopy(_registry(signature))


@lru_cache(maxsize=4)
def _registry(signature):
    result = copy.deepcopy(BUILTINS)
    for path in sorted((ROOT / 'controllers').glob('*.controller.json')):
        spec = json.loads(path.read_text(encoding='utf-8-sig'))
        identity = spec.get('id')
        if not isinstance(identity, str) or not identity or len(identity) > 60 or identity in result:
            raise ValueError('Invalid or duplicate controller ID in ' + path.name)
        if spec.get('kind') not in ('rule','native') or type(spec.get('schema_version')) is not int or spec.get('schema_version') != 1:
            raise ValueError('Controller plugins support schema 1, rule or native kind')
        spec['configuration'] = configuration(spec.get('configuration'))
        if type(spec.get('require_proximity', False)) is not bool:
            raise ValueError('require_proximity must be boolean')
        if spec['kind']=='native':
            executable=spec.get('executable')
            source=spec.get('source')
            if not isinstance(executable,str) or Path(executable).name!=executable or not isinstance(source,str) or Path(source).name!=source:
                raise ValueError('Native executable/source must be local filenames')
            executable_path=(ROOT/'controllers'/executable).resolve()
            source_path=(ROOT/'controllers'/source).resolve()
            if executable_path.parent!=(ROOT/'controllers').resolve() or source_path.parent!=(ROOT/'controllers').resolve():
                raise ValueError('Native plugin must remain inside controllers directory')
            spec.update(executable_name=executable,executable_sha256=hashlib.sha256(executable_path.read_bytes()).hexdigest(),source_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest())
        result[identity] = {**spec, 'spec_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    executable = ROOT / 'controllers' / NATIVE_NAME
    source = ROOT / 'controllers' / 'native_guarded.cpp'
    if executable.exists() and source.exists():
        result['native-guarded-v1'] = {'kind': 'native', 'description': 'Compiled C++ threshold controller via stdin/stdout','executable_name':NATIVE_NAME,
            'executable_sha256': hashlib.sha256(executable.read_bytes()).hexdigest(),
            'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
    return result


def summarize(rows, trace):
    known = all('fixture_present' in e for e in trace['events'])
    return {'events': len(rows), 'pulses': sum(r['command'] == 'PULSE' for r in rows),
        'unsafe_fixture_pulses': sum(r['command'] == 'PULSE' and not e['fixture_present'] for r,e in zip(rows,trace['events'])) if known else None,
        'missed_present_events': sum(r['command'] == 'HOLD' and e['fixture_present'] for r,e in zip(rows,trace['events'])) if known else None,
        'rejected_stale': sum('Stale' in r['reason'] for r in rows),
        'rejected_duplicate': sum('Duplicate' in r['reason'] for r in rows),
        'rejected_out_of_order': sum('Out-of-order' in r['reason'] for r in rows),
        'rejected_invalid': sum('Invalid' in r['reason'] for r in rows),
        'rejected_sensor_disagreement': sum('corroboration' in r['reason'] or 'IMU' in r['reason'] for r in rows),
        'missing_observation_duration_ms': sum(trace['events'][i+1]['time_ms']-e['time_ms'] for i,e in enumerate(trace['events'][:-1]) if e.get('observation') is None)}


def implementation_digest():
    files={name:hashlib.sha256(loaded_source(Path(__file__).with_name(name))).hexdigest()
           for name in ('engine.py','controllers.py','faults.py','provenance.py')}
    return digest({'sources':files,'installed_descriptors':registry()})


def evaluate(trace, identity):
    specs = registry()
    if identity not in specs:
        raise ValueError('Unknown controller: ' + str(identity))
    spec = specs[identity]
    cfg = configuration(trace.get('controller_configs', {}).get(identity, spec.get('configuration', trace.get('controller_config'))))
    local = copy.deepcopy(trace)
    local['controller_config'] = cfg
    if spec['kind'] == 'builtin':
        result = replay(local, identity)
    elif spec['kind'] == 'native':
        result = native_replay(local, cfg, spec)
    else:
        result = replay(local, 'guarded-v1')
        need_proximity = identity == 'fusion-v1' or spec.get('require_proximity', False)
        if need_proximity:
            # Recompute state through the controller contract after a sensor veto.
            accepted_rows = []
            for i, row in enumerate(result['rows']):
                if i and accepted_rows[-1]['command'] == 'HOLD':
                    # A veto terminates hysteresis; distance enter threshold applies next.
                    if row['command'] == 'PULSE' and local['events'][i].get('observation', {}).get('distance_mm', 10000) >= cfg['enter_mm']:
                        row.update(command='HOLD', reason='Sensor corroboration veto reset hysteresis', state_after='IDLE')
                if row['command'] == 'PULSE':
                    e = local['events'][i]
                    proximity = e.get('streams', {}).get('proximity')
                    imu = e.get('streams', {}).get('imu')
                    if not proximity or not proximity.get('valid', True) or e['time_ms']-proximity['sample_ms'] > cfg['max_age_ms'] or proximity.get('value') is not True:
                        row.update(command='HOLD', reason='Sensor corroboration missing, stale or negative', state_after='IDLE')
                    elif imu and imu.get('valid', True) and e['time_ms']-imu['sample_ms'] <= cfg['max_age_ms'] and abs(imu.get('value', 0)) > 1500:
                        row.update(command='HOLD', reason='IMU shock veto (>1500 milli_g)', state_after='IDLE')
                row['state_before'] = accepted_rows[-1]['state_after'] if accepted_rows else 'IDLE'
                accepted_rows.append(row)
            result['rows'] = accepted_rows
    result['policy'] = identity
    result['trace_digest'] = digest(trace)
    result['configuration'] = {**cfg,'exit_mm':cfg['enter_mm']} if identity=='baseline-v1' else cfg
    result['provenance'] = {**result.get('provenance', {}), 'controller_adapter_sha256': hashlib.sha256(_LOADED_SOURCE).hexdigest(), 'descriptor': spec}
    result['provenance']['implementation_digest'] = implementation_digest()
    result['policy_digest'] = digest({'id': identity, 'config': cfg, 'descriptor': spec})
    result['metrics'] = summarize(result['rows'], trace)
    for row, event in zip(result['rows'], trace['events']):
        if 'fixture_present' in event:
            row['unsafe_fixture_pulse'] = row['command'] == 'PULSE' and not event['fixture_present']
    return result


def native_replay(trace, cfg, spec):
    if len(trace['events']) > 1000:
        raise ValueError('Native adapter supports at most 1000 events')
    lines = [f"{cfg['enter_mm']} {cfg['exit_mm']} {cfg['max_age_ms']}"]
    for e in trace['events']:
        o = e.get('observation')
        # Transport arbitrary IDs as a stable integer index, not whitespace-delimited strings.
        identity = int(hashlib.sha256(o['id'].encode()).hexdigest()[:15],16) if o else 0
        lines.append(f"{e['time_ms']} {identity} {o['sample_ms'] if o else 0} {o.get('distance_mm') if o and o.get('valid',True) else -1} {int(o is not None)}")
    payload = '\n'.join(lines)+'\n'
    exe = ROOT / 'controllers' / spec['executable_name']
    outputs = []
    for _ in range(2):
        completed = subprocess.run([str(exe)], input=payload, text=True, capture_output=True, timeout=5, cwd=ROOT)
        if completed.returncode != 0 or len(completed.stdout) > 100000:
            raise ValueError('Native controller failed or exceeded output limit')
        outputs.append(completed.stdout.splitlines())
    if outputs[0] != outputs[1]:
        raise ValueError('Native controller was not deterministic in two identical invocations')
    if len(outputs[0]) != len(trace['events']):
        raise ValueError('Native controller returned the wrong number of decisions')
    rows = []
    reasons = {'accepted': 'Native threshold accepted', 'stale': 'Stale observation rejected', 'duplicate': 'Duplicate observation rejected',
        'order': 'Out-of-order sample rejected', 'invalid': 'Invalid observation rejected', 'missing': 'No observation; hold simulated actuator'}
    for line,e in zip(outputs[0], trace['events']):
        tokens = line.split()
        if len(tokens) != 2 or tokens[0] not in ('PULSE','HOLD') or not 1<=len(tokens[1])<=80 or any(not (ch.isalnum() or ch in '_-') for ch in tokens[1]):
            raise ValueError('Native controller violated its output contract')
        obs = e.get('observation')
        rows.append({'time_ms': e['time_ms'], 'observation_id': obs['id'] if obs else None,
            'sample_age_ms': e['time_ms']-obs['sample_ms'] if obs else None, 'command': tokens[0], 'reason': reasons.get(tokens[1],'Native decision: '+tokens[1].replace('_',' ')),
            'state_before': rows[-1]['state_after'] if rows else 'IDLE', 'state_after': 'ACTIVE' if tokens[0]=='PULSE' else 'IDLE'})
    return {'rows': rows, 'provenance': {'engine_source_sha256': hashlib.sha256(loaded_source(ROOT/'causalbench'/'engine.py')).hexdigest(), 'native_repeat_check': True}}


def comparison(trace):
    identities = trace.get('controllers', ['baseline-v1','guarded-v1'])
    if not isinstance(identities,list) or not 2 <= len(identities) <= 4 or not all(isinstance(p,str) for p in identities) or len(set(identities)) != len(identities):
        raise ValueError('Choose 2..4 distinct controllers')
    results = {p: evaluate(trace, p) for p in identities}
    first, second = (results[p] for p in identities[:2])
    return {'baseline': first, 'guarded': second, 'controllers': results,
        'divergence_times_ms': [a['time_ms'] for a,b in zip(first['rows'],second['rows']) if a['command'] != b['command']],
        'scope': 'Open-loop replay of identical recorded inputs; command disagreement does not prove a physical outcome.',
        'all_pair_divergences': {a+' vs '+b: sum(x['command']!=y['command'] for x,y in zip(results[a]['rows'],results[b]['rows']))
            for i,a in enumerate(identities) for b in identities[i+1:]}}
