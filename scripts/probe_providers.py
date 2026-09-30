"""Small, auditable transport checks. Never execute returned code or grade weather answers."""
import argparse,json,time,sys
from datetime import datetime,timezone
from pathlib import Path
import httpx
from dotenv import dotenv_values
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from weather_bench.catalog import ROOT,DEFAULT_CATALOG,inventory
from weather_bench.runner import prompt,parse_action,completion_error
from weather_bench.transport import request_deadline,stream_completion
from weather_bench.health import atomic_json
from weather_bench.report import public_text


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--panel',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
    panel=json.loads(Path(args.panel).read_text());key=next(v for k,v in dotenv_values(ROOT/'.env').items() if 'key' in k.lower() and v)
    report={'generated_at':datetime.now(timezone.utc).isoformat(),'kind':'transport-probes','runs':[],'known_cost_usd':0.}
    target=Path(args.output)
    with httpx.Client(headers={'Authorization':'Bearer '+key,'X-Title':'Weather benchmark transport probe'},timeout=45) as client:
        for spec in panel:
            model=spec['model'];arm=spec.get('arm','python');json_mode=spec.get('json_mode',True)
            action={'action':'python','code':'print(1 + 1)'} if arm=='python' else {'action':'read_skill','skill':'inspect-zarr'}
            messages=[{'role':'system','content':prompt(arm,max_calls=40,max_exec=40,allow_batch=True,network=True)},
                      {'role':'user','content':'Transport compatibility check only. Do not solve a weather task. Return exactly this JSON action: '+json.dumps(action)}]
            for turn in range(spec.get('turns',2)):
                if report['known_cost_usd']>=1:raise RuntimeError('Preflight $1 reported-cost ceiling reached')
                body={'model':model,'messages':messages,'max_tokens':512,'provider':{'only':spec['providers'],'allow_fallbacks':len(spec['providers'])>1,'require_parameters':True}}
                if spec.get('stream'):body['stream']=True
                if json_mode:body['response_format']={'type':'json_object'}
                if spec.get('reasoning',True):body['reasoning']={'effort':'low'}
                started=time.monotonic();row={'model':model,'arm':arm,'providers':spec['providers'],'json_mode':json_mode,'turn':turn+1}
                try:
                    with request_deadline(45):
                        if spec.get('stream'):
                            response,payload=stream_completion(client,body,45,ROOT/'results/raw/probes'/f'{model.replace("/","_")}-{arm}-{turn}.json')
                        else:
                            response=client.post('https://openrouter.ai/api/v1/chat/completions',json=body)
                            payload=response.json()
                    row['http_status']=response.status_code
                    row['stream']=bool(spec.get('stream'))
                    choice=(payload.get('choices') or [{}])[0];usage=payload.get('usage') or {}
                    row.update(provider=payload.get('provider'),finish_reason=choice.get('finish_reason'),native_finish_reason=choice.get('native_finish_reason'),usage={k:usage.get(k) for k in ('prompt_tokens','completion_tokens','total_tokens','cost')})
                    report['known_cost_usd']+=float(usage.get('cost') or 0)
                    content=choice.get('message',{}).get('content') or '';row['response']=public_text(content)
                    row['transport_ok']=response.status_code==200 and not completion_error(payload)
                    try:actual=parse_action(content);row['action_valid']=actual==action
                    except (ValueError,TypeError):row['action_valid']=False
                    if not row['transport_ok']:row['error']=public_text(str(completion_error(payload)))[:1000]
                    row['passed']=row['transport_ok'] and row['action_valid']
                except (httpx.HTTPError,ValueError) as exc:
                    row.update(passed=False,error=type(exc).__name__,billing_complete=False)
                    if isinstance(exc,httpx.HTTPStatusError):
                        row['http_status']=exc.response.status_code
                        row['error_detail']=public_text(exc.response.text)[:1000]
                row['seconds']=time.monotonic()-started;report['runs'].append(row);atomic_json(target,report)
                print(json.dumps({k:row[k] for k in ('model','arm','providers','json_mode','turn','passed','seconds','native_finish_reason','error') if k in row}),flush=True)
                if not row['passed']:break
                messages.append({'role':'assistant','content':content})
                feedback={'stdout':'2\n','stderr':'','returncode':0} if arm=='python' else {'documentation':(DEFAULT_CATALOG/inventory()['inspect-zarr']['doc']).read_text()}
                action={'action':'submit'} if arm=='python' else {'action':'skill','skill':'inspect-zarr','args':['--input','/inputs/example.zarr']}
                messages.append({'role':'user','content':'Execution observation:\n'+json.dumps(feedback)+'\nFor this transport check, return exactly '+json.dumps(action)})
    print('Reported probe cost: $'+str(report['known_cost_usd']),flush=True)

if __name__=='__main__':main()
