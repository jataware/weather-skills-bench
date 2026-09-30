import copy
import json
import pytest
from weather_bench.catalog import ROOT
from weather_bench.comparison import comparison_views,MODEL_OR_BATCH_KEYS
from weather_bench.health import output_stem


def study(name,model):
    return {'study_id':name,'config':{'models':[model],'cases':['a'],'arms':['skills_only','python'],'max_calls':40,'max_cost_usd':1,'providers':{model:['route']}},
            'planned_runs':2,'runs':[{'run_id':name+'1','model':model}],'catalog_commit':'pinned',
            'finished_at':None,'ledger':{'spent':.1},'health':{'state':'running'}}


def test_comparison_keeps_sources_and_sums_once():
    base=study('base','m1');extension=study('new','m2');extension['config']['extends_study']='base'
    original=copy.deepcopy([base,extension]);view=comparison_views([base,extension])[0]
    assert [base,extension]==original
    assert view['planned_runs']==4 and len(view['runs'])==2
    assert view['config']['models']==['m1','m2'] and view['ledger']['spent']==.2
    assert view['component_studies']==['base','new'] and view['runs'][1]['source_study_id']=='new'
    assert view['finished_at'] is None
    base['finished_at']='2026-09-29';extension['finished_at']='2026-09-30'
    assert comparison_views([base,extension])[0]['finished_at']=='2026-09-30'


@pytest.mark.parametrize('change',['budget','cases','catalog','model','run'])
def test_incompatible_or_duplicate_extension_rejected(change):
    base=study('base','m1');extension=study('new','m2');extension['config']['extends_study']='base'
    if change=='budget':extension['config']['max_calls']=41
    if change=='cases':extension['config']['cases']=['different']
    if change=='catalog':extension['catalog_commit']='different'
    if change=='model':extension['config']['models']=['m1']
    if change=='run':extension['runs'][0]['run_id']='base1'
    with pytest.raises(ValueError):comparison_views([base,extension])


def test_registered_ministral_settings_match_recovery():
    base=json.loads((ROOT/'configs/end-to-end-recovery-v2.json').read_text())
    new=json.loads((ROOT/'configs/end-to-end-ministral-v2.json').read_text())
    assert {k:v for k,v in base.items() if k not in MODEL_OR_BATCH_KEYS}=={k:v for k,v in new.items() if k not in MODEL_OR_BATCH_KEYS}
    assert len(new['models'])*len(new['cases'])*len(new['arms'])*new['repetitions']==6
    assert output_stem(new)=='ministral' and output_stem(base)=='e2e'
    assert new['models']==['mistralai/ministral-3b-2512']
    with pytest.raises(ValueError):output_stem({'output_stem':'../e2e'})


def test_small_extension_preserves_transport_disclosure_and_exclusion():
    base=study('base','m1');extension=study('new','m2')
    for s in (base,extension):
        s['config'].update(protocol_version='cached-heat-v4',exclusion_note='Astra helped author this benchmark.',json_mode=True)
        s['catalog_overlay_sha256']='same-patch'
    extension['config'].update(extends_study='base',model_json_mode={'m2':False},model_transport_note='m2 lacks JSON enforcement.')
    view=comparison_views([base,extension])[0]
    assert view['config']['model_json_mode']=={'m2':False}
    assert view['config']['model_transport_note']=='m2 lacks JSON enforcement.'
    assert 'Astra' in view['config']['exclusion_note']
    extension['catalog_overlay_sha256']='different-patch'
    with pytest.raises(ValueError):comparison_views([base,extension])


def test_small_panel_keeps_task_and_budgets():
    base=json.loads((ROOT/'configs/refined-heat-panel-v4.json').read_text())
    small=json.loads((ROOT/'configs/refined-heat-small-v4.json').read_text())
    assert {k:v for k,v in base.items() if k not in MODEL_OR_BATCH_KEYS}=={k:v for k,v in small.items() if k not in MODEL_OR_BATCH_KEYS}
    assert not set(base['models'])&set(small['models'])
    assert 'openai/gpt-6-astra' not in base['models']+small['models']


def test_queued_extension_shows_pending_without_inventing_runs(tmp_path):
    from weather_bench.comparison import queued_comparison_parts
    (tmp_path/'configs').mkdir();(tmp_path/'results').mkdir()
    base=study('base','m1');config=copy.deepcopy(base['config'])
    config.update(models=['m2'],extends_study='base',output_stem='small',repetitions=1)
    (tmp_path/'configs/small.json').write_text(json.dumps(config))
    (tmp_path/'results/small-queue.json').write_text(json.dumps({'state':'waiting','config':'configs/small.json'}))
    parts=queued_comparison_parts([base],tmp_path)
    assert len(parts)==1 and parts[0]['runs']==[] and parts[0]['planned_runs']==2
    assert parts[0]['ledger']['spent']==0 and parts[0]['health']['state']=='waiting'
    recorded=copy.deepcopy(parts[0]);recorded['study_id']='actual'
    assert queued_comparison_parts([base,recorded],tmp_path)==[]
