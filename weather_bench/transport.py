"""Wall-clock request deadlines and conservative accounting for unconfirmed requests."""
from contextlib import contextmanager
import json
import signal
import httpx


def stream_completion(client,body,timeout,journal):
    """Collect one SSE response; never return a partial action for execution.

    Persist partial responses on failure, including generation IDs and any usage.
    The runner decides whether a failed transport may retry within its budgets.
    """
    from .health import atomic_json
    payload={'choices':[]};choice={'index':0,'message':{'role':'assistant','content':''}}
    done=False
    try:
        with client.stream('POST','https://openrouter.ai/api/v1/chat/completions',json=body,timeout=timeout) as response:
            if response.status_code>=400:
                response.read();response.raise_for_status()
            if 'text/event-stream' not in response.headers.get('content-type',''):
                response.read();return response,response.json()
            event=[]
            def consume(lines):
                nonlocal done
                if not lines:return
                data='\n'.join(lines)
                if data.strip()=='[DONE]':done=True;return
                chunk=json.loads(data)
                for key in ('id','model','provider','usage','error'):
                    if key in chunk:payload[key]=chunk[key]
                for c in chunk.get('choices',[]):
                    if c.get('index',0)!=0:continue
                    delta=c.get('delta') or {}
                    content=delta.get('content')
                    if isinstance(content,str):choice['message']['content']+=content
                    for key in ('finish_reason','native_finish_reason','error'):
                        if c.get(key) is not None:choice[key]=c[key]
                    payload['choices']=[choice]
            for line in response.iter_lines():
                if not line:
                    consume(event);event=[]
                    if done:break
                elif line.startswith('data:'):event.append(line[5:].lstrip())
            if event:consume(event)
            if not done and not payload.get('error'):
                raise httpx.RemoteProtocolError('Completion stream ended without DONE')
            return response,payload
    except (httpx.HTTPError,ValueError,KeyboardInterrupt) as exc:
        atomic_json(journal,{'request':body,'response':payload,'transport_error':type(exc).__name__,'detail':str(exc),'complete':False})
        raise


@contextmanager
def request_deadline(seconds):
    def expired(signum,frame):
        raise httpx.ReadTimeout('Total request deadline exceeded (including keepalive traffic)')
    old=signal.signal(signal.SIGALRM,expired)
    signal.setitimer(signal.ITIMER_REAL,seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        signal.signal(signal.SIGALRM,old)


def reserve_unconfirmed(ledger,config,model,run_id,body=None):
    prices=config.get('billing_prices',{}).get(model)
    if config.get('unknown_cost_policy')!='reserve' or not prices:
        ledger['uncertain_cost']=True
        return
    # UTF-8 bytes bound ordinary BPE input tokens; extra allowance covers message
    # framing. Double the fixed endpoint rates to allow cache-write/route fees.
    size=sum(len(m['content'].encode()) for m in body['messages']) if body else config['max_context_bytes']
    reserve=2*((size+4096)*prices['prompt']+config['max_output_tokens']*prices['completion'])+.01
    if config.get('max_run_cost_usd') is not None and body:
        from .budget import request_cost_bound
        reserve=request_cost_bound(config,model,body)
    ledger['budget_reserve_usd']=ledger.get('budget_reserve_usd',0)+reserve
    ledger.setdefault('unconfirmed_requests',[]).append({'run_id':run_id,'model':model,'reserve_usd':reserve})
    ledger['uncertain_cost']=False  # bounded, not reconciled; run cost stays unknown
    return reserve
