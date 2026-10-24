"""Seeded fault composition, with common random draws across parameter sweeps."""
from .provenance import loaded_source, register_source
_LOADED_SOURCE=register_source(__file__)
import copy
import math
import random
from .engine import make_trace, validate_trace, integer

DEFAULT_FAULTS = {"delay_ms": 600, "delay_rate": 0.0, "drop_rate": 0.0,
                  "duplicate_rate": 0.0, "reorder_rate": 0.0, "invalid_rate": 0.0,
                  "noise_mm": 0, "start_ms": 1200, "duration_ms": 1000,
                  "disconnect_stream": "none"}
DEFAULT_CONFIG = {"version": 1, "enter_mm": 100, "exit_mm": 120, "max_age_ms": 300}


def configuration(value=None):
    if value is not None and not isinstance(value, dict):
        raise ValueError("Controller configuration must be an object")
    result = {**DEFAULT_CONFIG, **(value or {})}
    if set(result) != set(DEFAULT_CONFIG) or type(result['version']) is not int or result['version'] != 1:
        raise ValueError("Unsupported controller configuration fields/version")
    for key, high in (("enter_mm", 10000), ("exit_mm", 10000), ("max_age_ms", 86400000)):
        integer(result[key], key, 0, high)
    if result['exit_mm'] < result['enter_mm']:
        raise ValueError("Exit threshold must be >= enter threshold")
    return result


def settings(value=None):
    if value is not None and not isinstance(value, dict):
        raise ValueError("Fault settings must be an object")
    result = {**DEFAULT_FAULTS, **(value or {})}
    if set(result) != set(DEFAULT_FAULTS):
        raise ValueError("Unknown fault field")
    for key in ('delay_rate', 'drop_rate', 'duplicate_rate', 'reorder_rate', 'invalid_rate'):
        v = result[key]
        if type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1:
            raise ValueError(key + " must be 0..1")
    for key, high in (("delay_ms", 60000), ("noise_mm", 2000), ("start_ms", 86400000), ("duration_ms", 86400000)):
        integer(result[key], key, 0, high)
    if result['disconnect_stream'] not in ('none', 'temperature', 'imu', 'proximity'):
        raise ValueError("Unknown auxiliary sensor stream")
    return result


def stream_value(name, now, seq, distance):
    values = {'temperature': (24000 + (seq % 7) * 100, 'milliC'),
              'imu': (seq % 5 * 10, 'milli_g'), 'proximity': (distance < 100, 'bool')}
    value, unit = values[name]
    return {'id': f'{name}-{seq}', 'device_id': f'sim-{name}', 'session_id': 'simulation',
            'sequence': seq, 'sample_ms': now, 'value': value, 'unit': unit, 'valid': True}


def apply_faults(obs, history, now, faults, draws, noise):
    """Arrival order stays fixed. Delays select an actual previously sampled value."""
    result = copy.deepcopy(obs)
    audit = []
    if not faults['start_ms'] <= now < faults['start_ms'] + faults['duration_ms']:
        return result, audit
    if result is not None and draws[0] < faults['delay_rate']:
        old = [o for o in history + [obs] if o is not None and o['sample_ms'] <= now - faults['delay_ms']]
        if old:
            result = copy.deepcopy(old[-1])
            # Distinct transport identity makes freshness/order, rather than deduplication, observable.
            result['id'] += f':delivered-{now}'
            audit.append('delay')
    if result is not None and draws[1] < faults['duplicate_rate'] and history:
        prior = next((o for o in reversed(history) if o is not None), None)
        if prior is not None:
            result = copy.deepcopy(prior)
            audit.append('duplicate')
    if result is not None and draws[2] < faults['reorder_rate'] and len(history) >= 2:
        prior = next((o for o in reversed(history[:-1]) if o is not None), None)
        if prior is not None:
            result = copy.deepcopy(prior)
            result['id'] += f':out-of-order-{now}'
            audit.append('out-of-order')
    if result is not None and faults['noise_mm']:
        if result.get('valid', True):
            result['distance_mm'] = max(0, min(10000, result['distance_mm'] + round(noise * faults['noise_mm'])))
            audit.append('noise')
    if result is not None and draws[3] < faults['invalid_rate']:
        result.update(valid=False, raw_distance_mm=result.get('distance_mm'), distance_mm=None)
        audit.append('invalid')
    if draws[4] < faults['drop_rate']:
        result = None
        audit.append('drop')
    return result, audit


