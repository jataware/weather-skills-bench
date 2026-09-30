import copy
import json
import math
from pathlib import Path
import pytest
from weather_bench.cases import cases, write_inputs
from weather_bench.catalog import ROOT, tree_hash
from weather_bench.grading import grade, workflow, flags
from weather_bench.runner import add_usage, empty_usage, parse_action, prompt, completion_error, expand_actions
from weather_bench.sandbox import Sandbox
from weather_bench.fixtures import verify_inputs, materialize


@pytest.mark.parametrize("case",cases(),ids=lambda c:c.id)
def test_oracle_accepts_exact_answer_and_rejects_wrong_answer(case):
    assert grade(case.expected,case.expected)["passed"]
    wrong=copy.deepcopy(case.expected)
    def perturb(v):
        if isinstance(v,list):
            v[0]=perturb(v[0]); return v
        return v+'wrong' if isinstance(v,str) else v+1
    key=next(k for k,v in wrong.items() if not isinstance(v,str) and k not in ("dates","latitude","longitude","lead_days"))
    wrong[key]=perturb(wrong[key])
    assert not grade(case.expected,wrong)["passed"]


@pytest.mark.parametrize("actual",[None,{}, {"x":True},{"x":float("nan")},{"x":float("inf")},{"x":"1"},{"x":[1]},{"x":1,"extra":2}])
def test_grade_rejects_bad_shapes_types_and_nonfinite(actual):
    assert not grade({"x":1},actual)["passed"]


def test_tolerance_is_explicit():
    assert grade({"x":1.0},{"x":1.0000001})["passed"]
    assert not grade({"x":1.0},{"x":1.001})["passed"]
    assert not grade({"x":1.0},{"x":10**1000})["passed"]


@pytest.mark.parametrize("text",['{"x":NaN}','{"x":Infinity}','{"x":1e400}'])
def test_nonfinite_answer_is_rejected_before_persisting_results(text):
    sandbox=Sandbox.__new__(Sandbox)
    sandbox.execute=lambda action:{"returncode":0,"stdout":text}
    assert sandbox.answer() is None


def reference_events(case):
    return [{"action":"skill","skill":n["skill"],"returncode":0,
             "args":[p for name in n["inputs"] for p in ("--input",name+".zarr")]+["--output",n["output"]+".zarr",*n["args"]]} for n in case.recipe]


def test_workflow_checks_ancestry_and_order_not_just_names():
    case=cases()[2]; events=reference_events(case)
    assert workflow(case,events)["passed"]
    disconnected=copy.deepcopy(events)
    disconnected[1]["args"][1]="unrelated.zarr"
    assert not workflow(case,disconnected)["passed"]
    assert not workflow(case,list(reversed(events)))["passed"]
    failed=copy.deepcopy(events); failed[0]["returncode"]=2
    assert not workflow(case,failed)["passed"]


def test_workflow_allows_independent_branch_reordering():
    case=cases()[5]; events=reference_events(case)
    reordered=[events[2],events[0],events[1],*events[3:]]
    assert workflow(case,reordered)["passed"]


def test_workflow_forbids_deaccumulating_rates():
    case=cases()[0]; events=reference_events(case)
    assert workflow(case,events)["passed"]
    events.append({"action":"skill","skill":"deaccumulate","args":[],"returncode":2})
    assert not workflow(case,events)["passed"]


def test_cli_flag_parser_handles_repeated_and_nargs_inputs():
    assert flags(["-i","a","b","--output=c","--dim","x"])["--input"]==["a","b"]
    assert flags(["-i","a","--input","b"])["--input"]==["a","b"]


def test_fixture_bytes_are_repeatable(tmp_path):
    case=cases()[0]
    write_inputs(case,tmp_path/"a"); write_inputs(case,tmp_path/"b")
    assert tree_hash(tmp_path/"a")==tree_hash(tmp_path/"b")
    verify_inputs(case,tmp_path/"a")
    (tmp_path/"a/rain.zarr/changed.txt").write_text("changed")
    with pytest.raises(RuntimeError): verify_inputs(case,tmp_path/"a")


