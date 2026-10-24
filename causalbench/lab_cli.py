"""Headless research and CI entry points for the same dashboard services."""
from .provenance import loaded_source, register_source
_LOADED_SOURCE=register_source(__file__)
import argparse
import json
from pathlib import Path
from .engine import canonical, compare, seal
from .studies import spec_trace, batch, frontier, minimize, check_regression
from .plant import simulate
from .controllers import registry
from .server import Store
from . import packages


def main():
    parser=argparse.ArgumentParser(description='CausalBench experiment/analysis CLI')
    parser.add_argument('command',choices=['experiment','batch','frontier','plant','minimize','regressions','package','controllers'])
    parser.add_argument('--input',type=Path,help='JSON request, trace, or regression case list')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--database',type=Path,default=Path('data/experiments.sqlite'))
    parser.add_argument('--run-id')
    args=parser.parse_args()
    body=json.loads(args.input.read_text(encoding='utf-8-sig')) if args.input else {}
    exit_code=0
    if args.command=='controllers':
        result=registry()
    elif args.command=='experiment':
        trace=spec_trace(body)
        result=seal(trace,compare(trace))
    elif args.command=='batch':
        result=batch(body.get('spec',{}),body.get('seeds',[42]),body.get('variations'))
    elif args.command=='frontier':
        result=frontier(body.get('spec',{}),body.get('parameter','delay_ms'),body.get('values'),body.get('seeds'),body.get('predicate','baseline-incorrect'))
    elif args.command=='plant':
        result=simulate(body.get('spec',{}),body.get('ticks',60),body.get('step_ms',200),body.get('speed_mm_s',180),body.get('gate_rate_deg_s',150))
    elif args.command=='minimize':
        result=minimize(body.get('trace',body),body.get('predicate','divergence'),body.get('budget',150))
    elif args.command=='regressions':
        cases=body.get('cases') if args.input else [Store(args.database).artifact(a['id'])['payload'] for a in Store(args.database).artifacts('regression')]
        if not cases:
            parser.error('No regression cases supplied or saved; an empty suite is not a passing check')
        result={'kind':'regression-check','cases':[check_regression(c) for c in cases]}
        exit_code=0 if all(c['passed'] for c in result['cases']) else 1
    else:
        if not args.run_id or not args.output:
            parser.error('package requires --run-id and --output')
        data=Store(args.database).package(args.run_id)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_bytes(data)
        print('Saved '+str(args.output))
        return
    if args.command in ('batch','frontier','plant','minimize'):
        result['reproduction_input']=body
        if args.command=='minimize':
            result['reproduction_input']={'trace':body.get('trace',body),'predicate':body.get('predicate','divergence'),'budget':body.get('budget',150)}
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
        print('Saved '+str(args.output))
    else:
        print(canonical(result))
    raise SystemExit(exit_code)


if __name__=='__main__':
    main()
