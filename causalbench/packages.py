"""Portable source snapshots. Imports inspect archives; they never execute imported code."""
from .provenance import loaded_source, retained_sources, register_source
_LOADED_SOURCE=register_source(__file__)
import argparse
import ast
import hashlib
import io
import json
import platform
import sys
import zipfile
from functools import lru_cache
from pathlib import Path, PurePosixPath
from .engine import canonical, digest, verify

ROOT=Path(__file__).resolve().parent.parent
REPRODUCER='''from pathlib import Path
import hashlib, json, sys
from causalbench.engine import compare, canonical
root=Path(__file__).resolve().parent
inventory=json.loads((root/'inventory.json').read_text())
for name, expected in inventory['files'].items():
    if hashlib.sha256((root/name).read_bytes()).hexdigest()!=expected:
        raise SystemExit('Modified archived file: '+name)
bundle=json.loads((root/'evidence.json').read_text())
actual=compare(json.loads((root/'trace.json').read_text()))
ok=canonical(actual)==canonical(bundle['manifest']['comparison'])
print('REPRODUCED' if ok else 'MISMATCH')
raise SystemExit(0 if ok else 1)
'''
ANALYSIS_REPRODUCER='''from pathlib import Path
import hashlib,json
from causalbench.engine import canonical
from causalbench.studies import batch,frontier,minimize,check_regression
from causalbench.plant import simulate
root=Path(__file__).resolve().parent
inventory=json.loads((root/'inventory.json').read_text())
for name,sha in inventory['files'].items():
    if hashlib.sha256((root/name).read_bytes()).hexdigest()!=sha:
        raise SystemExit('Modified file: '+name)
saved=json.loads((root/'analysis.json').read_text())
body=saved['reproduction_input']; kind=saved['kind']
if kind=='batch': actual=batch(body.get('spec',{}),body.get('seeds',[42]),body.get('variations'))
elif kind=='frontier': actual=frontier(body.get('spec',{}),body.get('parameter','delay_ms'),body.get('values'),body.get('seeds'),body.get('predicate','baseline-incorrect'))
elif kind=='minimization': actual=minimize(body['trace'],body.get('predicate','divergence'),body.get('budget',150))
elif kind=='closed-loop': actual=simulate(body.get('spec',{}),body.get('ticks',60),body.get('step_ms',200),body.get('speed_mm_s',180),body.get('gate_rate_deg_s',150))
elif kind=='regression-check': actual={'kind':kind,'cases':[check_regression(c) for c in body['cases']]}
else: raise SystemExit('No analysis reproducer for this kind')
expected={k:v for k,v in saved.items() if k not in ('reproduction_input','run_id')}
ok=canonical(actual)==canonical(expected)
print('REPRODUCED' if ok else 'MISMATCH')
raise SystemExit(0 if ok else 1)
'''


def source_snapshot():
    paths=[]
    for folder,patterns in (('causalbench',['*.py']),('controllers',['*.cpp','*.c','*.h','*.hpp','*.exe','*.bin','*.dll','native_guarded','*.json'])):
        for pattern in patterns:
            paths.extend(sorted((ROOT/folder).glob(pattern)))
    for name in retained_sources():
        p=Path(name)
        if p.parent==(ROOT/'causalbench').resolve() and p not in paths:
            paths.append(p)
    signature=tuple((str(p),loaded_source(p) if p.parent==(ROOT/'causalbench').resolve() else p.read_bytes()) for p in sorted(set(paths)))
    return _snapshot(signature)


@lru_cache(maxsize=3)
def _snapshot(signature):
    files={}
    for name,content in signature:
        path=Path(name)
        files[path.relative_to(ROOT).as_posix()]=content
    inventory={'format_version':1,'files':{name:hashlib.sha256(data).hexdigest() for name,data in files.items()},
        'environment':{'python':platform.python_version(),'implementation':platform.python_implementation(),
            'platform':platform.platform(),'dependencies':'Python standard library; supplied native example built statically; other native adapters require their declared OS/runtime'}}
    fingerprint=digest(inventory)
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in files.items():
            z.writestr(name,data)
        z.writestr('source_inventory.json',canonical(inventory))
    return fingerprint,out.getvalue()


def build(bundle, source_bytes):
    if not verify(bundle):
        raise ValueError('Cannot package invalid evidence')
    source=zipfile.ZipFile(io.BytesIO(source_bytes))
    contents={name:source.read(name) for name in source.namelist() if name!='source_inventory.json'}
    environment=json.loads(source.read('source_inventory.json'))['environment']
    contents.update({'evidence.json':canonical(bundle).encode(),'trace.json':canonical(bundle['manifest']['trace']).encode(),
        'reproduce.py':archived_reproducer(contents,'REPRODUCER'),'HOW_TO_REPRODUCE.md':
        b'# Reproduce a trusted local archive\n\nInspect the package first: python -m causalbench.packages verify FILE.zip\n\nOnly extract and run source you trust. Extract to a new directory, then run `python reproduce.py` with the recorded Python version. Native artifacts require the recorded OS/architecture. Expected result: REPRODUCED.\n\nImports into CausalBench only inspect archives and replay their trace using installed controllers. They never run archived code. The inventory is a consistency check, not a signature.\n'})
    inventory={'format_version':1,'environment':environment,'files':{name:hashlib.sha256(data).hexdigest() for name,data in contents.items()},
        'evidence_digest':bundle['manifest_digest']}
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in contents.items():
            z.writestr(name,data)
        z.writestr('inventory.json',canonical(inventory))
        z.writestr('inventory.sha256',digest(inventory))
    return out.getvalue()


