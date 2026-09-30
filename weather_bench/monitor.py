"""Refresh the static report as a long study advances; no model requests."""
import json
import subprocess
import sys
import time
from pathlib import Path
from .catalog import ROOT
from .report import export_dashboard,MODEL_PROFILES
from .health import output_stem


def refresh(path):
    raw=json.loads(path.read_text())
    export_dashboard()
    data=json.loads((ROOT/'docs/data.json').read_text())
    study=next(s for s in data['studies'] if s['study_id']==raw['study_id'])
    small=study['config'].get('study_role')=='small-model-extension'
    e2e=study['config'].get('study_role')=='end-to-end'
    stem=output_stem(study['config'])
    n=len(study['runs']);finished=bool(study.get('finished_at'))
    state='Complete' if finished and n==study['planned_runs'] else 'Partial — stopped' if finished else study.get('health',{}).get('state','stopped').title()
    lines=['# '+('End-to-end real-forecast study' if e2e else 'Small-model comparison' if small else 'Expanded skills-only study'), '',f"**{state}: {n}/{study['planned_runs']} recorded attempts.** Study `{study['study_id']}`.",'',
           f"{len(study['config']['models'])} models, {len(study['config']['cases'])} fixed diagnostic tasks, skills-only versus Python only (Python with execution feedback), one repetition. One-shot is absent. Operator interruptions are unscored; provider errors remain in operational success rates. Matched capability tests exclude provider errors and interruptions.", '',
           '| Model | Condition | Passed / scored | Median seconds | Mean tokens | USD / attempt | USD / success | Provider errors |',
           '|---|---|---:|---:|---:|---:|---:|---:|']
    def money(value):return 'Unknown' if value is None else f'${value:.4f}'
    for row in study['condition_statistics']:
        name=MODEL_PROFILES.get(row['model'],{}).get('label',row['model'])
        arm={'skills_only':'Skills only','skills':'Python + skills','python':'Python only'}.get(row['arm'],row['arm'])
        per_success='—' if not row['passed'] else money(row['cost_per_success_usd'])
        lines.append(f"| {name} | {arm} | {row['passed']}/{row['scored']} | {row['median_seconds']:.1f} | {row['mean_tokens']:,.0f} | {money(row['cost_per_attempt_usd'])} | {per_success} | {row['provider_errors']} |")
    lines+=['',f"Reported study charges: **${study['ledger']['spent']:.4f}**. Unconfirmed charges are additional; the ${study['ledger'].get('budget_reserve_usd',0):.4f} reserve is a budget precaution, not billed spend. Preflight charges are recorded separately in `results/preflight-v2.json`.",'',
            '## Paired comparisons','', '| Model | Evaluable pairs | Skills wins | Python only wins | Exact McNemar p | Holm-adjusted p |', '|---|---:|---:|---:|---:|---:|']
    def pvalue(value):return '—' if value is None else f'{value:.4f}'
    for row in study['paired_statistics']:
        name=MODEL_PROFILES.get(row['model'],{}).get('label',row['model'])
        lines.append(f"| {name} | {row['pairs']} | {row['skills_only_wins']} | {row['python_only_wins']} | {pvalue(row['mcnemar_exact_p'])} | {pvalue(row.get('mcnemar_holm_p'))} |")
    lines+=['', 'These are exploratory comparisons on a small, deliberately chosen synthetic task set. An insignificant difference does not establish equivalence. Interim rows have unequal coverage and should not be used to rank models.', '',
            '## Interpretation boundaries', '',
            '- Scientific calculations, output-contract failures, action-format rejections, and provider failures are different phenomena. Inspect the linked run traces before attributing a failed task to weather reasoning.',
            '- The skills-only host requires earlier guide reads and catalog calls, blocks model-written Python, and serializes answers from produced artifacts. Early failures can occur before any skill is executed.',
            '- The Python comparator can inspect inputs, execute programs, receive errors, and retry. The JSON-action harness approximates that workflow; it does not run the complete Codex or Claude Code clients.',
            '- Reading long guides, repeated context, CLI discovery and extra calls can increase resource use. Provider-applied caching is recorded, but explicit cache breakpoints are not requested.',
            '- This study does not establish operational forecast quality in Africa, local-hosting feasibility, or performance on African networks. See [model review](MODEL_REVIEW.md), [methodology](METHODOLOGY.md), and [statistics](STATISTICS.md).', '',
            'The original availability-only pilot and its explanation remain in [FINDINGS.md](FINDINGS.md). The [dashboard](docs/index.html) contains task briefs, exact answers, clickable comparisons, and per-run traces.']
    findings='E2E_FINDINGS.md' if e2e else 'SMALL_MODEL_FINDINGS.md' if small else 'EXPANDED_FINDINGS.md'
    if study['config'].get('output_stem'):findings=stem.upper().replace('-','_')+'_FINDINGS.md'
    if e2e:
        if study.get('quality'):
            lines[2:2]=['**Provisional:** '+study['quality']['note'], '', 'See END_TO_END.md and results/rainfall-semantics-audit.json for the independent sensitivity check. Registered scores are unchanged.', '']
        lines=[line.replace('fixed diagnostic tasks','real-forecast end-to-end tasks').replace('synthetic task set','archived real-forecast task set') for line in lines]
        lines+=['', 'Live forecast retrieval and plotting are included in completion time. Source versions are checked before and after each attempt. Heat task has a documented catalog reference defect; a correct alternative remains eligible. See END_TO_END.md.']
    if study['config'].get('protocol_version') in ('cached-heat-v3','cached-heat-v4'):
        lines=[line.replace('skills-only versus Python only (Python with execution feedback)', 'Python + skills versus Python only (main comparison), plus Skills only (diagnostic)').replace('Live forecast retrieval and plotting are included in completion time. Source versions are checked before and after each attempt. Heat task has a documented catalog reference defect; a correct alternative remains eligible. See END_TO_END.md.', 'Raw forecast bytes are served from a verified read-only local cache. Plotting is timed; download and setup are excluded. Catalog defects are patched in a separate version. Agents share no intermediate artifacts. See configs/refined-heat-v3.json.') for line in lines]
    if study['config'].get('model_transport_note'):
        lines += ['',study['config']['model_transport_note']]
    if study['config'].get('exclusion_note'):
        lines[4:4]=[study['config']['exclusion_note'],'']
    if small:
        lines=[line.replace('results/preflight-v2.json','results/preflight-small-models.json') for line in lines]
    if study['config'].get('preflight_report'):
        lines=[line.replace('results/preflight-v2.json',study['config']['preflight_report']) for line in lines]
    (ROOT/findings).write_text('\n'.join(lines)+'\n')
    (ROOT/f'results/{stem}-summary.json').write_text(json.dumps({'study_id':study['study_id'],'state':state,'recorded_attempts':n,'planned_attempts':study['planned_runs'],'condition_statistics':study['condition_statistics'],'paired_statistics':study['paired_statistics']},indent=2)+'\n')
    print(f'{state}: {n}/{study["planned_runs"]}; exports refreshed',flush=True)
    return finished


def main():
    path=Path(sys.argv[1]).resolve();last=None;last_refresh=0
    while True:
        stamp=path.stat().st_mtime_ns
        if stamp!=last or time.monotonic()-last_refresh>=15:
            try:
                finished=refresh(path)
            except json.JSONDecodeError:
                time.sleep(1);continue  # the runner may be midway through writing
            last=stamp;last_refresh=time.monotonic()
            if finished:
                import os
                env=dict(os.environ,PYTHONPATH=str(ROOT))
                subprocess.run([sys.executable,str(ROOT/'scripts/audit_study.py'),str(path)],cwd=ROOT,env=env,check=True)
                return
        time.sleep(5)

if __name__=='__main__':main()
