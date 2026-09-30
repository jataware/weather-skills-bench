"""Compare explicitly linked model additions without altering recorded studies."""
from copy import deepcopy


MODEL_OR_BATCH_KEYS={'models','providers','provider_price_caps','billing_prices','endpoint_parameters',
                    'model_json_mode','model_transport_note','preflight_recheck_report','model_metadata','study_label','study_note','max_cost_usd','output_stem','extends_study','preflight_report'}


def comparison_views(studies):
    by_id={s['study_id']:s for s in studies}
    groups={}
    for extension in studies:
        parent=extension['config'].get('extends_study')
        if parent in by_id:groups.setdefault(parent,[]).append(extension)
    result=[]
    for parent,extensions in groups.items():
        base=by_id[parent];parts=[base,*extensions]
        protocol=lambda s:{k:v for k,v in s['config'].items() if k not in MODEL_OR_BATCH_KEYS}
        if any(protocol(p)!=protocol(base) or p['catalog_commit']!=base['catalog_commit'] or p.get('catalog_overlay_sha256')!=base.get('catalog_overlay_sha256') for p in extensions):
            raise ValueError('Linked model extension changes the scientific protocol or task budgets')
        models=[m for p in parts for m in p['config']['models']]
        if len(set(models))!=len(models):
            raise ValueError('Model additions must not replace or repeat an existing model')
        ids=[r['run_id'] for p in parts for r in p['runs']]
        if len(set(ids))!=len(ids):raise ValueError('Duplicate run in model comparison')
        view=deepcopy(base)
        view.update(study_id='comparison-'+parent,component_studies=[p['study_id'] for p in parts],
                    planned_runs=sum(p['planned_runs'] for p in parts),
                    runs=[{**deepcopy(r),'source_study_id':p['study_id']} for p in parts for r in p['runs']],
                    finished_at=max(p['finished_at'] for p in parts) if all(p.get('finished_at') for p in parts) else None,
                    resume_note='Combined comparison of separately recorded batches with identical tasks, prompts, per-attempt limits and scoring. Additional models were selected after the original panel; this is an exploratory expansion. Individual batches remain available in the experiment selector.')
        view['config']['models']=models
        view['config']['study_label']=(f'Heat outlook · {len(models)} models · Astra excluded' if base['config'].get('protocol_version')=='cached-heat-v4' else f'Real forecasts · {len(models)} models')
        view['config']['max_cost_usd']=sum(p['config']['max_cost_usd'] for p in parts)
        for key in ('providers','provider_price_caps','billing_prices','endpoint_parameters','model_json_mode'):
            view['config'][key]={k:v for p in parts for k,v in p['config'].get(key,{}).items()}
        view['config']['model_transport_note']=' '.join(dict.fromkeys(p['config']['model_transport_note'] for p in parts if p['config'].get('model_transport_note')))
        view['ledger']={'spent':sum(p['ledger']['spent'] for p in parts),
                        'budget_reserve_usd':sum(p['ledger'].get('budget_reserve_usd',0) for p in parts),
                        'uncertain_cost':any(p['ledger'].get('uncertain_cost',False) for p in parts)}
        active=next((p for p in reversed(parts) if p.get('health',{}).get('state')=='running'),None)
        view['health']=deepcopy((active or parts[-1]).get('health',{}))
        result.append(view)
    return result


def repair_views(studies):
    """One fixed retry per provider-failed cell, never select a best answer."""
    by_id={s['study_id']:s for s in studies};views=[]
    for retry in studies:
        parent=retry['config'].get('comparison_parent')
        if parent not in by_id:continue
        base=by_id[parent];old={r['run_id']:r for r in base['runs']}
        selected=set(retry['config']['retry_attempts'])
        if selected!={rid for rid,r in old.items() if r['status']=='api_error'}:
            raise ValueError('Repair view must retain every original task outcome')
        replacements={}
        for r in retry['runs']:
            rid=r['retry_of']['run_id']
            if rid not in selected or rid in replacements:raise ValueError('Invalid or repeated repair attempt')
            if any(r[k]!=old[rid][k] for k in ('model','case_id','arm','rep')):raise ValueError('Repair cell mismatch')
            replacements[rid]=r
        view=deepcopy(base)
        view.update(study_id='repaired-'+retry['study_id'],
                    latest_activity_at=retry.get('started_at',base.get('started_at')),
                    prior_provider_attempts=[deepcopy(old[rid]) for rid in sorted(selected)],
                    runs=[deepcopy(replacements[r['run_id']] if r['run_id'] in replacements else r) for r in base['runs'] if r['run_id'] not in selected or r['run_id'] in replacements],
                    finished_at=retry.get('finished_at'),health=deepcopy(retry.get('health',{})),
                    repair_progress={'recorded':len(retry['runs']),'planned':len(selected)},
                    resume_note='Provider-failed cells received one new isolated attempt with revised transport settings. Original passes and task failures are unchanged. This is a post-hoc recovery view, not a uniform-protocol rerun. Original provider attempts remain linked; total spend includes both attempts.')
        view['config']['study_label']=retry['config'].get('comparison_label','Real forecasts · provider recovery')
        if retry['config'].get('model_transport_note'):
            view['config']['model_transport_note']=retry['config']['model_transport_note']
        view['config']['transport_retry_config']=deepcopy(retry['config'])
        view['ledger']={'spent':base['ledger']['spent']+retry['ledger']['spent'],
                        'budget_reserve_usd':base['ledger'].get('budget_reserve_usd',0)+retry['ledger'].get('budget_reserve_usd',0),
                        'uncertain_cost':base['ledger'].get('uncertain_cost',False) or retry['ledger'].get('uncertain_cost',False)}
        views.append(view)
    return views


def queued_comparison_parts(studies,root):
    """Expose registered, queued model additions as pending cells, never outcomes."""
    import json
    by_id={s['study_id']:s for s in studies}
    recorded={s['config'].get('output_stem') for s in studies}
    parts=[]
    for path in sorted((root/'results').glob('*-queue.json')):
        state=json.loads(path.read_text())
        if state.get('state') not in ('waiting','starting') or not state.get('config'):continue
        config_path=(root/state['config']).resolve()
        if not config_path.is_relative_to((root/'configs').resolve()):continue
        config=json.loads(config_path.read_text())
        parent=by_id.get(config.get('extends_study'))
        if not parent or config.get('output_stem') in recorded:continue
        part=deepcopy(parent)
        part.update(study_id='queued-'+config['output_stem'],kind='queued',config=config,
                    runs=[],finished_at=None,ledger={'spent':0.,'uncertain_cost':False},
                    planned_runs=len(config['models'])*len(config['cases'])*len(config['arms'])*config['repetitions'],
                    health={'state':'waiting'},resume_note='Registered model extension queued after the parent batch. No attempts have run yet.')
        parts.append(part)
    return parts
