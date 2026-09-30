"""Independent oracle and actual CLI regression checks for the refined heat task."""
import hashlib,json,sys,time,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from weather_bench.refined import case,source_cache,sandbox,verify_profile,CATALOG
from weather_bench.e2e_validation import fields,collect_figure
from weather_bench.grading import grade,workflow
from weather_bench.catalog import tree_hash


def validate():
    overlay='--overlay' in sys.argv;tag='rolling-fix' if overlay else 'heat-v3'
    c=case();pin=verify_profile(overlay=overlay);inputs,source=source_cache();folder=ROOT/'.build/refined-validation'/str(time.time_ns())
    image_ids={kind:subprocess.check_output(['docker','image','inspect','weather-bench-'+kind+':'+tag,'--format','{{.Id}}'],text=True).strip() for kind in ('python','skills')}
    cache_key=hashlib.sha256(json.dumps([pin,source,c.public(),c.recipe,c.expected,image_ids,tree_hash(ROOT/'references/e2e'),hashlib.sha256(Path(__file__).read_bytes()).hexdigest()],sort_keys=True).encode()).hexdigest()
    saved=ROOT/('results/refined-reference-v4.json' if overlay else 'results/refined-reference.json')
    if saved.exists() and '--force' not in sys.argv:
        previous=json.loads(saved.read_text())
        if previous['runs'][0].get('cache_key')==cache_key:
            print(json.dumps({'passed':True,'validation_cache_hit':True,'cache_key':cache_key}),flush=True);return
    events=[];started=time.monotonic()
    with sandbox(inputs,folder/'skills',skills=True,catalog=CATALOG,image_tag=tag) as s:
        for node in c.recipe:
            args=[part for name in node['inputs'] for part in ('--input','/work/'+name+'.zarr')]
            filename=node['output'] if node['output'].endswith('.png') else node['output']+'.zarr'
            args+=['--output','/work/'+filename,*node['args']]
            event={'action':'skill','skill':node['skill'],'args':args}
            event.update(s.execute(event,timeout=180));events.append(event)
            print(node['id'],event['returncode'],round(event['seconds'],3),flush=True)
            if event['returncode']:raise RuntimeError(event['stderr'])
        result=s.submit_artifacts(fields(c));assert not result['returncode'],result
        answer=s.answer();score=grade(c.expected,answer,**c.public()['tolerance']);assert score['passed'],score
        figure=collect_figure(s,ROOT/'docs/artifacts/reference'/f'{c.id}.png');assert figure['passed'],figure
        repeated=s.execute({k:events[1][k] for k in ('action','skill','args')})
        assert repeated.get('cache_hit') and not repeated['returncode'],repeated
        conversion=s.execute({'action':'skill','skill':'unit-convert','args':['-i','/work/forecast.zarr','-o','/work/kelvin.zarr','--to-units','K']})
        assert not conversion['returncode'],conversion
        conversion_values=s.execute({'action':'python','code':'''import xarray as xr,numpy as np
raw=xr.open_zarr('/inputs/archive.zarr',chunks=None).t2m.sel(latitude=slice(5,-5),longitude=slice(34,42))
converted=xr.open_zarr('/work/kelvin.zarr',chunks=None).t2m
assert converted.attrs['units'] in ('K','kelvin')
np.testing.assert_allclose(converted.values,raw.values,atol=1e-4,rtol=1e-6)
'''})
        assert not conversion_values['returncode'],conversion_values
        images=s.image_ids
    with sandbox(inputs,folder/'python',catalog=CATALOG,image_tag=tag) as p:
        code=(ROOT/'references/e2e/python_solution.py').read_text().replace('xr.open_zarr(source(date,product),','xr.open_zarr("/inputs/archive.zarr",')
        event=p.execute({'action':'python','code':'CASE_ID="e2e-kenya-heat"\n'+code},timeout=180)
        assert not event['returncode'],event
        python_answer=p.answer();python_score=grade(c.expected,python_answer,**c.public()['tolerance']);assert python_score['passed'],python_score
        python_png=collect_figure(p,ROOT/'docs/artifacts/reference'/f'{c.id}-python.png');assert python_png['passed'],python_png
    # Actual clipping regression: choose an extent crossing source chunk boundaries.
    with sandbox(inputs,folder/'regression',skills=True,catalog=CATALOG,image_tag=tag) as r:
        make=r.execute({'action':'python','code':'''import xarray as xr
x=xr.open_zarr('/inputs/archive.zarr',chunks='auto')[['t2m']]
x.to_zarr('/work/raw.zarr',mode='w',consolidated=True)
'''},timeout=180);assert not make['returncode'],make
        clipping=r.execute({'action':'skill','skill':'clip-region','args':['-i','/work/raw.zarr','-o','/work/clipped.zarr','--bbox','5/34/-5/42']},timeout=180)
        assert not clipping['returncode'],clipping
        check=r.execute({'action':'python','code':'''import xarray as xr, numpy as np
raw=xr.open_zarr('/inputs/archive.zarr',chunks=None).t2m.sel(latitude=slice(5,-5),longitude=slice(34,42))
actual=xr.open_zarr('/work/clipped.zarr',chunks=None).t2m
np.testing.assert_allclose(actual.values,raw.values,rtol=1e-6,atol=1e-4)
print('Clipped values agree with independent raw-array selection')
'''});assert not check['returncode'],check
    report={'case_id':c.id,'kind':'reference','answer':answer,'expected':c.expected,'correctness':score,'scientific_correctness':score,
        'workflow':workflow(c,events),'oracle_verified':True,'figure':figure,'events':events,'image_ids':images,
        'input_sha256':{'archive':source['store_sha256']},'source_versions':source,'wall_seconds':time.monotonic()-started,
        'python_reference':{'answer':python_answer,'correctness':python_score,'figure':python_png,'event':event},
        'regressions':{'weighted_celsius':True,'explicit_kelvin_conversion':conversion,'clipping':clipping,'repeat_skill_cache':repeated},
        'cache_key':cache_key}
    saved.write_text(json.dumps({**pin,'runs':[report]},indent=2)+'\n')
    (ROOT/'cases'/f'{c.id}.json').write_text(json.dumps(c.public(),indent=2)+'\n')
    print(json.dumps({'passed':True,'seconds':report['wall_seconds'],'cache_repeat_seconds':repeated['seconds'],'original_execution_seconds':repeated['cached_execution_seconds']}),flush=True)

if __name__=='__main__':validate()
