"""Regression for the additional rolling-temperature defect, separate from v3 runs."""
import json,subprocess,sys,tempfile,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from weather_bench.refined import CATALOG,source_cache,verify_profile
from weather_bench.sandbox import Sandbox
from weather_bench.e2e_sandbox import E2E_ENABLED
verify_profile()
context=ROOT/'.build/docker-rolling-followup';relative=Path('skills/weather-skills/aggregate-temporal/scripts/aggregate.py')
for relative in (relative,Path('skills/weather-skills/summarize-dim/scripts/summarize_dim.py')):
    (context/relative).parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(CATALOG/relative,context/relative)
subprocess.run(['git','apply','--directory',str(context.relative_to(ROOT)),str(ROOT/'patches/rolling-temperature-followup.patch')],cwd=ROOT,check=True)
(context/'Dockerfile').write_text('FROM weather-bench-skills:heat-v3\nCOPY skills /catalog/skills\n')
subprocess.run(['docker','build','-t','weather-bench-skills:rolling-fix',str(context)],check=True)
subprocess.run(['docker','tag','weather-bench-python:heat-v3','weather-bench-python:rolling-fix'],check=True)
inputs,_=source_cache();work=Path(tempfile.mkdtemp(dir=ROOT/'.build'))
events=[]
with Sandbox(inputs,work,skills=True,skills_only=True,catalog=CATALOG,runtime={'tag':'rolling-fix','enabled':E2E_ENABLED,'memory':'2g'}) as s:
    for skill,args in [
        ('kenya-forecast-fetch',['--source-store','/inputs/archive.zarr','--date','2026-09-27','--dataset','daily_vars','-v','t2m','--bbox','5/34/-5/42','-o','/work/t.zarr']),
        ('summarize-dim',['-i','/work/t.zarr','-o','/work/regional.zarr','--dim','latitude','--dim','longitude','--method','mean','--lat-weighted']),
        ('aggregate-temporal',['-i','/work/regional.zarr','-o','/work/rolling.zarr','--window','7','--align','right','--method','max']),
        ('select',['-i','/work/rolling.zarr','-o','/work/week1.zarr','--dim','step','--index','0']),
        ('summarize-dim',['-i','/work/week1.zarr','-o','/work/median.zarr','--dim','number','--method','median'])]:
        e={'action':'skill','skill':skill,'args':args};e.update(s.execute(e,timeout=120));events.append(e)
        assert not e['returncode'],e
    code='''import xarray as xr,numpy as np
raw=xr.open_zarr('/inputs/archive.zarr',chunks=None).t2m.sel(latitude=slice(5,-5),longitude=slice(34,42)).transpose('number','step','latitude','longitude')
a=raw.values.astype(float)-273.15
regional=np.average(a.mean(-1),axis=-1,weights=np.cos(np.deg2rad(raw.latitude.values)))
expected=np.lib.stride_tricks.sliding_window_view(regional,7,axis=1).max(-1)
actual=xr.open_zarr('/work/rolling.zarr',chunks=None).t2m.transpose('number','step')
assert actual.attrs['units'] in ('degree_Celsius','°C')
np.testing.assert_allclose(actual.values,expected,rtol=1e-6,atol=1e-4)
median=xr.open_zarr('/work/median.zarr',chunks=None).t2m
np.testing.assert_allclose(median.values.squeeze(),np.median(expected[:,0]),rtol=1e-6,atol=1e-4)
print('Rolling maxima and full-axis member median match independent raw-array calculations')
'''
    p=subprocess.run(['docker','exec',s.containers['skills'],'python','-c',code],capture_output=True,text=True);assert not p.returncode,p.stderr
    result={'passed':True,'events':events,'image_ids':s.image_ids,'oracle_check':p.stdout.strip(),'applied_to_active_cohort':False}
(ROOT/'results/rolling-followup-validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='events'}))