def test_every_frozen_archive_matches_its_manifest():
    import hashlib
    manifest=json.loads((ROOT/"fixtures/manifest.json").read_text())
    assert set(manifest["cases"])=={c.id for c in cases()}
    for entry in manifest["cases"].values():
        assert hashlib.sha256((ROOT/"fixtures"/entry["archive"]).read_bytes()).hexdigest()==entry["sha256"]


def test_materialized_input_matches_frozen_bytes(tmp_path):
    materialize(cases()[0],tmp_path)
    verify_inputs(cases()[0],tmp_path)


def test_usage_accumulates_all_calls_without_double_counting_reasoning():
    total=empty_usage()
    add_usage(total,{"prompt_tokens":10,"completion_tokens":8,"total_tokens":18,"cost":.1,
                     "completion_tokens_details":{"reasoning_tokens":5},"prompt_tokens_details":{"cached_tokens":4}})
    add_usage(total,{"prompt_tokens":20,"completion_tokens":2,"total_tokens":22,"cost":.2})
    assert total["total_tokens"]==40
    assert total["reasoning_tokens"]==5
    assert total["known_cost_usd"]==pytest.approx(.3)
    add_usage(total,{})
    assert not total["cost_complete"]


def test_python_arm_has_no_skill_docs_or_actions():
    text=prompt("python")
    assert '"action":"skill"' not in text
    assert "aggregate-temporal" not in text
    assert '"action":"read_skill"' not in text


def test_parse_action_is_strict():
    assert parse_action('```json\n{"action":"submit"}\n```')=={"action":"submit"}
    assert parse_action('```python\nprint(1)\n```')=={"action":"python","code":"print(1)"}
    for value in ('[]','{"action":"shell"}','{"action":"python","code":4}',"do stuff"):
        with pytest.raises((ValueError,TypeError)): parse_action(value)


def test_nested_provider_error_is_not_an_agent_reasoning_failure():
    error={"code":429,"message":"rate limited"}
    assert completion_error({"choices":[{"finish_reason":"error","error":error,"message":{"content":None}}]})==error
    assert completion_error({"error":error})==error
    assert completion_error({"choices":[{"finish_reason":"stop","message":{"content":"ok"}}]}) is None


def test_batches_preserve_actions_and_condition_boundaries():
    action={"action":"batch","actions":[{"action":"python","code":"pass"},{"action":"submit"}]}
    assert expand_actions(action,"python",True)==action["actions"]
    with pytest.raises(ValueError): expand_actions(action,"python",False)
    with pytest.raises(ValueError): expand_actions(action,"python_one_shot",True)
    with pytest.raises(ValueError): expand_actions({"action":"batch","actions":[action]},"skills",True)
    with pytest.raises(ValueError): expand_actions({"action":"batch","actions":list(reversed(action["actions"]))},"skills",True)


@pytest.mark.parametrize("first_fails",[False,True])
def test_batched_agent_execution_stops_on_error(monkeypatch,tmp_path,first_fails):
    from weather_bench import runner
    case=cases()[0]; executed=[]
    class FakeSandbox:
        def __init__(self,*args,**kwargs): self.image_ids={"python":"test-image"}
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def execute(self,action,**kwargs):
            executed.append(action)
            return {"returncode":1 if first_fails else 0,"stdout":"","stderr":"","seconds":.01}
        def answer(self): return None if first_fails else case.expected
    replies=iter([{"action":"batch","actions":[{"action":"python","code":"first"},{"action":"python","code":"second"},{"action":"submit"}]},{"action":"submit"}])
    class FakeResponse:
        def raise_for_status(self): pass
        def json(self): return {"choices":[{"message":{"content":json.dumps(next(replies))},"finish_reason":"stop"}],"usage":{"prompt_tokens":10,"completion_tokens":10,"total_tokens":20,"cost":0}}
    class FakeClient:
        def post(self,*args,**kwargs):
            assert 'temperature' not in kwargs['json']
            assert kwargs['json']['reasoning']=={'effort':'low'}
            return FakeResponse()
    monkeypatch.setattr(runner,"ROOT",tmp_path)
    monkeypatch.setattr(runner,"Sandbox",FakeSandbox)
    config=json.loads((ROOT/"configs/pilot.json").read_text())
    config.update(allow_batch=True,model_metadata={"test":{'supported_parameters':['temperature','reasoning']}},endpoint_parameters={'test':['reasoning']})
    result=runner.run_one(case,"test","python",0,config,FakeClient(),{"spent":0.,"uncertain_cost":False})
    assert len(executed)==(1 if first_fails else 2)
    assert result["correctness"]["passed"]==(not first_fails)