def build_analysis(payload, source_bytes):
    if 'reproduction_input' not in payload:
        raise ValueError('This artifact has no saved reproduction request')
    with zipfile.ZipFile(io.BytesIO(source_bytes)) as source:
        contents={name:source.read(name) for name in source.namelist() if name!='source_inventory.json'}
        environment=json.loads(source.read('source_inventory.json'))['environment']
    runner=archived_reproducer(contents,'ANALYSIS_REPRODUCER')
    contents.update({'analysis.json':canonical(payload).encode(),'reproduce.py':runner,
        'HOW_TO_REPRODUCE.md':b'# Trusted analysis archive\n\nInspect first with `python -m causalbench.packages verify FILE.zip`. Extract trusted sources to a new directory. Run `python reproduce.py` with the recorded Python version/OS. Expected: REPRODUCED. Imported source is not automatically executed.\n'})
    inventory={'format_version':1,'kind':'analysis','environment':environment,'files':{n:hashlib.sha256(v).hexdigest() for n,v in contents.items()},'analysis_digest':digest(payload)}
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in contents.items():z.writestr(name,data)
        z.writestr('inventory.json',canonical(inventory))
        z.writestr('inventory.sha256',digest(inventory))
    return out.getvalue()


def archived_reproducer(contents,name):
    """Read the archived runner as an AST string literal, without importing archived code."""
    source=contents.get('causalbench/packages.py')
    if source is None:
        raise ValueError('Archived package runner source is missing')
    try:
        for item in ast.parse(source.decode('utf-8-sig')).body:
            if isinstance(item,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in item.targets):
                if isinstance(item.value,ast.Constant) and isinstance(item.value.value,str):
                    return item.value.value.encode()
    except (SyntaxError,UnicodeError) as exc:
        raise ValueError('Archived runner source is invalid') from exc
    raise ValueError('Archived source has no compatible reproduction runner')


def inspect(data):
    if not isinstance(data,bytes) or len(data)>16000000:
        raise ValueError('Package must be <=16 MB')
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            info=z.infolist()
            names=[i.filename for i in info]
            if len(info)>100 or len(set(names))!=len(names) or sum(i.file_size for i in info)>24000000:
                raise ValueError('Package entry/size limit exceeded')
            for item in info:
                p=PurePosixPath(item.filename)
                if p.is_absolute() or '..' in p.parts or '\\' in item.filename or ':' in item.filename or item.is_dir():
                    raise ValueError('Unsafe archive member')
            inventory=json.loads(z.read('inventory.json'))
            if inventory.get('format_version')!=1 or digest(inventory)!=z.read('inventory.sha256').decode():
                raise ValueError('Package inventory digest mismatch')
            expected=inventory['files']
            if set(names)!=set(expected)|{'inventory.json','inventory.sha256'}:
                raise ValueError('Package missing/extra files')
            for name,expected_digest in expected.items():
                if hashlib.sha256(z.read(name)).hexdigest()!=expected_digest:
                    raise ValueError('Modified package member: '+name)
            if inventory.get('kind')=='analysis':
                payload=json.loads(z.read('analysis.json'))
                if not isinstance(payload,dict) or payload.get('kind') not in ('batch','frontier','minimization','closed-loop','regression-check') or digest(payload)!=inventory['analysis_digest']:
                    raise ValueError('Analysis digest mismatch')
                return {'valid':True,'kind':'analysis','environment':inventory['environment'],'files':len(expected),'analysis':payload,
                    'scope':'Archived analysis inspected without executing source.'}
            bundle=json.loads(z.read('evidence.json'))
            if not verify(bundle) or inventory['evidence_digest']!=bundle['manifest_digest'] or json.loads(z.read('trace.json'))!=bundle['manifest']['trace']:
                raise ValueError('Package evidence/trace mismatch')
            return {'valid':True,'environment':inventory['environment'],'files':len(expected),'bundle':bundle,
                'scope':'Archive consistency verified. Source is not executed or authenticated.'}
    except (zipfile.BadZipFile,KeyError,TypeError,json.JSONDecodeError,UnicodeError) as exc:
        raise ValueError('Invalid reproducibility package') from exc


def archived_sources(data):
    """Retain imported sources in the database, never install them in the executable registry."""
    checked=inspect(data)
    with zipfile.ZipFile(io.BytesIO(data)) as source:
        contents={n:source.read(n) for n in source.namelist() if n.startswith(('causalbench/','controllers/'))}
    inventory={'format_version':1,'environment':checked['environment'],
        'files':{n:hashlib.sha256(v).hexdigest() for n,v in contents.items()}}
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for name,content in contents.items():z.writestr(name,content)
        z.writestr('source_inventory.json',canonical(inventory))
    return digest(inventory),out.getvalue()


def main():
    parser=argparse.ArgumentParser(description='Inspect a reproducibility package without running its source')
    parser.add_argument('command',choices=['verify'])
    parser.add_argument('package',type=Path)
    args=parser.parse_args()
    try:
        result=inspect(args.package.read_bytes())
        print(canonical({k:v for k,v in result.items() if k!='bundle'}))
    except (ValueError,OSError) as exc:
        print(str(exc),file=sys.stderr)
        raise SystemExit(1)


if __name__=='__main__':
    main()
