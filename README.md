# Weather Skills Benchmark

The current experiment compares **Python only**, **Skills only**, and **Python + skills** on a two-week Kenya heat outlook using verified, cached ECMWF forecast data. Four models receive the same $2 per-run allowance and 30-minute limit, with no cumulative token cap. The hybrid condition requires guide discovery and prefers supported skill operations while retaining Python for recovery. See [guided results](GUIDED_HEAT_V5_FINDINGS.md), [provider recovery results](GUIDED_HEAT_V5_RECOVERY_FINDINGS.md), and [methodology](METHODOLOGY.md). The recovery view contains all 12 outcomes and preserves the original provider-failed attempts.

Earlier [live-retrieval tasks](END_TO_END.md) start agents without weather data and include downloading real archives. The cached experiment isolates analysis from download latency and uses a separately pinned, repaired catalog. The original live-data cohorts remain in [E2E_FINDINGS.md](E2E_FINDINGS.md), the synthetic comparison in [EXPANDED_FINDINGS.md](EXPANDED_FINDINGS.md), and the initial pilot in [FINDINGS.md](FINDINGS.md). These different protocols are not pooled.

For a long-running study, a separate local monitor refreshes the static dashboard and findings after every saved attempt, then audits the completed dataset:

```bash
.venv/bin/python -m weather_bench.monitor results/studies/STUDY_ID.json
```

The monitor makes no model requests. The dashboard refreshes every 15 seconds, preserves filters, and shows worker heartbeat freshness. Completion and missing outcomes are visible in a clickable model/task coverage table. Final integrity audits are written to `results/e2e-audit.json`, `results/expanded-audit.json`, or `results/small-model-audit.json`, depending on the cohort.