def test_python_reference_validation_passes_every_case():
    data=json.loads((ROOT/"results/python-validation.json").read_text())
    assert len(data)==len([c for c in cases() if c.suite=='diagnostic-v2'])
    assert all(r["correctness"]["passed"] for r in data)
    real=json.loads((ROOT/'results/e2e-reference.json').read_text())['runs']
    assert len(real)==len([c for c in cases() if c.suite=='end-to-end-v1'])
    assert all(r['oracle_verified'] for r in real)


def test_dashboard_export_preserves_published_runs_without_private_traces(monkeypatch,tmp_path):
    import shutil
    from weather_bench import report
    source=next(p for p in reversed(sorted((ROOT/'results/published').glob('*.json'))) if json.loads(p.read_text()).get('runs'))
    expected=json.loads(source.read_text())
    target=tmp_path/'results/published'; target.mkdir(parents=True)
    shutil.copy(source,target/source.name)
    monkeypatch.setattr(report,'ROOT',tmp_path)
    report.export_dashboard()
    payload=json.loads((tmp_path/'docs/data.json').read_text())
    assert payload['studies'][0]['study_id']==expected['study_id']
    assert len(payload['studies'][0]['runs'])==len(expected['runs'])
    assert 'requests' not in payload['studies'][0]['runs'][0]


def test_all_ground_truth_is_verified_and_catalog_limitations_are_explicit():
    data=json.loads((ROOT/"results/reference.json").read_text())
    assert len(data["runs"])==len(cases())
    assert all(r.get('oracle_verified') or (r["correctness"]["passed"] and r["workflow"]["passed"]) for r in data["runs"])
    by_id={r['case_id']:r for r in data['runs']}
    manifest=json.loads((ROOT/'fixtures/manifest.json').read_text())
    for case in cases():
        ref=by_id[case.id]
        answer=ref['expected'] if ref.get('oracle_verified') else ref['answer']
        assert grade(case.expected,answer,**case.public()['tolerance'])['passed']
        assert by_id[case.id]['input_sha256']==manifest['cases'][case.id]['stores']


def test_public_audit_preserves_debugging_evidence_without_api_envelopes(monkeypatch,tmp_path):
    from weather_bench import report
    monkeypatch.setattr(report,'ROOT',tmp_path)
    raw=tmp_path/'results/raw/run1'; raw.mkdir(parents=True)
    (raw/'000.json').write_text(json.dumps({
        'request':{'headers':{'Authorization':'Bearer secret'},'messages':[{'role':'system','content':'Read skill guides.'}]},
        'response':{'user_id':'private-user','choices':[{'message':{'content':'{"action":"submit"}',
                    'reasoning':'PRIVATE REASONING','reasoning_details':[{'text':'PRIVATE REASONING'}]}}]}}))
    run={'run_id':'run1','requests':[{'provider':'test','seconds':2,'usage':{'prompt_tokens':20,'completion_tokens':5,'total_tokens':25,'cost':.002}}],
         'events':[{'action':'python','code':'print(42)','stdout':'42\n','stderr':'','returncode':0,'seconds':.1},
                   {'action':'api_error','message':json.dumps({'error':{'code':429,'message':'Rate limited','metadata':{'provider_name':'test','provider_error_code':'limit_requests','raw':'private provider envelope'}},'user_id':'private-user'})}]}
    audit=report.public_audit(run)
    assert audit['model_calls'][0]['usage']['total_tokens']==25
    assert audit['model_calls'][0]['response']=='{"action":"submit"}'
    assert audit['events'][0]['code']=='print(42)'
    assert audit['events'][0]['stdout']=='42\n'
    assert audit['instructions']=='Read skill guides.'
    assert '429' in audit['events'][1]['message']
    serialized=json.dumps(audit)
    for secret in ('PRIVATE REASONING','private-user','private provider envelope','Authorization'):
        assert secret not in serialized


