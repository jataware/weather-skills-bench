"""Explicit, single replacement attempts for infrastructure-failed cells only."""
import json


SCIENTIFIC_KEYS=('cases','arms','repetitions','seed','temperature','reasoning_effort','max_calls',
                 'max_executions','max_total_tokens','max_output_tokens','max_context_bytes',
                 'task_timeout_seconds','execution_timeout_seconds','allow_batch','json_mode','task_clarifications',
                 'skill_policy','max_run_cost_usd','experiment_version')


def validate_retry_manifest(config,root,pin):
    from .report import effective_status
    sources={name:json.loads((root/'results/studies'/f'{name}.json').read_text()) for name in config['retry_sources']}
    def provider_failure(s,r):
        native=next((q.get('native_finish_reason') for q in reversed(r.get('requests',[])) if q.get('native_finish_reason')),None)
        return effective_status(r,s['config'],native)=='api_error'
    expected={r['run_id']:(s,r) for s in sources.values() for r in s['runs'] if provider_failure(s,r)}
    if set(config['retry_attempts'])!=set(expected) or len(config['retry_attempts'])!=len(expected):
        raise ValueError('Retry batch must include every provider error exactly once; completed task outcomes are ineligible')
    result={}
    for rid in config['retry_attempts']:
        source,run=expected[rid]
        if source['catalog_tree_sha256']!=pin['catalog_tree_sha256']:raise ValueError('Catalog changed')
        if source.get('catalog_overlay_sha256')!=pin.get('catalog_overlay_sha256'):raise ValueError('Catalog overlay changed')
        for key in SCIENTIFIC_KEYS:
            # An extension may contain only its own model, but shares all cases.
            if source['config'].get(key)!=config.get(key):raise ValueError('Scientific settings changed: '+key)
        key=(run['case_id'],run['model'],run['arm'],run['rep'])
        if key in result:raise ValueError('Duplicate retry cell')
        result[key]={'study_id':source['study_id'],'run_id':rid}
    return result
