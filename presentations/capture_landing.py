"""Capture the current landing page, with explicit snapshot provenance."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'presentations/assets'
def capture():
    data=json.loads((ROOT/'docs/data.json').read_text())
    sid='comparison-20260930T155730Z-ae0a07'
    study=next(s for s in data['studies'] if s['study_id']==sid)
    with sync_playwright() as p:
        b=p.chromium.launch(executable_path='/Users/brandonrose/Library/Caches/ms-playwright/chromium-1243/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing',headless=True)
        page=b.new_page(viewport={'width':1600,'height':840},device_scale_factor=2)
        page.add_init_script('window.BENCHMARK_SNAPSHOT=true')
        page.goto((ROOT/'docs/index.html').as_uri())
        page.evaluate('''d=>{Object.assign(DATA,d);selectedStudy=DATA.studies.findIndex(s=>s.study_id==='comparison-20260930T155730Z-ae0a07');renderStudySelect();setFilters();renderResults();}''',data)
        page.screenshot(path=str(OUT/'dashboard-landing.png'))
        b.close()
    info={'exported_at':data['exported_at'],'study_id':sid,'recorded_attempts':len(study['runs']),'planned_attempts':study['planned_runs'],'finished':bool(study.get('finished_at')),'note':'Unfiltered landing page, viewport screenshot. Coverage continues below the visible viewport.'}
    (OUT/'landing-provenance.json').write_text(json.dumps(info,indent=2)+'\n')
    print(json.dumps(info),flush=True)
    return info
if __name__=='__main__':capture()
