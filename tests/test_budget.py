from copy import deepcopy
import pytest
from weather_bench.budget import validate_budget,request_cost_bound,admit_request


def config():
    return {'models':['m'],'max_cost_usd':24,'max_run_cost_usd':2,
            'billing_prices':{'m':{'prompt':1e-6,'completion':2e-6}},
            'provider_price_caps':{'m':{'prompt':1,'completion':2}}}


@pytest.mark.parametrize('value',[0,-1,float('inf'),float('nan')])
def test_invalid_cap_rejected(value):
    c=config();c['max_run_cost_usd']=value
    with pytest.raises(ValueError):validate_budget(c)


def test_cap_requires_price_bounds_covering_allowed_routes():
    c=config();validate_budget(c)
    c['provider_price_caps']['m']['prompt']=3
    with pytest.raises(ValueError,match='price ceilings'):validate_budget(c)


def test_reserves_are_scoped_to_run_but_study_exposure_includes_all():
    c=config();body={'messages':[{'content':'test'}],'max_tokens':100}
    ledger={'spent':0,'budget_reserve_usd':1.99,'unconfirmed_requests':[{'run_id':'old','reserve_usd':1.99}]}
    admission=admit_request(c,'m',body,{'known_cost_usd':0},ledger,'new')
    assert admission['status'] is None and admission['run_remaining_usd']==2
    ledger['unconfirmed_requests'][0]['run_id']='new'
    assert admit_request(c,'m',body,{'known_cost_usd':0},ledger,'new')['status']=='run_cost_budget'
    ledger['uncertain_cost']=True
    assert admit_request(c,'m',body,{'known_cost_usd':0},ledger,'new')['status']=='cost_unknown'


def test_request_bound_uses_utf8_and_actual_output_limit():
    c=config();body={'messages':[{'content':'é'}],'max_tokens':100}
    assert request_cost_bound(c,'m',body)==2*((2+64+4096)*1e-6+100*2e-6)+.01
    bigger=deepcopy(body);bigger['max_tokens']=200
    assert request_cost_bound(c,'m',bigger)>request_cost_bound(c,'m',body)
