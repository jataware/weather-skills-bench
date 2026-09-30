"use strict";
function studyLabel(s) { return s.config.study_label || (s.config.study_role==='small-model-extension'?'Small models · 1B / 3B':s.config.protocol_version==='skills-only-v2'?'Skills-only v2':'Archived pilot'); }
const DATA = window.BENCHMARK_DATA || {cases: [], studies: []};
const $ = id => document.getElementById(id);
const LABEL = {python: "Python only", skills_only: "Skills only", skills: "Python + skills", python_one_shot: "Python · one shot", docs_only: "Docs + Python"};
const COLOR = {skills_only: "#2563eb", skills: "#059669", python: "#ea580c", python_one_shot: "#7c3aed", docs_only: "#64748b"};
const ARMS = Object.keys(LABEL);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"}[c]));
const mean = xs => xs.length ? xs.reduce((a,b) => a+b, 0)/xs.length : null;
const median = xs => {const a = [...xs].sort((a,b)=>a-b), i = Math.floor(a.length/2); return a.length ? (a.length%2 ? a[i] : (a[i-1]+a[i])/2) : null;};
const money = n => n === null ? "Unknown" : "$" + n.toFixed(n < .01 ? 4 : 3);
const secs = n => n === null ? "—" : n.toFixed(1) + "s";
const tokens = n => n === null ? "—" : n >= 1000 ? (n/1000).toFixed(1)+"k" : Math.round(n).toLocaleString();
const knownCost = rs => rs.reduce((sum,r)=>sum+r.usage.known_cost_usd,0);
const cost = rs => rs.length && rs.every(r => r.usage.cost_complete) ? rs.reduce((a,r)=>a+r.usage.known_cost_usd,0) : null;
const ratio = (a,b) => a === null || b === null || b === 0 ? "—" : (a/b).toFixed(2)+"×";
const modelLabel = m => DATA.model_profiles?.[m]?.label || m;
const skillCalls = r => r.trace.filter(e=>e.action==='skill' && !(e.args || []).includes('--help'));
const docReads = r => r.trace.filter(e=>e.action==='read_skill').length;
const condition = arm => `<span class="condition"><i class="dot" style="--series:${COLOR[arm] || '#64748b'}"></i>${esc(LABEL[arm] || arm)}</span>`;
const pretty = value => `<pre>${esc(JSON.stringify(value, null, 2))}</pre>`;
let selectedStudy = DATA.studies.reduce((last,s,i)=>s.finished_at && s.runs.length === s.planned_runs ? i : last,-1);
const latestV2=DATA.studies.findLastIndex(s=>s.config?.protocol_version==='skills-only-v2' && s.config.study_role!=='small-model-extension');
if(latestV2>=0)selectedStudy=latestV2;
const latestE2E=DATA.studies.findLastIndex(s=>s.config?.study_role==='end-to-end' && s.runs.length);
if(latestE2E>=0)selectedStudy=latestE2E;
const latestRefined=DATA.studies.reduce((last,s,i)=>['cached-heat-v3','cached-heat-v4'].includes(s.config?.protocol_version) && (last<0 || (s.latest_activity_at || s.started_at)>=(DATA.studies[last].latest_activity_at || DATA.studies[last].started_at)) ? i : last,-1);
if(latestRefined>=0)selectedStudy=latestRefined;
if (selectedStudy < 0) selectedStudy = DATA.studies.length-1;
let resultBasis = "capability";
let sortKey = "model", sortDirection = 1, chartMetric = "success";
const visibleArms = new Set(ARMS.filter(a=>a!=="python_one_shot"));
const study = () => DATA.studies[selectedStudy] || null;
const orderedArms = () => ARMS.filter(a=>a!=="python_one_shot" && (study()?.config.arms || []).includes(a));
const filteredRuns = () => (study()?.runs || []).filter(r => ($("model-select").value === "all" || r.model === $("model-select").value) && ($("case-select").value === "all" || r.case_id === $("case-select").value));
const evaluable = r => !['api_error','interrupted','source_changed'].includes(r.status);
const outcomeLabel = r => ({model_response_error:r.correctness.passed?'Pass · response error':'Response format error',api_error:'Provider error',interrupted:'Interrupted · unscored',source_changed:'Source unverified · unscored'}[r.status] || (r.correctness.passed?'Pass':'Fail'));
const included = r => !['interrupted','source_changed'].includes(r.status) && (resultBasis==='operational' || r.status!=='api_error');
const selectedModels = () => (study()?.config.models || []).filter(m=>$('model-select').value==='all' || m===$('model-select').value);
const selectedCases = () => (study()?.config.cases || []).filter(c=>$('case-select').value==='all' || c===$('case-select').value);
function healthLabel(s) {
  if(s.finished_at)return s.runs.length===s.planned_runs?'Complete':'Stopped · partial';
  if(window.BENCHMARK_SNAPSHOT)return 'Partial · snapshot';
  const h=s.health;
  if(h?.state==='waiting')return 'Queued';
  if(h?.state==='running' && Date.now()-Date.parse(h.updated_at)<60000)return 'Running';
  return h?.state==='running'?'Update overdue':'Stopped';
}
function renderProgress(runs) {
  const s=study();if(!s)return;
  const models=selectedModels(), cases=selectedCases(),arms=orderedArms();
  runs=runs.filter(r=>arms.includes(r.arm));
  const retryIds=s.config.retry_attempts?new Set(s.config.retry_attempts):null;
  const scheduled=retryIds?[...new Map(DATA.studies.flatMap(s=>s.runs).filter(r=>retryIds.has(r.run_id)).map(r=>[r.run_id,r])).values()]:null;
  const planned=scheduled?scheduled.filter(r=>models.includes(r.model)&&cases.includes(r.case_id)&&arms.includes(r.arm)).length:models.length*cases.length*arms.length*s.config.repetitions;
  const pass=runs.filter(r=>evaluable(r)&&r.correctness.passed).length;
  const fail=runs.filter(r=>evaluable(r)&&!r.correctness.passed).length;
  const errors=runs.filter(r=>r.status==='api_error').length;
  const unscored=runs.filter(r=>['interrupted','source_changed'].includes(r.status)).length;
  const pending=Math.max(0,planned-runs.length), state=healthLabel(s),active=state==='Running'?s.health?.active:null;
  const segments=[['pass',pass,'passed'],['fail',fail,'task failures'],['provider',errors,'provider errors'],['unscored',unscored,'unscored'],['pending',pending,'pending']];
  $('study-progress').innerHTML=`<div class="progress-heading"><h2>${runs.length} / ${planned} ${s.repair_progress?'current outcomes':'attempts recorded'}</h2><span>${esc(state)}${s.health?.updated_at?' · Updated '+esc(new Date(s.health.updated_at).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})):''}</span></div><div class="progress-track" role="img" aria-label="${segments.map(([,n,l])=>n+' '+l).join(', ')}">${segments.filter(([,n])=>n).map(([key,n,label])=>`<span class="segment-${key}" style="width:${n/Math.max(planned,1)*100}%" title="${n} ${label}"></span>`).join('')}</div><div class="progress-legend">${segments.map(([key,n,label])=>`<span><i class="segment-${key}"></i><b>${n}</b> ${label}</span>`).join('')}</div>${active?`<p class="active-attempt">Now: ${esc(modelLabel(active.model))} · ${esc(LABEL[active.arm])} · ${esc(DATA.cases.find(c=>c.id===active.case_id)?.title || active.case_id)}</p>`:pending?'<p class="active-attempt">Unfinished experiment. Pending cells have no result.</p>':''}`;
  $('coverage').innerHTML=`<table><thead><tr><th>Model / task coverage</th>${cases.map(id=>`<th>${esc(DATA.cases.find(c=>c.id===id)?.title || id)}</th>`).join('')}</tr></thead><tbody>${models.map(model=>`<tr><th>${esc(modelLabel(model))}</th>${cases.map(id=>`<td><div class="coverage-cell">${arms.map(arm=>{
    const rs=runs.filter(r=>r.model===model && r.case_id===id && r.arm===arm);
    const scheduledCell=!scheduled || scheduled.some(r=>r.model===model && r.case_id===id && r.arm===arm);
    const current=active?.model===model && active?.case_id===id && active?.arm===arm;
    const r=rs.length===1?rs[0]:null;
    const kind=r?(r.status==='api_error'?'provider':['interrupted','source_changed'].includes(r.status)?'unscored':r.correctness.passed?'pass':'fail'):rs.length?'mixed':current?'running':'pending';
    const label=!scheduledCell?'Not scheduled':r?(r.status==='model_response_error'?'Response error':{provider:'Provider error',unscored:'Unscored',pass:'Pass',fail:'Fail'}[kind]):rs.length?`${rs.filter(r=>evaluable(r)&&r.correctness.passed).length} pass / ${rs.length} recorded`:current?'Running':'Pending';
    return `<button ${scheduledCell?'':'disabled'} class="coverage-result coverage-${kind}" data-cell-model="${esc(model)}" data-cell-case="${id}" data-cell-arm="${arm}" aria-label="${esc(modelLabel(model)+', '+id+', '+LABEL[arm]+': '+label)}"><span>${esc(LABEL[arm])}</span><b>${label}</b></button>`;
  }).join('')}</div></td>`).join('')}</tr>`).join('')}</tbody></table>`;
  $('coverage').querySelectorAll('[data-cell-model]').forEach(button=>button.addEventListener('click',()=>{
    const rs=runs.filter(r=>r.model===button.dataset.cellModel && r.case_id===button.dataset.cellCase && r.arm===button.dataset.cellArm);
    if(rs.length===1)return showRun(rs[0].run_id);
    showDetail(`${modelLabel(button.dataset.cellModel)} · ${LABEL[button.dataset.cellArm]}`,rs.length?runListHTML(rs):'<p>No saved attempt yet for this condition.</p>');bindRunLinks($('detail-content'));
  }));
}
function aggregate(runs) {
  const groups = [];
  for (const model of selectedModels()) for (const arm of orderedArms()) {
    const all = runs.filter(r=>r.model === model && r.arm === arm), rs=all.filter(included);
    const passed = rs.filter(r=>r.correctness.passed).length, total = cost(rs);
    groups.push({model, arm, attempts:all.length, n: rs.length, passed, success: rs.length?passed/rs.length*100:null,
      latency: median(rs.map(r=>r.solve_seconds)), tokens: mean(rs.map(r=>r.usage.total_tokens)),
      cost: total === null || !rs.length ? null : total/rs.length, cost_per_success: total === null || !passed ? null : total/passed, errors: all.filter(r=>r.status === "api_error").length,
      adoption: ["skills","skills_only"].includes(arm) && rs.length ? rs.filter(r=>skillCalls(r).length).length/rs.length : null,
      workflow: ["skills","skills_only"].includes(arm) && rs.length ? rs.filter(r=>r.workflow?.passed).length/rs.length : null});
  }
  return groups;
}
function niceMax(n) {
  if (!n) return 1;
  const power = 10 ** Math.floor(Math.log10(n)), value = n/power;
  return ([1,2,2.5,4,5,8,10].find(x=>x>=value) || 10)*power;
}
function wilson(passed,total) {
  if(!total)return null;const z=1.959963984540054,p=passed/total,d=1+z*z/total;
  const center=(p+z*z/(2*total))/d,r=z*Math.sqrt(p*(1-p)/total+z*z/(4*total*total))/d;
  return [Math.max(0,center-r),Math.min(1,center+r)];
}
function renderCharts(groups) {
  const shown=groups.filter(g=>visibleArms.has(g.arm));
  const models=[...new Set(shown.map(g=>g.model))].sort((a,b)=>modelLabel(a).localeCompare(modelLabel(b)));
  const arms=ARMS.filter(a=>visibleArms.has(a) && shown.some(g=>g.arm===a));
  const metrics={
    success:{title:study()?.quality?'Task success · registered score':'Task success',unit:'% · higher is better · 95% Wilson intervals',max:100,format:n=>Math.round(n)+'%',axis:n=>Math.round(n)+'%'},
    latency:{title:'Median completion time',unit:'seconds · lower is better',format:secs,axis:n=>Number(n.toFixed(1))+'s'},
    tokens:{title:'Average tokens',unit:'per attempt · lower is better',format:tokens,axis:tokens},
    cost:{title:'Average cost',unit:'USD per attempt · lower is better',format:money,axis:money}
  },metric=metrics[chartMetric];
  if(!shown.length){$('charts').innerHTML='<p class="empty">No results for the selected conditions.</p>';return;}
  const mobile=innerWidth<=600,width=mobile?Math.max(310,innerWidth-40):1160,left=mobile?135:175,right=mobile?72:135,top=15,plot=width-left-right;
  const barHeight=mobile?12:15,gap=6,groupHeight=arms.length*(barHeight+gap)+20;
  const bottom=top+models.length*groupHeight-10,height=bottom+32;
  const max=metric.max || niceMax(Math.max(...shown.map(g=>g[chartMetric] || 0)));
  let svg='';const ticks=mobile?2:4;
  for(let i=0;i<=ticks;i++){const x=left+plot*i/ticks;svg+=`<line class="grid" x1="${x}" x2="${x}" y1="5" y2="${bottom}"/><text x="${x}" y="${bottom+20}" text-anchor="middle">${esc(metric.axis(max*i/ticks))}</text>`;}
  models.forEach((model,i)=>{
    const y=top+i*groupHeight;svg+=`<text class="model-label" x="0" y="${y+arms.length*(barHeight+gap)/2}">${esc(modelLabel(model))}</text>`;
    arms.forEach((arm,j)=>{
      const g=shown.find(g=>g.model===model && g.arm===arm);if(!g)return;
      const value=g[chartMetric],w=value===null?0:value/max*plot,by=y+j*(barHeight+gap);
      const label=value===null?(g.n?'Unknown':g.errors?'Provider error':g.attempts?'Unscored':'Pending'):metric.format(value),suffix=chartMetric==='success' && g.n?` (${g.passed}/${g.n})`:'';
      const accessible=`${modelLabel(model)}, ${LABEL[arm]}, ${metric.title}: ${label}${suffix}. Open ${g.attempts} runs.`;
      let ci='';
      if(chartMetric==='success' && g.n){const [lo,hi]=wilson(g.passed,g.n).map(v=>left+v*plot),cy=by+barHeight/2;ci=`<path d="M ${lo} ${cy} H ${hi} M ${lo} ${cy-3} V ${cy+3} M ${hi} ${cy-3} V ${cy+3}" fill="none" stroke="#182230" stroke-width="1"/>`;}
      svg+=`<g class="bar-link" tabindex="0" role="button" data-model="${esc(model)}" data-arm="${arm}" aria-label="${esc(accessible)}"><title>${esc(accessible)}</title><rect x="${left}" y="${by-2}" width="${plot}" height="${barHeight+4}" fill="transparent"/>${value===null?'':`<rect x="${left}" y="${by}" width="${Math.max(w,1.5)}" height="${barHeight}" fill="${COLOR[arm]}"/>`}${ci}<text class="bar-value" x="${left+plot+8}" y="${by+barHeight-3}">${esc(label+suffix)}${g.errors && resultBasis==='operational'?'*':''}</text></g>`;
    });
  });
  $('charts').innerHTML=`<section class="chart"><div class="chart-heading"><h3>${metric.title}</h3><span>${metric.unit}</span></div><svg viewBox="0 0 ${width} ${height}" role="group" aria-label="${metric.title}; select a bar for underlying attempts">${svg}</svg></section>`;
  $('charts').querySelectorAll('.bar-link').forEach(bar=>{
    const open=()=>showGroup(bar.dataset.model,bar.dataset.arm);
    bar.addEventListener('click',open);bar.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();open();}});
  });
}
function renderTable(groups) {
  groups.sort((a,b) => {
    const value=g=>sortKey==='model'?modelLabel(g.model):sortKey==='arm'?ARMS.indexOf(g.arm):g[sortKey];
    const av=value(a), bv=value(b);
    if (av===null || bv===null) return av===bv ? 0 : av===null ? 1 : -1;
    const result=typeof av==='string' ? av.localeCompare(bv) : av-bv;
    return result*sortDirection || modelLabel(a.model).localeCompare(modelLabel(b.model)) || ARMS.indexOf(a.arm)-ARMS.indexOf(b.arm);
  });
  $("comparison").innerHTML=groups.map(g=>`<tr><td><button class="text-button model-name" data-group-model="${esc(g.model)}" data-group-arm="${g.arm}">${esc(modelLabel(g.model))}</button><span class="weight-label">${esc(DATA.model_profiles?.[g.model]?.weights || '')}</span></td><td>${condition(g.arm)}</td><td class="numeric"><span class="success-value">${g.n?Math.round(g.success)+'%':'—'}</span><span class="rate-count">${g.n?g.passed+"/"+g.n+" · "+wilson(g.passed,g.n).map(x=>Math.round(x*100)).join("–")+"%":"No task outcome"}</span></td><td class="numeric">${secs(g.latency)}</td><td class="numeric">${tokens(g.tokens)}</td><td class="numeric">${g.n?money(g.cost):'—'}</td><td class="numeric">${!g.passed?'—':money(g.cost_per_success)}</td><td class="numeric ${g.errors?'error':'muted'}">${g.errors || '—'}</td><td class="numeric muted">${g.adoption===null?'—':`${Math.round(g.adoption*g.n)}/${g.n}`}</td><td class="numeric muted">${g.workflow===null?'—':`${Math.round(g.workflow*g.n)}/${g.n}`}</td></tr>`).join('') || '<tr><td colspan="10" class="empty">No results in this selection.</td></tr>';
  document.querySelectorAll('[data-group-model]').forEach(button=>button.addEventListener('click',()=>showGroup(button.dataset.groupModel,button.dataset.groupArm)));
  document.querySelectorAll('[data-sort]').forEach(button=>{
    const base=button.dataset.label || button.textContent.replace(/ [↑↓]$/, '');
    button.dataset.label=base;
    button.textContent=base+(button.dataset.sort===sortKey ? (sortDirection===1 ? ' ↑' : ' ↓') : '');
    button.parentElement.setAttribute('aria-sort',button.dataset.sort===sortKey ? (sortDirection===1 ? 'ascending' : 'descending') : 'none');
  });
}
function renderPaired(runs) {
  const arm=study()?.config.primary_skill_arm || (study()?.config.arms.includes('skills_only')?'skills_only':'skills'),rows=[];
  $('paired-title').textContent=`Paired effect · ${LABEL[arm]} vs. Python only`;
  $('paired-wins').textContent=`${LABEL[arm]} wins / Python only wins`;
  const source=(study()?.runs || []).filter(r=>$('case-select').value==='all' || r.case_id===$('case-select').value);
  for(const model of [...new Set(source.map(r=>r.model))]) {
    const a=source.filter(r=>r.model===model && r.arm===arm),b=source.filter(r=>r.model===model && r.arm==='python');
    const matched=a.map(a=>[a,b.find(b=>b.case_id===a.case_id && b.rep===a.rep)]).filter(([a,b])=>b);
    const pairs=matched.filter(([a,b])=>!['api_error','interrupted','source_changed'].includes(a.status) && !['api_error','interrupted','source_changed'].includes(b.status));
    if(!pairs.length)continue;
    const wins=pairs.filter(([a,b])=>a.correctness.passed&&!b.correctness.passed).length,losses=pairs.filter(([a,b])=>!a.correctness.passed&&b.correctness.passed).length;
    const independent=new Set(pairs.map(p=>p[0].case_id)).size===pairs.length,n=wins+losses;
    let p=1;if(n){let term=1,sum=1;for(let i=1;i<=Math.min(wins,losses);i++){term*= (n-i+1)/i;sum+=term;}p=Math.min(1,2*sum/2**n);}
    rows.push({model,n:pairs.length,excluded:matched.length-pairs.length,wins,losses,diff:(wins-losses)/pairs.length*100,p:independent?p:null});
  }
  let previous=0;const familySize=study()?.config.models.length || rows.length;const tested=rows.filter(r=>r.p!==null).sort((a,b)=>a.p-b.p);
  tested.forEach((r,i)=>{previous=Math.max(previous,Math.min(1,r.p*(familySize-i)));r.adjusted=previous;});
  const ptext=p=>p===null || p===undefined?'—':p<.001?'<0.001':p.toFixed(3);
  $('paired').innerHTML=rows.filter(r=>$('model-select').value==='all' || r.model===$('model-select').value).map(r=>`<tr><td>${esc(modelLabel(r.model))}</td><td class="numeric">${r.n}${r.excluded?`<span class="rate-count">${r.excluded} excluded</span>`:''}</td><td class="numeric">${r.wins} / ${r.losses}</td><td class="numeric">${r.diff>0?'+':''}${Math.round(r.diff)} pp</td><td class="numeric">${esc(ptext(r.p))}</td><td class="numeric">${esc(ptext(r.adjusted))}</td></tr>`).join('') || '<tr><td colspan="6" class="empty">No matched pairs in this selection.</td></tr>';
}
function selectedRuns(runs) {
  const outcome=$("outcome-select").value, arm=$("run-arm-select").value;
  return runs.filter(r=>(arm==='all' || r.arm===arm) && (outcome==='all' || (outcome==='api_error' ? r.status==='api_error' : outcome==='pass' ? r.correctness.passed : !r.correctness.passed)));
}
function bindRunLinks(root) {
  root.querySelectorAll('[data-run]').forEach(button=>button.addEventListener('click',()=>showRun(button.dataset.run)));
}
function renderScatter(runs) {
  const known=runs.filter(r=>r.usage.cost_complete), width=window.innerWidth<600 ? Math.max(310,innerWidth-40) : 1100;
  const height=310, left=80, right=25, top=15, bottom=255;
  const maxTokens=niceMax(Math.max(1,...known.map(r=>r.usage.total_tokens)));
  const maxCost=niceMax(Math.max(.0001,...known.map(r=>r.usage.known_cost_usd)));
  let svg='';
  for(let i=0;i<=4;i++) {
    const x=left+(width-left-right)*i/4, y=bottom-(bottom-top)*i/4;
    svg+=`<line class="grid" x1="${x}" x2="${x}" y1="${top}" y2="${bottom}"/><text x="${x}" y="${bottom+20}" text-anchor="middle">${tokens(maxTokens*i/4)}</text><line class="grid" x1="${left}" x2="${width-right}" y1="${y}" y2="${y}"/><text x="${left-10}" y="${y+4}" text-anchor="end">${money(maxCost*i/4)}</text>`;
  }
  svg+=`<text x="${left+(width-left-right)/2}" y="${height-8}" text-anchor="middle">Total tokens per attempt →</text><text transform="translate(13 ${bottom/2}) rotate(-90)" text-anchor="middle">Billed cost (USD) →</text>`;
  known.forEach(r=>{
    const x=left+(width-left-right)*r.usage.total_tokens/maxTokens, y=bottom-(bottom-top)*r.usage.known_cost_usd/maxCost;
    const label=`${modelLabel(r.model)} · ${LABEL[r.arm]} · ${r.case_id} · ${outcomeLabel(r)} · ${r.usage.total_tokens.toLocaleString()} tokens · ${money(r.usage.known_cost_usd)}`;
    const shape=r.status==='api_error'?`<path d="M ${x-5} ${y-5} l 10 10 M ${x-5} ${y+5} l 10 -10" stroke="${COLOR[r.arm]}" stroke-width="2.5"/>`:`<circle cx="${x}" cy="${y}" r="6" fill="${r.correctness.passed?COLOR[r.arm]:'white'}" stroke="${COLOR[r.arm]}" stroke-width="2"/>`;
    svg+=`<g class="run-point" role="button" tabindex="0" data-run="${esc(r.run_id)}" aria-label="${esc(label)}"><title>${esc(label)}</title><circle cx="${x}" cy="${y}" r="11" fill="transparent"/>${shape}</g>`;
  });
  $("run-scatter").innerHTML=known.length?`<svg viewBox="0 0 ${width} ${height}" role="group" aria-label="Individual run tokens and billed cost">${svg}</svg>`:'<p class="empty">No attempts with known billing in this selection.</p>';
  $("run-hover").textContent=`${runs.length} attempts${runs.length-known.length?`; ${runs.length-known.length} with unknown cost omitted from plot`:''}. Select a point or use View log below.`;
  bindRunLinks($("run-scatter"));
  $("run-scatter").querySelectorAll('[data-run]').forEach(point=>{
    const label=()=>{$("run-hover").textContent=point.getAttribute('aria-label')};
    point.addEventListener('mouseenter',label);point.addEventListener('focus',label);
    point.addEventListener('keydown',event=>{if(event.key==='Enter' || event.key===' '){event.preventDefault();showRun(point.dataset.run)}});
  });
}
function renderRuns(runs) {
  $("run-legend").innerHTML=orderedArms().map(a=>condition(a)).join("")+"<span>● Pass &nbsp; ○ Fail &nbsp; × Provider error</span>";
  const selected=selectedRuns(runs);
  $("runs").innerHTML=selected.map(r=>`<tr><td><button class="text-button model-name" data-run="${esc(r.run_id)}">${esc(modelLabel(r.model))}</button><div class="run-condition">${condition(r.arm)}</div></td><td>${esc(DATA.cases.find(c=>c.id===r.case_id)?.title || r.case_id)}</td><td class="${r.correctness.passed?'pass':'fail'}">${outcomeLabel(r)}</td><td class="numeric">${secs(r.solve_seconds)}</td><td class="numeric">${tokens(r.usage.total_tokens)}</td><td class="numeric">${money(r.usage.cost_complete?r.usage.known_cost_usd:null)}</td><td class="numeric">${['skills','skills_only'].includes(r.arm)?skillCalls(r).length:'—'}</td><td><button class="text-button" data-run="${esc(r.run_id)}">View log →</button></td></tr>`).join('') || '<tr><td colspan="8" class="empty">No attempts in this selection.</td></tr>';
  bindRunLinks($("runs"));renderScatter(selected);
}
function renderResults() {
  const s=study(), runs=filteredRuns(), groups=aggregate(runs), errors=runs.filter(r=>r.status==='api_error').length;
  const prior=(s?.prior_provider_attempts || []).filter(r=>($('model-select').value==='all' || r.model===$('model-select').value) && ($('case-select').value==='all' || r.case_id===$('case-select').value));
  const spendRuns=[...runs,...prior];
  const fullRepair=s?.repair_progress && $('model-select').value==='all' && $('case-select').value==='all';
  const reportedSpend=fullRepair?s.ledger.spent:knownCost(spendRuns);
  $("study-status").textContent=s ? `${studyLabel(s)} · ${healthLabel(s)}` : 'No model runs';
  $("study-summary").innerHTML=[`<b>${runs.length}</b> ${s?.repair_progress?'current outcomes':'recorded attempts'}`,`<b>${runs.filter(evaluable).length}</b> task outcomes`,`<b>${selectedModels().length}</b> models`,`<b>${selectedCases().length}</b> tasks`,`<b>${s?.config.repetitions || 0}</b> repetition${s?.config.repetitions===1?'':'s'}`,`<b>${cost(spendRuns)===null?'≥'+money(reportedSpend):money(reportedSpend)}</b> ${cost(spendRuns)===null?'reported spend · billing incomplete':'reported spend'}${prior.length?' · includes original failures':''}`,...(errors?[`<span class="error">${errors} provider errors</span>`]:[])].map(x=>`<span>${x}</span>`).join('');
  $("exclusion-note").hidden=!s?.config.exclusion_note;
  $("exclusion-note").textContent=s?.config.exclusion_note || "";
  $("run-count").textContent=runs.length;
  const eligible=runs.filter(r=>['skills','skills_only'].includes(r.arm));
  $("skill-adoption").textContent=eligible.length ? `Skill invocation: ${eligible.filter(r=>skillCalls(r).length).length}/${eligible.length} runs invoked a skill · ${eligible.filter(r=>docReads(r)).length}/${eligible.length} read a guide. ${study()?.config.primary_skill_arm==='skills'?'Python is available in the main comparison; Skills only is a separate diagnostic.':study()?.config.arms.includes('skills_only')?'Model-written code disabled.':'Skills and Python available.'}` : '';
  renderProgress(runs);
  $("quality-note").hidden=!s?.quality;
  $("quality-note").innerHTML=s?.quality?`<b>${esc(s.quality.title)}</b><span>${esc(s.quality.note)}</span>`:'';
  $("basis-note").textContent=resultBasis==='capability'?'Provider errors excluded from success, time, tokens and cost averages.':'Provider errors included; interruptions and unverified sources remain unscored.';
  if(s?.repair_progress)$('basis-note').textContent+=' Charts summarize displayed attempts; total spend also includes original provider failures.';
  renderCharts(groups);renderTable(groups);renderPaired(runs);renderRuns(runs);renderTasks();
  const diagnostics=s?.diagnostics, notes=[];
  if (diagnostics?.provider_failures) notes.push(`${diagnostics.provider_failures} additional provider failures retained as diagnostics.`);
  if (diagnostics?.interruption) {const i=diagnostics.interruption; notes.push(`${i.unknown_requests || 1} interrupted request(s) have unconfirmed billing. Recorded diagnostic cost: $${(i.total_known_cost_usd ?? i.known_cost_usd ?? 0).toFixed(4)}; excluded from scored spend.`);}
  if(s?.ledger.unconfirmed_requests?.length) notes.push(`${s.ledger.unconfirmed_requests.length} request(s) have unconfirmed charges. Known study charges: ${money(s.ledger.spent)}; budget reserve: ${money(s.ledger.budget_reserve_usd)} (not billed cost).`);
  if(s?.resume_note) notes.push(s.resume_note);
  if(s?.repair_progress)notes.push(`Provider retries: ${s.repair_progress.recorded}/${s.repair_progress.planned} recorded.`);
  for (const [model,reason] of Object.entries(diagnostics?.excluded_models || {})) notes.push(`${modelLabel(model)} excluded: ${reason}`);
  $("diagnostics").textContent=notes.join(' ') || 'No additional study diagnostics.';
  $("footer-note").textContent=s ? `Study ${s.study_id} · ${s.runs.length}/${s.planned_runs} attempts recorded` : 'Reference validation only';
}
let drawerHistory=[],drawerOpener=null;
function closeDrawer(){ $('detail-drawer').hidden=true;drawerHistory=[];if(drawerOpener?.isConnected)drawerOpener.focus(); }
function showDetail(title,html) {
  const drawer=$('detail-drawer');
  if(!drawer.hidden)drawerHistory.push({title:$('detail-title').textContent,nodes:[...$('detail-content').childNodes],scroll:drawer.scrollTop});
  else{drawerHistory=[];drawerOpener=document.activeElement;}
  $('detail-title').textContent=title;$('detail-content').innerHTML=html;drawer.hidden=false;drawer.scrollTop=0;
  $('drawer-back').hidden=!drawerHistory.length;$('detail-title').focus({preventScroll:true});
}
function runListHTML(runs) {
  return `<div class="drawer-run-list">${runs.map(r=>`<button class="drawer-run" data-run="${esc(r.run_id)}"><span><b>${esc(DATA.cases.find(c=>c.id===r.case_id)?.title || r.case_id)}</b><small>${esc(modelLabel(r.model))} · ${esc(LABEL[r.arm])} · repetition ${r.rep+1}</small></span><span class="${r.correctness.passed?'pass':'fail'}">${outcomeLabel(r)} →<small>${tokens(r.usage.total_tokens)} tokens · ${money(r.usage.cost_complete?r.usage.known_cost_usd:null)} · ${secs(r.solve_seconds)}</small></span></button>`).join('') || '<p class="empty">No runs for this selection.</p>'}</div>`;
}
function showGroup(model,arm) {
  const runs=filteredRuns().filter(r=>r.model===model && r.arm===arm),scored=runs.filter(included),passed=scored.filter(r=>r.correctness.passed).length;
  showDetail(`${modelLabel(model)} · ${LABEL[arm]}`,`<div class="run-metrics"><span><b>${passed}/${scored.length}</b> ${resultBasis==='capability'?'task outcomes':'scored attempts'} passed</span><span><b>${tokens(runs.reduce((n,r)=>n+r.usage.total_tokens,0))}</b> total tokens</span><span><b>${money(cost(runs))}</b> total billed</span></div><p class="footnote">${runs.reduce((n,r)=>n+r.trace.filter(e=>e.action==='protocol_error').length,0)} rejected actions · ${runs.reduce((n,r)=>n+r.trace.filter(e=>e.returncode && ['python','skill'].includes(e.action)).length,0)} failed executions · ${runs.filter(r=>r.status==='api_error').length} provider errors${runs.some(r=>r.status==='interrupted')?` · ${runs.filter(r=>r.status==='interrupted').length} unscored interruption(s)`:''}</p>${runListHTML(runs)}`);
  bindRunLinks($('detail-content'));
}
function feedbackHTML(text) {
  let value;try{value=JSON.parse(text);}catch{return `<pre>${esc(text)}</pre>`;}
  if(value && typeof value==='object' && 'remaining_budget' in value && 'result' in value) return feedbackHTML(JSON.stringify(value.result))+`<h4>Remaining budget</h4>${pretty(value.remaining_budget)}`;
  return (Array.isArray(value)?value:[value]).map((entry,i)=>{
    if(!entry || typeof entry!=='object')return pretty(entry);
    return `<div>${Array.isArray(value)?`<h4>Action ${i+1} feedback</h4>`:''}${Object.entries(entry).map(([key,value])=>`<h4>${esc(key)}</h4>${typeof value==='string'?`<pre>${esc(value || '(empty)')}</pre>`:pretty(value)}`).join('')}</div>`;
  }).join('');
}
function showRun(id) {
  const r=[...(study()?.runs || []),...(study()?.prior_provider_attempts || [])].find(r=>r.run_id===id) || DATA.studies.flatMap(s=>s.runs).find(r=>r.run_id===id);if(!r)return;
  const audit=r.audit, events=audit?.events || r.trace, calls=audit?.model_calls || [];
  const title=e=>e.skill?`${e.action==='read_skill'?'Read guide':'Run skill'} · ${e.skill}`:e.action.replaceAll('_',' ');
  const log=events.map((e,i)=>`<details class="log-event" ${e.returncode || e.action.endsWith('error')?'open':''}><summary><span class="event-number">${i+1}</span><b>${esc(title(e))}</b><span class="event-result ${e.returncode || e.action.endsWith('error')?'fail':'muted'}">${e.returncode===undefined?'':`exit ${e.returncode} · `}${e.seconds===undefined?'':secs(e.seconds)}${e.cache_hit?' · cached within run':''}</span></summary>${e.turn && calls.some(c=>c.number===e.turn)?`<p><button class="text-button" data-call-number="${e.turn}">Model response ${e.turn} →</button>${e.action==='read_skill' && calls.some(c=>c.number===e.turn+1)?` · <button class="text-button" data-call-number="${e.turn+1}" data-feedback="true">Read guide feedback →</button>`:''}</p>`:''}${e.wait_seconds!==undefined?`<p>${typeof e.http_status==='number'?'HTTP ':''}${esc(e.http_status)} · Retry ${esc(e.retry_number)} · Wait ${secs(e.wait_seconds)} · Counts toward the original request and time budgets.</p>`:''}${e.action==='budget_stop'?`<p>Remaining run allowance ${money(e.run_remaining_usd)} · Next request bound ${money(e.next_request_bound_usd)} · Unconfirmed reserve ${money(e.unconfirmed_reserve_usd)}</p>`:''}${e.fields?`<h4>Artifact submission</h4>${pretty(e.fields)}`:''}${e.args?`<h4>Arguments</h4>${pretty(e.args)}`:''}${e.code!==undefined?`<h4>Executed Python</h4><pre>${esc(e.code)}</pre>`:''}${e.message?`<h4>Error / observation</h4><pre>${esc(e.message)}</pre>`:''}${e.stdout!==undefined?`<h4>stdout</h4><pre>${esc(e.stdout || '(empty)')}</pre>`:''}${e.stderr!==undefined?`<h4>stderr</h4><pre class="${e.returncode?'error-output':''}">${esc(e.stderr || '(empty)')}</pre>`:''}${!audit?'<p class="muted">Detailed output was not exported for this archived run.</p>':''}</details>`).join('');
  const maxTokens=Math.max(1,...calls.map(c=>c.usage.total_tokens || 0));
  let cumulative=0, costKnown=true;
  const callRows=calls.map(c=>{
    if(c.usage.cost===null || c.usage.cost===undefined)costKnown=false;else cumulative+=c.usage.cost;
    return `<tr><td>${c.number}</td><td><div class="call-bar" aria-label="${esc(`${c.usage.prompt_tokens ?? 'Unknown'} input and ${c.usage.completion_tokens ?? 'Unknown'} output tokens`)}"><i style="width:${(c.usage.prompt_tokens || 0)/maxTokens*100}%"></i><i style="width:${(c.usage.completion_tokens || 0)/maxTokens*100}%"></i></div></td><td class="numeric">${tokens(c.usage.total_tokens)}</td><td class="numeric">${money(c.usage.cost ?? null)}</td><td class="numeric">${money(costKnown?cumulative:null)}</td><td class="numeric">${secs(c.seconds ?? null)}</td></tr>`;
  }).join('');
  const responses=calls.map(c=>`<details class="log-event" id="model-response-${c.number}"><summary>Response ${c.number}<span class="event-result muted">${esc(c.native_finish_reason || c.finish_reason || 'unreported')} · ${esc(c.provider || 'unreported')}</span></summary>${c.input_observation?`<details><summary>Feedback received before this response</summary>${feedbackHTML(c.input_observation)}</details>`:''}<h4>Model response</h4><pre>${esc(c.response ?? 'Visible response was not recorded or is unavailable in this export.')}</pre></details>`).join('');
  const caseInfo=DATA.cases.find(c=>c.id===r.case_id);
  showDetail(`${modelLabel(r.model)} · ${LABEL[r.arm]}`,`
    <p class="muted">${esc(caseInfo?.title || r.case_id)} · <span class="${r.correctness.passed?'pass':'fail'}">${outcomeLabel(r)}</span> · Stop: ${esc(r.status)}</p>
    ${r.retry_of?`<p><button class="text-button" id="original-attempt">View original provider failure →</button></p>`:''}${r.failure_detail?`<p class="failure-explanation"><b>${esc(r.failure_detail.title)}</b>${r.failure_detail.provider?` · ${esc(r.failure_detail.provider)}`:''} · <code>${esc(r.failure_detail.code)}</code><br>${esc(r.failure_detail.message)}${r.original_status!==r.status?`<br>Classification corrected from ${esc(r.original_status)} using the recorded stopping evidence; original response and score retained.`:''}</p>`:''}
    <div class="run-metrics"><span><b>${secs(r.solve_seconds)}</b> solve time</span><span><b>${r.usage.total_tokens.toLocaleString()}</b> tokens</span><span><b>${r.usage.cost_complete?money(r.usage.known_cost_usd):'≥'+money(r.usage.known_cost_usd)}</b> ${r.usage.cost_complete?'billed':'reported · billing incomplete'}</span><span><b>${skillCalls(r).length}</b> skill calls</span><span><b>${docReads(r)}</b> guides read</span>${r.provider_retries!==undefined?`<span><b>${r.provider_retries}</b> provider retries · ${secs(r.retry_wait_seconds)} waiting</span>`:''}<button id="download-log" class="text-button">Download log ↓</button></div>
    ${r.budget?`<p class="footnote">Run allowance: ${money(r.budget.cap_usd)} · Reported: ${money(r.budget.reported_usd)} · Unconfirmed reserve: ${money(r.budget.reserved_usd)}. Requests require room for a conservative cost estimate; reservations are not billed charges.</p>`:''}
    <nav class="log-tabs" aria-label="Run details"><button data-log-view="execution" aria-current="page">Execution log (${events.length})</button><button data-log-view="calls">Model calls (${calls.length})</button><button data-log-view="answer">Answer & grading</button></nav>
    <section id="log-execution"><p class="log-controls"><button class="text-button" id="expand-events">Expand all</button> · <button class="text-button" id="collapse-events">Collapse all</button></p>${log || '<p class="muted">No execution events recorded.</p>'}</section>
    <section id="log-calls" hidden><p class="footnote">Tokens per request: <span class="input-key">■ Input</span> <span class="output-key">■ Output</span>. Input includes conversation history and cached tokens.</p><div class="table-scroll"><table><thead><tr><th>Call</th><th>Token usage</th><th class="numeric">Total</th><th class="numeric">Cost</th><th class="numeric">Cumulative</th><th class="numeric">Time</th></tr></thead><tbody>${callRows || '<tr><td colspan="6">No returned model requests recorded.</td></tr>'}</tbody></table></div>
    <p class="footnote">Input ${r.usage.prompt_tokens.toLocaleString()} · Output ${r.usage.completion_tokens.toLocaleString()} · Cached input ${r.usage.cached_tokens.toLocaleString()} · Reasoning ${r.usage.reasoning_tokens.toLocaleString()} (already included in output).</p>${responses}${audit?.instructions?`<details><summary>Agent instructions sent to the model</summary><pre>${esc(audit.instructions)}</pre></details>`:''}<p class="footnote">Model ${secs(r.llm_seconds)} · Execution ${secs(r.execution_seconds)} · Setup ${secs(r.setup_seconds)}. Provider: ${esc(r.providers.join(', ') || 'Unreported')}.</p></section>
    <section id="log-answer" hidden>${r.figure?`<p>Scientific result: <b>${r.scientific_correctness?.passed?'Pass':'Fail'}</b> · Figure delivery: <b>${r.figure.passed?'Pass':'Fail'}</b></p>${r.figure.url?`<a href="${esc(r.figure.url)}" target="_blank" rel="noopener"><img src="${esc(r.figure.url)}" alt="Forecast figure produced in this run" style="max-width:100%;height:auto"></a>`:''}<p class="footnote">Figure delivery checks PNG format, size and nonblank pixels; visual scientific correctness requires review.</p><details><summary>Source versions and network transfer</summary>${pretty({versions:r.source_versions,connections:r.network_events})}</details>`:''}${r.sensitivity_audit?`<p class="quality-note"><b>Post-hoc rainfall sensitivity check</b><span>Direct cumulative endpoint differences: ${r.sensitivity_audit.endpoint_scientific_passed?'numeric answer passes':'numeric answer fails'}. Registered scores below are unchanged; the original brief omitted the clipping rule.</span></p>`:''}<h3>Answer check</h3><p class="${r.correctness.passed?'pass':'fail'}">${['interrupted','source_changed'].includes(r.status)?'This attempt is unscored. Artifact checks below are retained for inspection.':r.status==='api_error'?'Provider failure. Artifact checks below do not establish a completed task outcome.':r.correctness.passed?'All answer checks passed.':'Answer did not meet the task contract.'}</p>${r.correctness.failures.length?`<ul class="grading-failures">${r.correctness.failures.map(f=>`<li>${esc(f)}</li>`).join('')}</ul>`:''}<div class="answer-comparison"><section><h3>Submitted answer</h3>${pretty(r.answer)}</section><section><h3>Expected answer</h3>${pretty(caseInfo?.expected ?? null)}</section></div>${r.workflow?`<details><summary>Reference workflow · ${r.workflow.passed?'matched':'not matched'}</summary><p class="footnote">This checks the reference recipe and artifact dependencies. A correct alternative can differ.</p>${pretty(r.workflow)}</details>`:''}</section>
    <p class="footnote log-policy">${esc(audit?.note || 'Only the archived action sequence is available for this run.')}</p><p class="mono muted">Run ${esc(r.run_id)}${r.source_study_id?` · Batch ${esc(r.source_study_id)}`:''}</p>`);
  if($('original-attempt'))$('original-attempt').addEventListener('click',()=>showRun(r.retry_of.run_id));
  document.querySelectorAll('[data-log-view]').forEach(button=>button.addEventListener('click',()=>{
    document.querySelectorAll('[data-log-view]').forEach(b=>{const active=b===button;if(active)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');$('log-'+b.dataset.logView).hidden=!active;});
  }));
  $('expand-events').addEventListener('click',()=>document.querySelectorAll('#log-execution > details').forEach(d=>d.open=true));
  $('collapse-events').addEventListener('click',()=>document.querySelectorAll('#log-execution > details').forEach(d=>d.open=false));
  document.querySelectorAll('[data-call-number]').forEach(button=>button.addEventListener('click',()=>{
    document.querySelector('[data-log-view="calls"]').click();
    const response=$('model-response-'+button.dataset.callNumber);
    if(response){response.open=true;if(button.dataset.feedback)response.querySelectorAll('details').forEach(d=>d.open=true);response.scrollIntoView({block:'center'});}
  }));
  $("download-log").addEventListener('click',()=>{
    const url=URL.createObjectURL(new Blob([JSON.stringify(r,(key,value)=>window.BENCHMARK_ASSET_EXPORT?.get(value) || value,2)],{type:'application/json'}));
    const link=document.createElement('a');link.href=url;link.download=`run-${r.run_id}.json`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
}
function renderTasks() {
  const taskCases=DATA.cases.filter(c=>(study()?.config.cases || []).includes(c.id));
  $("task-count").textContent=taskCases.length;
  $("validation-status").textContent=`${taskCases.filter(c=>c.oracle_verified ?? c.reference_passed).length}/${taskCases.length} answers verified · ${taskCases.filter(c=>c.reference_passed).length} catalog workflows pass`;
  const taskRuns=(study()?.runs || []).filter(r=>$('model-select').value==='all' || r.model===$('model-select').value);
  const arms=orderedArms();
  $('task-headings').innerHTML='<th>Task</th><th class="numeric">Skill steps</th>'+arms.map(arm=>`<th class="numeric">${esc(LABEL[arm])} success</th>`).join('')+'<th>Traces</th>';
  const taskRate=(id,arm)=>{const rs=taskRuns.filter(r=>r.case_id===id && r.arm===arm && included(r));return rs.length?`${rs.filter(r=>r.correctness.passed).length}/${rs.length}`:'—';};
  $('task-list').innerHTML=taskCases.map(c=>{const i=DATA.cases.indexOf(c);return `<tr><td><button class="text-button model-name" data-task="${i}">${esc(c.title)}</button><div class="run-condition">${c.suite==='cached-forecast-v3'?'Real forecast · cached raw data':c.suite==='end-to-end-v1'?'Real forecast · live retrieval':'Synthetic diagnostic'}</div></td><td class="numeric">${c.recipe.length}</td>${arms.map(arm=>`<td class="numeric">${taskRate(c.id,arm)}</td>`).join('')}<td><button class="text-button" data-task="${i}">View ${taskRuns.filter(r=>r.case_id===c.id).length} runs →</button></td></tr>`}).join('');
  document.querySelectorAll('[data-task]').forEach(button=>button.addEventListener('click',()=>{
    const c=DATA.cases[Number(button.dataset.task)];
    showDetail(c.title,`<p class="muted">${esc(c.id)} · ${esc(c.fixture_kind)}</p><p>${esc(c.brief)}</p>${study()?.config.task_clarifications?.[c.id]?`<p><b>Shared clarification for this experiment:</b> ${esc(study().config.task_clarifications[c.id])}</p>`:''}<p>${esc(c.challenge)}</p>${c.source_notes?`<details><summary>Source documentation</summary><ul>${c.source_notes.map(n=>`<li>${esc(n)}</li>`).join('')}</ul></details>`:''}${c.catalog_reference_error?`<p class="fail">Catalog reference did not complete. The independently verified answer remains the scoring target.</p>`:''}${c.reference_figure?`<a href="${esc(c.reference_figure)}" target="_blank" rel="noopener">View reference forecast figure ↗</a>`:''}<h3>Attempts & traces</h3>${runListHTML((study()?.runs || []).filter(r=>r.case_id===c.id && ($('model-select').value==='all' || r.model===$('model-select').value)))}<h3>Inputs</h3><p>${esc(c.inputs.join(', '))}</p><h3>Reference workflow</h3><ol>${c.recipe.map(n=>`<li><b>${esc(n.id)}</b> · ${esc(n.skill)}</li>`).join('')}</ol><p class="mono">${c.edges.map(([a,b])=>`${esc(a)} → ${esc(b)}`).join('<br>')}</p><p class="muted">Arrows show artifact dependencies. Independent branches may run in either order.</p><details><summary>Deterministic expected answer</summary>${pretty(c.expected)}<p>Absolute tolerance: ${esc(c.tolerance.atol)} · Relative tolerance: ${esc(c.tolerance.rtol)}. Exact dates, units, keys, and shapes.</p></details><details><summary>Reference arguments and answer schema</summary>${pretty({recipe:c.recipe,answer_schema:c.answer_schema})}</details>`);
    bindRunLinks($('detail-content'));
  }));
}
function setFilters() {
  const runs=study()?.runs || [];
  const previousArm=$('run-arm-select').value;
  $('run-arm-select').innerHTML='<option value="all">All conditions</option>'+ARMS.filter(arm=>(study()?.config.arms || []).includes(arm)).map(arm=>`<option value="${arm}">${esc(LABEL[arm])}</option>`).join('');
  if([...$('run-arm-select').options].some(o=>o.value===previousArm))$('run-arm-select').value=previousArm;
  $("model-select").innerHTML='<option value="all">All models</option>'+(study()?.config.models || []).slice().sort().map(m=>`<option value="${esc(m)}">${esc(modelLabel(m))}</option>`).join('');
  $("case-select").innerHTML='<option value="all">All experiment tasks</option>'+(study()?.config.cases || []).map(id=>`<option value="${esc(id)}">${esc(DATA.cases.find(c=>c.id===id)?.title || id)}</option>`).join('');
  $("conditions").innerHTML=orderedArms().map(arm=>`<label style="--series:${COLOR[arm]}"><input type="checkbox" value="${arm}" ${visibleArms.has(arm)?'checked':''}>${LABEL[arm]}</label>`).join('');
  $("conditions").querySelectorAll('input').forEach(input=>input.addEventListener('change',()=>{input.checked?visibleArms.add(input.value):visibleArms.delete(input.value);renderCharts(aggregate(filteredRuns()))}));
}
function renderStudySelect() { $("study-select").innerHTML=DATA.studies.length ? DATA.studies.map((s,i)=>`<option value="${i}">${esc(studyLabel(s))} · ${s.runs.length}/${s.planned_runs} · ${healthLabel(s)}</option>`).join('') : '<option>No experiments</option>';
$("study-select").value=String(selectedStudy); }
renderStudySelect();
$("study-select").addEventListener('change',e=>{closeDrawer();selectedStudy=Number(e.target.value);setFilters();renderResults()});
$("model-select").addEventListener('change',renderResults);
$("case-select").addEventListener('change',renderResults);
$("run-arm-select").addEventListener('change',()=>renderRuns(filteredRuns()));
$("outcome-select").addEventListener('change',()=>renderRuns(filteredRuns()));
document.querySelectorAll('[data-sort]').forEach(button=>button.addEventListener('click',()=>{if(sortKey===button.dataset.sort)sortDirection*=-1;else{sortKey=button.dataset.sort;sortDirection=sortKey==='success'?-1:1}renderTable(aggregate(filteredRuns()))}));
function setView(view) {
  if (!['results','tasks','runs'].includes(view)) view='results';
  document.querySelectorAll('[data-view]').forEach(button=>{const active=button.dataset.view===view;if(active)button.setAttribute('aria-current','page');else button.removeAttribute('aria-current');$('view-'+button.dataset.view).hidden=!active;});
}
document.querySelectorAll('[data-view]').forEach(button=>button.addEventListener('click',()=>{location.hash=button.dataset.view;setView(button.dataset.view)}));
window.addEventListener('hashchange',()=>setView(location.hash.slice(1)));
let resizeFrame;
window.addEventListener('resize',()=>{cancelAnimationFrame(resizeFrame);resizeFrame=requestAnimationFrame(()=>{renderCharts(aggregate(filteredRuns()));renderScatter(selectedRuns(filteredRuns()))})});
$("condition-help").addEventListener('click',()=>{
  if(['cached-heat-v3','cached-heat-v4'].includes(study()?.config.protocol_version))return showDetail('Experiment conditions',`${study()?.config.skill_policy==='guided-v1'?`<p><b>Guided skills follow-up:</b> Python + skills must read relevant guides before execution and each skill's guide before invoking it. Instructions prefer supported skill operations, with Python available for gaps and recovery. Scientific scores and observed skill adoption are separate.</p><p><b>Limits:</b> $${study().config.max_run_cost_usd} per run · ${study().config.task_timeout_seconds/60} minutes · ${study().config.max_calls} responses · ${study().config.max_executions} executions · no cumulative token limit. Pre-request cost estimates and unknown-charge reservations count against the allowance; actual charges may be lower. $${study().config.max_cost_usd} study ceiling. This experiment changes both prompting and budgets; results are not pooled with earlier runs.</p>`:''}<p>${esc(study()?.config.model_transport_note || "")}</p><p><b>Main comparison:</b> Python + skills versus Python only, with identical budgets. Skills only is a separate diagnostic of the catalog's completeness.</p><p>All conditions receive the same hash-verified raw forecast archive, mounted read-only. Download/setup time is excluded from solve time. Each run starts with an empty work directory. Agent outputs and conversations are never shared.</p><p>Repeated successful skill calls may reuse unchanged artifacts within their own run; cache hits appear in the execution log. Both coding conditions can retain and reuse files. This is a warm-data analysis benchmark, not a network-speed measurement.</p>`);

  if(!study()?.config.arms.includes('skills_only'))return showDetail('Archived experiment conditions',`<p>This pilot made skills available but also allowed Python in the same condition. Reading guides and invoking skills were optional; the traces show whether the agent actually used them.</p><p>The Python only baseline could inspect, execute and revise. The archived one-shot baseline received one response and one execution, with no retry feedback. One-shot is excluded from the primary leaderboard and the new study.</p><p>These historical results are not pooled with the current skills-only protocol.</p>`);
  showDetail('Experiment conditions',`<div class="table-scroll"><table><thead><tr><th>Condition</th><th>Skill access</th><th>Execution feedback</th></tr></thead><tbody><tr><td>Python only</td><td>None</td><td>Inspect, execute, revise</td></tr><tr><td>Skills only</td><td>Required guides + skill scripts; no model code</td><td>Inspect, execute, revise</td></tr></tbody></table></div><p>Skills-only and Python only have the same maximum budgets. The skills agent must read guides and invoke catalog operations. Arbitrary code is disabled; submission only serializes values from its output artifacts.</p><p>The baseline can inspect files, write Python, execute it and revise errors. This models an iterative coding-agent workflow; it is not a claim to run the full Codex or Claude Code product. One-shot results are retained only in archived logs.</p><p>Used skills counts runs with at least one non-help skill invocation, including failed calls. Workflow checks the reference skill sequence separately from answer correctness.</p>`);});
$('failure-help').addEventListener('click',()=>{
  const runs=filteredRuns().filter(r=>r.failure_detail), groups=new Map();
  for(const r of runs){const d=r.failure_detail,key=[d.category,d.provider,d.code].join('|');if(!groups.has(key))groups.set(key,{...d,runs:[]});groups.get(key).runs.push(r)}
  showDetail('Failure diagnostics',`<p>Provider errors describe service or transport failures. Response format errors remain task outcomes. ${study()?.config.provider_retry?`This experiment allows up to ${study().config.provider_retry.max_retries_per_run} bounded provider retries per attempt and fallback within the same model's tested provider allowlist. All waits and reported charges are included. Successful recoveries remain visible in execution logs.`:'This archived experiment stopped on its first terminal error, with no automatic retries or provider fallback.'}</p>${filteredRuns().some(r=>r.provider_retries)?`<h3>Attempts with provider retries</h3>${runListHTML(filteredRuns().filter(r=>r.provider_retries))}`:''}${[...groups.values()].map((g,i)=>`<details class="log-event" open><summary><b>${esc(g.title)}</b> · ${g.runs.length} attempt${g.runs.length===1?'':'s'} · ${esc(g.provider || 'Provider not reported')}</summary><p><code>${esc(g.code)}</code></p><p>${esc(g.message)}</p>${runListHTML(g.runs)}</details>`).join('') || '<p>No terminal provider or response errors in this selection.</p>'}`);bindRunLinks($('detail-content'));
});
$('close-drawer').addEventListener('click',closeDrawer);
$('drawer-back').addEventListener('click',()=>{const old=drawerHistory.pop();if(!old)return;$('detail-title').textContent=old.title;$('detail-content').replaceChildren(...old.nodes);$('detail-drawer').scrollTop=old.scroll;$('drawer-back').hidden=!drawerHistory.length;});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!$('detail-drawer').hidden)closeDrawer();});
document.querySelectorAll('[data-metric]').forEach(button=>button.addEventListener('click',()=>{chartMetric=button.dataset.metric;document.querySelectorAll('[data-metric]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));renderCharts(aggregate(filteredRuns()));}));
$("pins").textContent=`Catalog ${DATA.catalog_commit || 'unavailable'} · Core ${DATA.core_commit || 'unavailable'}`;
$('result-basis').addEventListener('change',e=>{resultBasis=e.target.value;renderResults()});
let refreshing=false;
function refreshData() {
  if(window.BENCHMARK_SNAPSHOT || refreshing)return;refreshing=true;
  const script=document.createElement('script');script.src='data.js?refresh='+Date.now();
  script.onload=()=>{
    const next=window.BENCHMARK_DATA, id=study()?.study_id, model=$('model-select').value, task=$('case-select').value;
    Object.assign(DATA,next);selectedStudy=Math.max(0,DATA.studies.findIndex(s=>s.study_id===id));
    renderStudySelect();setFilters();$('model-select').value=model;$('case-select').value=task;renderResults();script.remove();refreshing=false;
  };
  script.onerror=()=>{script.remove();refreshing=false;$('study-status').textContent='Refresh unavailable · showing saved data'};
  document.head.appendChild(script);
}
$('refresh-data').addEventListener('click',refreshData);
if(window.BENCHMARK_SNAPSHOT){
  $('refresh-data').hidden=true;
}else{
  setInterval(()=>{if(!document.hidden)refreshData()},15000);
}
setFilters();renderResults();renderTasks();setView(location.hash.slice(1));
