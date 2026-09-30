"""Versioned, offline heat task using immutable raw archive bytes."""
import copy
import fcntl
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import zipfile
from .catalog import ROOT, DEFAULT_CATALOG, lock, tree_hash

CASE_ID = 'e2e-kenya-heat-cached-v3'
CATALOG = ROOT.parent / 'weather-skills-catalog-refined'
TAG = 'heat-v3'


def source_cache():
    """Share raw inputs only. Verify every object on every mount; fail closed."""
    entry = json.loads((ROOT/'fixtures/real-sources.json').read_text())['temperature']
    digest = hashlib.sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest()
    root = ROOT/'.build/source-cache'/digest
    root.parent.mkdir(parents=True, exist_ok=True)
    with (root.parent/(digest+'.lock')).open('a') as guard:
        fcntl.flock(guard, fcntl.LOCK_EX)
        if not root.exists():
            staging = Path(tempfile.mkdtemp(dir=root.parent))
            try:
                dest = staging/'archive.zarr'; dest.mkdir()
                with zipfile.ZipFile(ROOT/'fixtures/real-source-temperature.zip') as archive:
                    expected = {o['path'] for o in entry['objects']}
                    # Frozen archives contain the object paths relative to their store.
                    for item in archive.infolist():
                        if item.is_dir(): continue
                        name = item.filename
                        if name not in expected or Path(name).is_absolute() or '..' in Path(name).parts:
                            raise ValueError('Unexpected raw archive member: '+name)
                        out = dest/name; out.parent.mkdir(parents=True,exist_ok=True)
                        out.write_bytes(archive.read(item))
                verify_source(dest,entry)
                staging.rename(root)
            finally:
                if staging.exists(): shutil.rmtree(staging)
        verify_source(root/'archive.zarr',entry)
    return root, {'mode':'immutable_local_archive','manifest_sha256':digest,'source_url':entry['url'],
                  'objects':len(entry['objects']),'version_match':True,'store_sha256':tree_hash(root/'archive.zarr')}


def verify_source(path,entry):
    files={str(p.relative_to(path)) for p in path.rglob('*') if p.is_file()}
    if files!={o['path'] for o in entry['objects']}:raise ValueError('Source object set changed')
    for obj in entry['objects']:
        p=path/obj['path']
        if p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest()!=obj['sha256']:
            raise ValueError('Source hash mismatch: '+obj['path'])


def case():
    from .e2e_cases import e2e_cases
    from .cases import Case
    old=next(c for c in e2e_cases() if c.id=='e2e-kenya-heat')
    class CachedCase(Case):
        def public(self):
            public=copy.deepcopy(old.public())
            public.update(id=self.id,title=self.title,brief=self.brief,suite=self.suite,
                          inputs=['archive.zarr'],fixture_kind='real archived forecast; verified local raw-data cache')
            public['source_notes']=[self.expected['source_url'],
                'The local store is a byte-for-byte frozen raw archive, not a standardized skill output. Network access is disabled.']
            return public
    c=CachedCase(**copy.deepcopy(old.__dict__))
    c.id=CASE_ID; c.suite='cached-forecast-v3'; c.title='Kenya heat outlook · frozen real forecast'
    c.brief=old.brief.replace('Start from the public Kenya forecast archive; no weather data is preloaded.',
        'The raw ECMWF archive is cached read-only at /inputs/archive.zarr. Inspect and process this local store; no network access is available. It is the unmodified daily_vars product for 2026-09-27. If using kenya-forecast-fetch, --source-store /inputs/archive.zarr selects this local source. Cite the original archive URL, not the cache path.')
    c.brief+=' Week 1 covers lead days 1–7 inclusive (2026-09-28 through 2026-10-04); week 2 covers days 8–14 inclusive (2026-10-05 through 2026-10-11). Compute the spatial mean separately for each member and day, then each member’s weekly maximum, then ensemble statistics. Include uncertainty in the figure. This describes a model forecast, not a verified outcome or heat-warning threshold.'
    c.recipe[0]['args'] += ['--source-store','/inputs/archive.zarr']
    return c


def verify_profile(overlay=False):
    expected=json.loads((ROOT/'catalog.refined.lock.json').read_text())
    if lock(CATALOG)!=expected:raise ValueError('Refined catalog differs from its pinned lock')
    if overlay:
        expected['catalog_overlay_sha256']=hashlib.sha256((ROOT/'patches/rolling-temperature-followup.patch').read_bytes()).hexdigest()
    return expected


def build():
    verify_profile()
    context=ROOT/'.build/docker-refined'; context.mkdir(parents=True,exist_ok=True)
    target=context/'catalog'
    if target.exists():shutil.rmtree(target)
    shutil.copytree(CATALOG/'skills',target/'skills',ignore=shutil.ignore_patterns('tests','__pycache__'))
    (context/'Dockerfile').write_text('FROM weather-bench-skills:e2e-v1\nCOPY catalog /catalog\n')
    subprocess.run(['docker','build','-t','weather-bench-skills:'+TAG,str(context)],check=True)
    subprocess.run(['docker','tag','weather-bench-python:e2e-v1','weather-bench-python:'+TAG],check=True)


def sandbox(inputs,work,image_tag=TAG,**kwargs):
    from .sandbox import Sandbox
    from .e2e_sandbox import E2E_ENABLED
    return Sandbox(inputs,work,**kwargs,runtime={'tag':image_tag,'enabled':E2E_ENABLED,'memory':'2g',
        'environment':{'PYTHONPATH':'/runtime'},'memoize_skills':True})