def test_public_audit_missing_raw_response_does_not_invent_logs(monkeypatch,tmp_path):
    from weather_bench import report
    monkeypatch.setattr(report,'ROOT',tmp_path)
    result=report.public_audit({'run_id':'missing','requests':[{'usage':{'total_tokens':4}}],'events':[]})
    assert result['instructions'] is None
    assert 'response' not in result['model_calls'][0]
    assert result['model_calls'][0]['usage']['cost'] is None
    assert result['model_calls'][0]['usage']['total_tokens']==4


def test_public_log_redaction():
    from weather_bench.report import public_text
    text=public_text('Bearer abc123 API_KEY="sensitive-value" sk-or-v1-123456789abcd org_123456789 /Users/example/log.py')
    for secret in ('abc123','sensitive-value','123456789','example'):
        assert secret not in text
    assert '[REDACTED]' in text


def test_skills_only_manifest_is_serialization_not_computation():
    from weather_bench.artifacts import validate_manifest
    valid={'x':{'artifact':'/work/out.zarr','variable':'temperature'},'units':'degree_Celsius'}
    assert validate_manifest(valid)==valid
    for invalid in ({'x':1},{'x':[1,2]},{'x':{'artifact':'/inputs/a.zarr','variable':'x'}},
                    {'x':{'artifact':'/work/../a.zarr','variable':'x'}},
                    {'x':{'artifact':'/work/a.zarr','variable':'x','formula':'x*2'}}):
        with pytest.raises(ValueError):validate_manifest(invalid)


def test_skills_only_python_execution_is_blocked_in_sandbox():
    sandbox=Sandbox.__new__(Sandbox);sandbox.skills_only=True
    with pytest.raises(ValueError,match='disabled'):
        sandbox.execute({'action':'python','code':'print(42)'})


def test_skills_only_prompt_requires_guides_and_artifact_submission():
    text=prompt('skills_only',allow_batch=True)
    assert 'MUST perform every scientific computation with these skills' in text
    assert 'BEFORE invoking' in text
    assert '"artifact"' in text
    assert '"action":"python"' not in text


def test_paired_statistics_use_discordant_pairs_and_do_not_double_count_repeats():
    from weather_bench.statistics import exact_mcnemar,wilson,paired_summary
    assert exact_mcnemar(0,0)==1
    assert exact_mcnemar(5,0)==pytest.approx(.0625)
    assert exact_mcnemar(0,5)==exact_mcnemar(5,0)
    assert wilson(3,3)[0]==pytest.approx(.4385029682)
    runs=[]
    for i in range(5):
        for arm,passed in [('skills_only',True),('python',False)]:
            runs.append({'model':'a','case_id':str(i),'rep':0,'arm':arm,'status':'submitted','correctness':{'passed':passed}})
    r=paired_summary(runs)[0]
    assert r['skills_only_wins']==5 and r['python_only_wins']==0
    assert r['mcnemar_exact_p']==pytest.approx(.0625)
    assert paired_summary(runs,family_size=6)[0]['mcnemar_holm_p']==pytest.approx(.375)
    repeated=runs+[dict(r,rep=1) for r in runs]
    assert paired_summary(repeated)[0]['mcnemar_exact_p'] is None
    runs[0]['status']='api_error'
    assert paired_summary(runs)[0]['excluded_provider_pairs']==1
    runs[0]['status']='interrupted'
    assert paired_summary(runs)[0]['excluded_provider_pairs']==1