def generate(scenario='stale', seed=42, faults=None, events=12, multistream=False, configs=None, policies=None):
    integer(events, 'event count', 1, 1000)
    integer(seed, 'seed', 0, 4294967295)
    if type(multistream) is not bool:
        raise ValueError('multistream must be boolean')
    f = settings(faults)
    rng = random.Random(seed)
    template = make_trace(scenario, seed)
    clean_template = make_trace('normal', seed)
    trace = {k: copy.deepcopy(v) for k, v in template.items() if k != 'events'}
    trace.update(events=[], fault_settings=f, generator_version=1, multistream=multistream)
    history = []
    for i in range(events):
        e = copy.deepcopy(template['events'][i % 12])
        offset = (i // 12) * 2400
        e['time_ms'] += offset
        e['receive_ms'] = e['time_ms']
        e['capture_sequence'] = i
        obs = e['observation']
        if obs is not None:
            obs['id'] = f"cycle-{i//12}:{obs['id']}"
            obs['sample_ms'] += offset
            obs['sequence'] = i
        original = copy.deepcopy(obs)
        # Draw every channel every tick, including outside the fault window.
        draws = [rng.random() for _ in range(5)]
        obs, audit = apply_faults(obs, history, e['time_ms'], f, draws, rng.uniform(-1, 1))
        e.update(observation=obs, applied_faults=audit)
        if multistream:
            # Separate transducers sample the current scene, not the corrupted primary reading.
            source_distance = clean_template['events'][i % 12]['observation']['distance_mm']
            e['streams'] = {name: stream_value(name, e['time_ms'], i, source_distance)
                            for name in ('temperature', 'imu', 'proximity')}
            if f['start_ms'] <= e['time_ms'] < f['start_ms'] + f['duration_ms'] and f['disconnect_stream'] != 'none':
                e['streams'][f['disconnect_stream']] = None
                e['applied_faults'].append('disconnect:' + f['disconnect_stream'])
        history.append(original)
        trace['events'].append(e)
    if policies is not None:
        if not isinstance(policies, list) or not 2 <= len(policies) <= 4 or len(set(policies)) != len(policies) or not all(isinstance(p, str) for p in policies):
            raise ValueError('Choose 2..4 distinct controller IDs')
        trace['controllers'] = policies
    if configs is not None:
        if not isinstance(configs, dict):
            raise ValueError('Controller configurations must be an object')
        trace['controller_configs'] = {p: configuration(c) for p, c in configs.items()}
    validate_trace(trace)
    return trace


def validate_streams(event):
    streams = event.get('streams', {})
    if not isinstance(streams, dict) or len(streams) > 16:
        raise ValueError('At most 16 auxiliary streams per event')
    for name, obs in streams.items():
        if not isinstance(name, str) or not 1 <= len(name) <= 50:
            raise ValueError('Invalid stream name')
        if obs is None:
            continue
        if not isinstance(obs, dict) or not isinstance(obs.get('id'), str) or not 1 <= len(obs['id']) <= 100:
            raise ValueError('Invalid stream observation')
        integer(obs.get('sample_ms'), 'stream sample time', 0, event['time_ms'])
        if type(obs.get('valid', True)) is not bool:
            raise ValueError('Invalid stream validity')
        unit = obs.get('unit')
        if unit not in ('milliC', 'milli_g', 'bool', 'mm'):
            raise ValueError('Unknown stream units')
        if obs.get('valid', True):
            if unit == 'bool':
                if type(obs.get('value')) is not bool:
                    raise ValueError('Boolean sensor needs a boolean value')
            else:
                integer(obs.get('value'), 'stream value', -1000000, 1000000)
