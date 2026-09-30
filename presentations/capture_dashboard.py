"""Capture an honest, frozen dashboard snapshot for the briefing slides."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'presentations/assets'
data=json.loads((ROOT/'docs/data.json').read_text())
study=next(s for s in data['studies'] if s['study_id']=='comparison-20260930T155730Z-ae0a07')
(OUT/'study-snapshot.json').write_text(json.dumps({'exported_at':data['exported_at'],'study':study},indent=2)+'\n')
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/Users/brandonrose/Library/Caches/ms-playwright/chromium-1243/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing',headless=True)
    page=browser.new_page(viewport={'width':1280,'height':1000},device_scale_factor=2)
    page.add_init_script('window.BENCHMARK_SNAPSHOT=true')
    page.goto((ROOT/'docs/index.html').as_uri())
    page.evaluate('''d=>{Object.assign(DATA,d);selectedStudy=DATA.studies.findIndex(s=>s.study_id==='comparison-20260930T155730Z-ae0a07');renderStudySelect();setFilters();renderResults();}''',data)
    page.screenshot(path=str(OUT/'dashboard-overview.png'),full_page=True)
    page.select_option('#model-select','anthropic/claude-fable-5.1')
    page.locator('[data-metric="latency"]').click()
    page.evaluate('''()=>{const el=document.createElement('div');el.id='slide-chart-capture';const first=document.querySelector('.chart-toolbar');first.before(el);for(const selector of ['.chart-toolbar','.result-basis','.metric-switch','#charts','#skill-adoption'])el.append(document.querySelector(selector));el.style.padding='18px';el.style.background='white';}''')
    page.locator('#slide-chart-capture').screenshot(path=str(OUT/'dashboard-comparison.png'))
    run=next(r for r in study['runs'] if r['model']=='anthropic/claude-fable-5.1' and r['arm']=='skills_only')
    page.evaluate('id=>showRun(id)',run['run_id'])
    page.locator('[data-log-view="calls"]').click()
    page.locator('#detail-drawer').evaluate('(el)=>{el.style.width="850px";el.style.height="600px";el.style.bottom="auto"}')
    page.locator('#detail-drawer').screenshot(path=str(OUT/'dashboard-trace.png'))
    (OUT/'screenshot-provenance.json').write_text(json.dumps({'exported_at':data['exported_at'],'study_id':study['study_id'],'run_id':run['run_id'],'selected_model':'anthropic/claude-fable-5.1','chart_metric':'latency','recorded_attempts':len(study['runs']),'planned_attempts':study['planned_runs'],'note':'Actual dashboard UI, frozen at export. Model filter is an interface illustration, not a ranking.'},indent=2)+'\n')
    print('Captured',len(study['runs']),'of',study['planned_runs'],'attempts; trace',run['run_id'])
    browser.close()
