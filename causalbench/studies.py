"""Paired-seed studies, bounded delta debugging, regression assertions and boundary scans."""
from .provenance import loaded_source, register_source
_LOADED_SOURCE=register_source(__file__)
import copy
import math
from .engine import compare, digest, integer, validate_trace
from .faults import generate, configuration, settings


def spec_trace(spec, seed=None):
    if not isinstance(spec, dict):
        raise ValueError('Experiment specification must be an object')
    return generate(spec.get('scenario','stale'), spec.get('seed',42) if seed is None else seed,
        spec.get('faults'), spec.get('events',12), spec.get('multistream',False),
        spec.get('configs'), spec.get('controllers',['baseline-v1','guarded-v1']))


def summary(trace, result):
    return {'trace_digest': digest(trace), 'seed': trace.get('seed'), 'divergences': len(result['divergence_times_ms']),
        'controllers': {p: r['metrics'] for p,r in result.get('controllers', {result['baseline']['policy']:result['baseline'],result['guarded']['policy']:result['guarded']}).items()}}


def batch(spec, seeds, variations=None):
    if not isinstance(seeds,list) or not 1 <= len(seeds) <= 30:
        raise ValueError('Supply 1..30 seeds')
    for seed in seeds:
        integer(seed,'seed',0,4294967295)
    variations = variations or [{'label':'selected settings'}]
    if not isinstance(variations,list) or not 1 <= len(variations) <= 12 or len(variations)*len(seeds)>120:
        raise ValueError('Study supports at most 120 paired runs')
    records = []
    groups = []
    for index, variation in enumerate(variations):
        if not isinstance(variation,dict):
            raise ValueError('Each variation must be an object')
        local = copy.deepcopy(spec)
        local['faults'] = {**settings(local.get('faults')), **variation.get('faults',{})}
        if 'configs' in variation:
            local['configs'] = variation['configs']
        group = []
        for seed in seeds:
            trace = spec_trace(local,seed)
            item = summary(trace,compare(trace))
            item['variation'] = index
            records.append(item)
            group.append(item)
        per_controller = {}
        for p in group[0]['controllers']:
            metrics = [r['controllers'][p] for r in group]
            errors = [m['unsafe_fixture_pulses'] for m in metrics]
            per_controller[p] = {'mean_incorrect_pulses': sum(errors)/len(errors) if all(e is not None for e in errors) else None,
                'runs_with_incorrect_pulse': sum(e>0 for e in errors if e is not None),
                'missed_present_events': sum(m.get('missed_present_events') or 0 for m in metrics),
                'events': sum(m['events'] for m in metrics),
                'rejections': sum(sum(m.get(k,0) for k in ('rejected_stale','rejected_duplicate','rejected_invalid','rejected_out_of_order','rejected_sensor_disagreement')) for m in metrics)}
            per_controller[p]['rejection_fraction']=per_controller[p]['rejections']/max(1,per_controller[p]['events'])
        groups.append({'label': str(variation.get('label', f'variation {index+1}'))[:100], 'runs':len(group),
            'mean_divergences':sum(r['divergences'] for r in group)/len(group), 'controllers':per_controller})
    return {'kind':'batch', 'spec':spec, 'seeds':seeds, 'variations':variations, 'groups':groups, 'records':records,
        'scope':'Paired seeded simulations. Frequencies describe these selected trials, not hardware reliability.'}


def fails(trace, predicate='divergence'):
    c = compare(trace)
    if predicate == 'divergence':
        return bool(c['divergence_times_ms'])
    if predicate not in ('baseline-incorrect','guarded-incorrect'):
        raise ValueError('Unknown failure predicate')
    metric = c[predicate.split('-')[0]]['metrics']['unsafe_fixture_pulses']
    if metric is None:
        raise ValueError('Outcome predicate requires fixture ground truth')
    return metric>0


