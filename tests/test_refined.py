import hashlib
from pathlib import Path
import pytest
from weather_bench.execution_cache import ExecutionCache
from weather_bench.refined import case,verify_source


def test_cache_requires_unchanged_inputs_and_outputs(tmp_path):
    inputs=tmp_path/'inputs';work=tmp_path/'work';inputs.mkdir();work.mkdir()
    (inputs/'raw').write_text('original');(work/'result').write_text('computed')
    cache=ExecutionCache(inputs,work)
    action={'action':'skill','skill':'select','args':['-i','/inputs/raw','-o','/work/result','--dim','time','--index','0']}
    key=cache.key(action,'image-1');result={'returncode':0,'stdout':'done','stderr':'','seconds':2.5}
    cache.put(key,result)
    assert cache.get(key)['cache_hit']
    assert cache.get(key)['cached_execution_seconds']==2.5
    assert ExecutionCache(inputs,work).get(key) is None  # no cross-run reuse
    assert cache.get(cache.key(action,'image-2')) is None
    (inputs/'raw').write_text('changed')
    assert cache.get(cache.key(action,'image-1')) is None
    (inputs/'raw').write_text('original');(work/'result').write_text('changed by agent')
    assert cache.get(key) is None


def test_failed_missing_and_inplace_calls_are_not_cached(tmp_path):
    inputs=tmp_path/'i';work=tmp_path/'w';inputs.mkdir();work.mkdir()
    (inputs/'raw').write_text('raw')
    cache=ExecutionCache(inputs,work)
    a={'action':'skill','skill':'select','args':['-i','/inputs/raw','-o','/work/result']}
    key=cache.key(a,'image');cache.put(key,{'returncode':1,'seconds':1})
    assert cache.get(key) is None
    cache.put(key,{'returncode':0,'seconds':1})
    assert cache.get(key) is None  # missing output
    a['args']=['-i','/work/result','-o','/work/result']
    assert cache.key(a,'image') is None


def test_source_cache_rejects_corruption_or_extra_files(tmp_path):
    (tmp_path/'raw').write_bytes(b'raw')
    entry={'objects':[{'path':'raw','sha256':hashlib.sha256(b'raw').hexdigest()}]}
    verify_source(tmp_path,entry)
    (tmp_path/'raw').write_bytes(b'changed')
    with pytest.raises(ValueError,match='hash mismatch'):verify_source(tmp_path,entry)
    (tmp_path/'raw').write_bytes(b'raw');(tmp_path/'answer.json').write_text('{}')
    with pytest.raises(ValueError,match='object set'):verify_source(tmp_path,entry)


def test_refined_brief_has_explicit_cache_and_calendar_contract():
    c=case();p=c.public()
    assert c.id=='e2e-kenya-heat-cached-v3'
    assert p['inputs']==['archive.zarr']
    assert 'no weather data is preloaded' not in p['brief']
    assert '2026-09-28 through 2026-10-04' in p['brief']
    assert '--source-store' in c.recipe[0]['args']
    assert 'expected' not in p and 'recipe' not in p