The benchmark exercises the actual [weather-skills-catalog](https://github.com/weather-skills/weather-skills-catalog) scripts against independent numerical oracles. Original availability-only and one-shot conditions remain archived; skill adoption is measured separately from scientific correctness.

The [dashboard](docs/index.html) presents model success, solve time, tokens, billed cost, matched comparisons, task briefs, expected answers, and observed skill sequences, a clickable tokens-versus-cost plot, and per-run execution/model-call logs. It opens directly in a browser and is ready for GitHub Pages. No key or backend is needed to view it.

## What is included

- Ten synthetic diagnostics, three live-retrieval forecast tasks, and a cached heat-outlook task, with public briefs in `cases/` and frozen inputs in `fixtures/`.
- Independent NumPy/stdlib answer calculations and actual catalog reference pipelines.
- Numerical grading separate from skill-order and artifact-dependency checks.
- Fresh directories and conversations for every run. Diagnostic containers have no network; end-to-end containers can reach only approved public data hosts through a proxy.
- An OpenRouter agent loop, three current comparison arms, archived historical arms, and optional `docs_only`.
- A static dashboard and manually triggered GitHub Pages deployment workflow.

All ten reference pipelines pass locally and in containers; independent one-program Python solutions also pass all ten cases. Reference validation is not an LLM performance result. The initial model pilot uses three cases and one repetition; it is exploratory, not a statistically supported ranking.

## Reproduce locally

Requires Python 3.12, Git, and Docker. Keep the catalog checkout next to this repository:

```bash
git clone https://github.com/weather-skills/weather-skills-catalog ../weather-skills-catalog
git -C ../weather-skills-catalog checkout 1a0af7de3bba2d7a6c4fe67f291eb0e58640b5f5
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.lock
.venv/bin/python -m weather_bench.cli reference
.venv/bin/python -m pytest -q
.venv/bin/python -m weather_bench.cli build-images
.venv/bin/python -m weather_bench.cli validate-containers
.venv/bin/python -m weather_bench.cli validate-python
```

The catalog and core are pinned separately in `catalog.lock.json`; Python dependencies are pinned in `requirements.lock`. No catalog source is modified. `fixtures/manifest.json` records content hashes. `freeze` regenerates the byte-stable input archives when intentionally revising the benchmark.

## Archived synthetic comparison

The expanded v2 study runs six models (Claude Fable 5.1, GPT-6 Astra, Claude Sonnet 5.5, Gemini 3.1 Flash-Lite, DeepSeek V4.1 Flash, Qwen3.5 9B) across all ten tasks and two conditions: 120 attempts. Skill guides are required, model-written code is disabled in the skills arm, and artifact submission is validated against successful skill outputs. All ten references pass with this restriction.

The landing page has clickable success/time/token/cost bars, Wilson intervals, cost per successful task, and paired exact McNemar tests with Holm adjustment. Task and run details open in non-modal drawers, including execution output, model responses and the feedback shown to each request. See [STATISTICS.md](STATISTICS.md) for interpretation.

## Run models

For the provider failure diagnosis, live compatibility checks and recovery settings, see [PROVIDER_RECOVERY.md](PROVIDER_RECOVERY.md).

Put `OPENROUTER_API_KEY=...` in `.env` (the existing lowercase `openrouter_api_key` is also accepted). The key stays in the host HTTP client and never enters an evaluation container, dashboard, or Git.

```bash
# Real forecast tasks with tested routes and bounded transport recovery
.venv/bin/python -m weather_bench.cli study --config configs/end-to-end-recovery-v2.json
# Synthetic diagnostic comparison
# .venv/bin/python -m weather_bench.cli study --config configs/expanded-v2.json
.venv/bin/python -m weather_bench.cli export
open docs/index.html
```

An interrupted study can be resumed with `study --config configs/pilot.json --resume results/studies/<id>.json`. Completed runs are retained in a new auditable study record. Changing a provider on resume is allowed only if that model had no agent actions; all of its conditions are then rescheduled together, with rejected requests preserved separately. This is not a best-of-N retry mechanism.

Edit the configuration to choose models, explicit providers, cases, repetitions, and resource limits. The completed 27-attempt pilot uses Sonnet 4.6 and Gemini 2.5 Flash (closed weights), plus Qwen3 30B A3B Instruct (open weights). DeepSeek V3.2 partial results are retained separately because of repeated provider failures. `configs/pilot.json` retains the original four-model matrix; `configs/pilot-available.json` runs the completed three-model design. Read [FINDINGS.md](FINDINGS.md) before interpreting the results and [MODEL_REVIEW.md](MODEL_REVIEW.md) for the researched model selection and deployment considerations. Provider availability and prices are resolved at study start. Historical configurations disable automatic fallback. The recovery configuration allows fallback within the same model and an explicit tested provider allowlist; model substitution is never automatic.

`max_cost_usd` is a **stop threshold on reported spend**, checked before each request. One in-flight request can cross it. Without an explicit reserve policy, an ambiguous API failure or missing usage cost stops the study. Configurations using `unknown_cost_policy: reserve` retain incomplete billing and a conservative allowance against the spend threshold; they never count an unknown charge as zero. Definite request rejections are recorded as infrastructure errors. A provider-side account/key cap is needed for a strict monetary ceiling. Raw responses and full run records are local under ignored `results/raw/` and `results/studies/`; shareable records are preserved under `results/published/` and exported to `docs/data.json` and `docs/data.js`. Exporting from a fresh clone preserves those published records.

`configs/full.json` includes all ten cases and three repetitions (360 planned runs). Add `docs_only` for a fourth condition. `configs/full-batched.json` enables sequential action batching for a separate experiment, reducing unnecessary model round trips while preserving individual invocation traces. The existing pilot did not use batching. Keep the one-shot arm separate from the matched-budget skills-versus-Python comparison. Do not merge experiments with different prompts, budgets, or provider routes into one ranking.

## Publish

The dashboard is entirely static. Push the reviewed repository, enable **GitHub Pages → GitHub Actions**, then run **Publish benchmark dashboard**. This workflow deploys only `docs/`, never `.env`, raw traces, or the answer-key Python modules. No deployment has been performed automatically.

Read [METHODOLOGY.md](METHODOLOGY.md) for experiment design and limitations, and [CATALOG_REVIEW.md](CATALOG_REVIEW.md) for catalog coverage and pinned-runtime findings.

## Share a single offline HTML file

```bash
.venv/bin/python scripts/bundle_dashboard.py
```

Share `docs/weather-skills-benchmark.html` by itself. It embeds the current public
results, charts, run logs, forecast images, styles, scripts, and methodology.
No server, network connection, API key, or companion folder is required.
This is a dated snapshot: automatic refresh is disabled and unfinished studies
are labelled partial snapshots. Rebuild it to include newer results. JSON and
individual run-log downloads embed their referenced images as data URLs.
Use `--output /path/to/report.html` to choose another filename.

## Focused cached-data heat pilot

The current `cached-heat-v4` experiment uses one real ECMWF heat-outlook task and three conditions: **Skills + Python**, **No Skills**, and **Skills only**. The primary comparison keeps Python available in both arms. The strict condition diagnoses catalog completeness. Earlier studies keep their original pins and results.

```bash
.venv/bin/python scripts/prepare_refined.py
.venv/bin/python -m weather_bench.cli study --config configs/refined-heat-v4.json
```

Preparation applies `patches/catalog-reliability-v3.patch` in a separate sibling catalog worktree, verifies `catalog.refined.lock.json`, builds separate offline images, verifies cached raw objects, and checks the skill workflow against an independent Python oracle. It requires the original catalog checkout and E2E base images. The source snapshot is already checked in; repeated downloads are unnecessary. Reference validation is reused only when the source, catalog, task, expected answer, image IDs, reference code and validator hashes match. Pass `--force` to `scripts/validate_refined.py` to execute validation again.

Agents receive only the immutable raw archive at `/inputs/archive.zarr` and an empty private `/work`. Successful identical skill calls can reuse unchanged outputs within their own run. Failed calls and changed inputs/outputs invalidate reuse; artifacts never transfer between agents. `results/refined-reference.json` records oracle checks, regression results and measured cache timing. The dashboard labels cache hits in execution logs.

The first focused pilot completed all nine runs with no provider errors (about $0.77). It also exposed two additional temperature paths: rolling aggregation and full-axis median over quantified lazy arrays. Their independently validated fixes are in `patches/rolling-temperature-followup.patch`; reproduce with `.venv/bin/python scripts/validate_rolling_followup.py` after preparing v3. This separate image does not modify the completed pilot's catalog or scores. See `results/refined-known-issues.json` and `results/rolling-followup-validation.json`.

The prepared v4 profile includes both follow-up fixes and has its own independently validated reference in `results/refined-reference-v4.json`. The nine recorded pilot attempts used v3; they are not represented as tests of the later fixes.