def minimize(trace, predicate='divergence', budget=150):
    validate_trace(trace)
    integer(budget,'minimization budget',1,300)
    if len(trace['events'])>300:
        raise ValueError('Minimizer supports at most 300 events')
    if not fails(trace,predicate):
        raise ValueError('Selected predicate does not occur in this trace')
    original = copy.deepcopy(trace)
    candidate = copy.deepcopy(trace)
    evaluations = 0
    granularity = 2
    def check(events):
        nonlocal evaluations
        evaluations += 1
        t = {**candidate,'events':events}
        return fails(t,predicate)
    while len(candidate['events'])>=2 and evaluations<budget:
        events = candidate['events']
        size = math.ceil(len(events)/granularity)
        changed = False
        for start in range(0,len(events),size):
            if evaluations>=budget:
                break
            remaining = events[:start]+events[start+size:]
            if remaining and check(remaining):
                candidate['events'] = remaining
                granularity = max(2,granularity-1)
                changed = True
                break
        if not changed:
            if granularity>=len(events):
                break
            granularity = min(len(events),granularity*2)
    # Certify 1-minimality rather than claiming a globally smallest trace.
    one_minimal = len(candidate['events'])==1
    if not one_minimal:
        i = 0
        while i<len(candidate['events']) and evaluations<budget:
            remaining = candidate['events'][:i]+candidate['events'][i+1:]
            if remaining and check(remaining):
                candidate['events']=remaining
                i=0
            else:
                i+=1
        one_minimal = i==len(candidate['events'])
    return {'kind':'minimization', 'predicate':predicate, 'original_digest':digest(original), 'original_events':len(original['events']),
        'retained_events':len(candidate['events']), 'evaluations':evaluations, 'one_minimal':one_minimal,
        'trace':candidate, 'comparison':compare(candidate),
        'scope':'Deletes events without changing their timestamps or IDs; each candidate starts from the declared default controller state. Reproduces the predicate, not the original full state history.'}


def regression(trace, name, limits=None):
    validate_trace(trace)
    if not isinstance(name,str) or not 1<=len(name)<=100:
        raise ValueError('Regression name must be 1..100 characters')
    limits = limits or {'guarded_max_incorrect':0}
    if not isinstance(limits,dict) or not limits or set(limits)-{'guarded_max_incorrect','baseline_max_incorrect','max_divergences','expected_commands'}:
        raise ValueError('Unsupported regression assertion')
    for k,v in limits.items():
        if k!='expected_commands':
            integer(v,k,0,10000)
    if 'expected_commands' in limits:
        commands=limits['expected_commands']
        if not isinstance(commands,list) or len(commands)!=len(trace['events']) or any(c not in ('PULSE','HOLD') for c in commands):
            raise ValueError('Expected commands must cover every event')
    c=compare(trace)
    return {'kind':'regression', 'name':name, 'trace':trace, 'trace_digest':digest(trace), 'limits':limits,
        'saved_policy_digests': {n:r['policy_digest'] for n,r in c.get('controllers',{'baseline':c['baseline'],'guarded':c['guarded']}).items()}}


def check_regression(case):
    if digest(case['trace'])!=case['trace_digest']:
        raise ValueError('Regression trace integrity failed')
    c=compare(case['trace'])
    checks=[]
    for key,limit in case['limits'].items():
        if key=='expected_commands':
            actual=[r['command'] for r in c['guarded']['rows']]
        elif key=='max_divergences':
            actual=len(c['divergence_times_ms'])
        else:
            actual=c[key.split('_')[0]]['metrics']['unsafe_fixture_pulses']
        passed=actual==limit if key=='expected_commands' else actual is not None and actual<=limit
        checks.append({'assertion':key,'actual':actual,'limit':limit,'passed':passed,'known':actual is not None})
    return {'name':case['name'],'passed':all(c['passed'] for c in checks),'checks':checks,
        'scope':'Current-controller regression against a fixed recorded trace.'}


def frontier(spec, parameter='delay_ms', values=None, seeds=None, predicate='baseline-incorrect'):
    if parameter not in ('delay_ms','drop_rate','duplicate_rate','noise_mm'):
        raise ValueError('Unsupported boundary parameter')
    values=values if values is not None else list(range(0,1201,100))
    seeds=seeds if seeds is not None else [42]
    if not isinstance(values,list) or not 1<=len(values)<=20 or not isinstance(seeds,list) or not 1<=len(seeds)<=10 or len(values)*len(seeds)>100:
        raise ValueError('Boundary scan supports at most 100 evaluations')
    points=[]
    for value in values:
        local=copy.deepcopy(spec)
        f=settings(local.get('faults'))
        f[parameter]=value
        if parameter=='delay_ms' and not f['delay_rate']:
            f['delay_rate']=1.0
        local['faults']=settings(f)
        failures=[]
        for seed in seeds:
            trace=spec_trace(local,seed)
            failures.append(fails(trace,predicate))
        points.append({'value':value,'failed_seeds':sum(failures),'seeds':len(seeds),'any_failure':any(failures)})
    first=next((p['value'] for p in points if p['any_failure']),None)
    return {'kind':'frontier','parameter':parameter,'predicate':predicate,'points':points,'first_observed_failure':first,
        'spec':spec,'seeds':seeds,'scope':'Exhaustive scan of supplied grid in its supplied order. No monotonicity, continuous threshold, or hardware reliability is inferred.'}
