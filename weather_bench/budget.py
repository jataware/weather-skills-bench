"""Pre-request spend admission for opt-in, dollar-budgeted experiments.

The bound is deliberately conservative, not a provider billing guarantee. Actual
charges and reservations are kept separate; neither is inferred from wall time.
"""
import math


def validate_budget(config):
    if config.get('max_run_cost_usd') is None:
        return
    for key in ('max_run_cost_usd', 'max_cost_usd'):
        value=config[key]
        if not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
            raise ValueError(f'{key} must be finite and positive')
    for model in config['models']:
        prices=config.get('billing_prices',{}).get(model,{})
        caps=config.get('provider_price_caps',{}).get(model,{})
        for key in ('prompt','completion'):
            price=prices.get(key);cap=caps.get(key)
            if (price is None or cap is None or not math.isfinite(price) or not math.isfinite(cap)
                    or price<0 or cap<0 or price+1e-15<cap/1_000_000):
                raise ValueError(f'{model}: reservation prices must cover provider price ceilings')


def request_cost_bound(config,model,body):
    prices=config['billing_prices'][model]
    # Bytes overestimate ordinary BPE tokens. Allow additional chat framing,
    # doubled rates for fees/cache writes, and a one-cent fixed margin.
    prompt_bound=sum(len(m['content'].encode('utf-8'))+64 for m in body['messages'])+4096
    return 2*(prompt_bound*prices['prompt']+body['max_tokens']*prices['completion'])+.01


def run_reserve(ledger,run_id):
    return sum(r['reserve_usd'] for r in ledger.get('unconfirmed_requests',[]) if r['run_id']==run_id)


def admit_request(config,model,body,usage,ledger,run_id):
    """Return admission evidence, or None for the unchanged legacy protocol."""
    if config.get('max_run_cost_usd') is None:
        return None
    bound=request_cost_bound(config,model,body)
    reserved=run_reserve(ledger,run_id)
    run_remaining=config['max_run_cost_usd']-usage['known_cost_usd']-reserved
    study_remaining=config['max_cost_usd']-ledger['spent']-ledger.get('budget_reserve_usd',0)
    status=('cost_unknown' if ledger.get('uncertain_cost') else
            'run_cost_budget' if bound>run_remaining else
            'study_budget' if bound>study_remaining else None)
    return {'status':status,'next_request_bound_usd':bound,
            'run_remaining_usd':run_remaining,'study_remaining_usd':study_remaining,
            'unconfirmed_reserve_usd':reserved}
