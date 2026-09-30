"""Opt-in routing and bounded retry rules for separately versioned experiments."""
from datetime import datetime,timezone
from email.utils import parsedate_to_datetime
import math


def json_mode_enabled(config,model):
    return config.get("model_json_mode",{}).get(model,config.get("json_mode",False))


def provider_preferences(config,model):
    fallback=bool(config.get('provider_allow_fallbacks',False))
    result={'allow_fallbacks':fallback,'require_parameters':True}
    routes=config.get('providers',{}).get(model)
    if routes:
        result['only']=list(routes)
        if fallback:result['order']=list(routes)
    cap=config.get('provider_price_caps',{}).get(model)
    if cap:result['max_price']=dict(cap)
    return result


def retry_wait(policy,code,error,retry_after,retries,consecutive,remaining,now=None):
    """Return a wait or None. Authentication, validation and unknown charges never
    become invisible retries. A larger Retry-After is honored by declining to
    retry if it cannot fit the configured wait/deadline budget.
    """
    if retries>=policy.get('max_retries_per_run',0) or consecutive>=policy.get('max_consecutive_retries',0):return None
    if code not in policy.get('http_statuses',[429,500,502,503,504])+policy.get('transport_errors',[]):return None
    error=error if isinstance(error,dict) else {}
    meta=error.get('metadata') or {}
    if isinstance(meta,dict) and (meta.get('error_type') in ('invalid_request','authentication','permission_denied','payment_required')
        or meta.get('provider_error_code')=='invalid_request_error'):return None
    delay=policy.get('base_delay_seconds',2)*2**consecutive
    if retry_after:
        try:hint=float(retry_after)
        except (ValueError,TypeError):
            try:hint=(parsedate_to_datetime(retry_after)-(now or datetime.now(timezone.utc))).total_seconds()
            except (ValueError,TypeError,OverflowError):return None
        if not math.isfinite(hint):return None
        delay=max(delay,hint)
    if delay>policy.get('max_delay_seconds',30) or delay+1>=remaining:return None
    return max(0.,delay)


def task_payload(case,config):
    result=case.public()
    clarification=config.get('task_clarifications',{}).get(case.id)
    if clarification:result={**result,'study_clarification':clarification}
    return result