def test_request_wall_clock_deadline_and_unknown_cost_reserve():
    import time,httpx
    from weather_bench.transport import request_deadline,reserve_unconfirmed
    with pytest.raises(httpx.ReadTimeout):
        with request_deadline(.02):time.sleep(.2)
    ledger={'spent':1.,'uncertain_cost':True}
    config={'unknown_cost_policy':'reserve','max_context_bytes':1000,'max_output_tokens':100,
            'billing_prices':{'m':{'prompt':.00001,'completion':.00005}}}
    reserve=reserve_unconfirmed(ledger,config,'m','run')
    assert reserve>1000*.00001+100*.00005
    assert ledger['spent']==1.
    assert ledger['budget_reserve_usd']==reserve
    assert ledger['unconfirmed_requests'][0]['run_id']=='run'
    assert not ledger['uncertain_cost']


def test_task_budget_timeout_is_not_misclassified_as_provider_exclusion():
    from weather_bench.report import effective_status
    config={'hard_request_deadline':True,'task_timeout_seconds':600}
    run={'status':'api_error','solve_seconds':600.2,'events':[{'action':'api_error','message':'ReadTimeout'}]}
    assert effective_status(run,config)=='task_timeout'
    assert effective_status(dict(run,solve_seconds=120),config)=='api_error'
    assert effective_status(dict(run,status='interrupted'),config)=='interrupted'
    assert run['status']=='api_error'


def test_native_tool_response_failure_is_not_provider_outage():
    from weather_bench.report import effective_status,failure_detail
    run={'status':'api_error','solve_seconds':2,'events':[{'action':'api_error','message':"{'message': 'Provider ended completion with error'}"}],
         'requests':[{'provider':'Google AI Studio'}]}
    config={'hard_request_deadline':True,'task_timeout_seconds':1200}
    assert effective_status(run,config,'MALFORMED_FUNCTION_CALL')=='model_response_error'
    assert effective_status(run,config,'UNEXPECTED_TOOL_CALL')=='model_response_error'
    assert effective_status(run,config)=='api_error'  # Do not infer a cause without evidence.
    detail=failure_detail(run,'MALFORMED_FUNCTION_CALL')
    assert detail['category']=='model_response' and detail['code']=='MALFORMED_FUNCTION_CALL'
    assert run['status']=='api_error'  # Historical evidence remains untouched.


def test_failure_diagnostics_distinguish_overload_credit_check_and_server_errors():
    import json
    from weather_bench.report import failure_detail
    def describe(meta,code=429):
        run={'status':'api_error','events':[{'action':'api_error','message':json.dumps({'error':{'code':code,'message':'error','metadata':meta},'user_id':'private-account'})}]}
        detail=failure_detail(run)
        assert 'private-account' not in json.dumps(detail)
        return detail
    assert describe({'provider_error_code':'engine_overloaded','provider_name':'DeepInfra'})['category']=='overload'
    assert describe({'provider_error_code':'RATE_LIMIT_EXCEEDED'})['category']=='rate_limit'
    assert describe({'limit_source':'openrouter_admission_control'})['category']=='router_admission'
    assert describe({},500)['category']=='server'
    assert describe({'provider_error_code':'invalid_request_error'})['title']=='Provider HTTP 429'


def test_native_finish_reason_survives_public_audit(tmp_path,monkeypatch):
    import json
    from weather_bench import report
    monkeypatch.setattr(report,'ROOT',tmp_path)
    raw=tmp_path/'results/raw/run';raw.mkdir(parents=True)
    (raw/'000.json').write_text(json.dumps({'request':{'messages':[]},'response':{'choices':[{'native_finish_reason':'MALFORMED_FUNCTION_CALL','message':{'content':'visible','reasoning':'PRIVATE'}}]}}))
    run={'run_id':'run','requests':[{'finish_reason':'error','usage':{}}],'events':[]}
    audit=report.public_audit(run)
    assert audit['model_calls'][0]['native_finish_reason']=='MALFORMED_FUNCTION_CALL'
    assert 'PRIVATE' not in json.dumps(audit)


def test_response_failures_remain_in_capability_denominator():
    from weather_bench.statistics import condition_summary
    run={'model':'m','arm':'python','status':'model_response_error','correctness':{'passed':False},
         'usage':{'known_cost_usd':.01,'cost_complete':True,'total_tokens':100},'solve_seconds':1.,'trace':[]}
    result=condition_summary([run],include_provider_errors=False)[0]
    assert result['scored']==1 and result['success_rate']==0 and result['provider_errors']==0
