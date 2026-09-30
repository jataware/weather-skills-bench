"""Create a separate final deck when the ten-model study stops; no model calls."""
import json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
status=ROOT/'presentations/final-refresh-status.json'
def save(**kwargs):
    tmp=status.with_suffix('.tmp');tmp.write_text(json.dumps(kwargs,indent=2)+'\n');tmp.replace(status)
sid='comparison-20260930T155730Z-ae0a07'
save(state='waiting',study_id=sid,output='presentations/weather-agent-benchmark-briefing-v2-final.pptx')
print('Waiting for final study export; the current v2 deck will not be overwritten.',flush=True)
try:
    deadline=time.monotonic()+4*3600
    while time.monotonic()<deadline:
        try:
            data=json.loads((ROOT/'docs/data.json').read_text())
            s=next((s for s in data['studies'] if s['study_id']==sid),None)
            if s and s.get('finished_at'):break
        except json.JSONDecodeError:pass
        time.sleep(15)
    else:raise TimeoutError('Study did not finish within four hours; current deck remains available.')
    subprocess.run([sys.executable,'presentations/capture_landing.py'],cwd=ROOT,check=True)
    env={**os.environ,'PYTHONPATH':'/tmp/weather-slides-deps','BRIEFING_SUFFIX':'v2-final'}
    subprocess.run([sys.executable,'presentations/build_briefing_v2.py'],cwd=ROOT,env=env,check=True)
    output=ROOT/'presentations/weather-agent-benchmark-briefing-v2-final.pptx'
    subprocess.run(['/opt/homebrew/bin/soffice','-env:UserInstallation=file:///tmp/weather-slides-final-lo-profile','--headless','--convert-to','pdf','--outdir',str(ROOT/'presentations/preview'),str(output)],check=True)
    info=json.loads((ROOT/'presentations/assets/landing-provenance.json').read_text())
    save(state='complete',study_id=sid,output=str(output.relative_to(ROOT)),snapshot=info)
    print('Final snapshot deck and PDF created.',flush=True)
except Exception as exc:
    save(state='failed',study_id=sid,error=str(exc));raise
