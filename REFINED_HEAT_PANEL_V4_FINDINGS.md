# End-to-end real-forecast study

**Complete: 18/18 recorded attempts.** Study `20260930T155730Z-ae0a07`.

GPT-6 Astra is excluded from this comparison because it helped develop the benchmark, tasks, and harness. This avoids evaluating the benchmark-authoring model; it does not establish that the remaining evaluation is free of design bias. Earlier Astra runs remain in archived experiments.

6 models, 1 real-forecast end-to-end tasks, Python + skills versus Python only (main comparison), plus Skills only (diagnostic), one repetition. One-shot is absent. Operator interruptions are unscored; provider errors remain in operational success rates. Matched capability tests exclude provider errors and interruptions.

| Model | Condition | Passed / scored | Median seconds | Mean tokens | USD / attempt | USD / success | Provider errors |
|---|---|---:|---:|---:|---:|---:|---:|
| Claude Fable 5.1 | Python only | 1/1 | 37.0 | 11,097 | $0.1727 | $0.1727 | 0 |
| Claude Fable 5.1 | Python + skills | 1/1 | 27.3 | 26,481 | $0.3130 | $0.3130 | 0 |
| Claude Fable 5.1 | Skills only | 1/1 | 70.6 | 109,617 | $1.1947 | $1.1947 | 0 |
| Claude Sonnet 5.5 | Python only | 1/1 | 55.4 | 43,960 | $0.1672 | $0.1672 | 0 |
| Claude Sonnet 5.5 | Python + skills | 1/1 | 28.3 | 51,603 | $0.1211 | $0.1211 | 0 |
| Claude Sonnet 5.5 | Skills only | 0/1 | 64.7 | 205,920 | $0.4486 | — | 0 |
| DeepSeek V4.1 Flash | Python only | 1/1 | 14.5 | 14,773 | $0.0015 | $0.0015 | 0 |
| DeepSeek V4.1 Flash | Python + skills | 1/1 | 23.2 | 39,953 | $0.0034 | $0.0034 | 0 |
| DeepSeek V4.1 Flash | Skills only | 1/1 | 157.3 | 189,007 | $0.0181 | $0.0181 | 0 |
| Gemini 3.1 Flash-Lite | Python only | 1/1 | 22.0 | 23,725 | $0.0113 | $0.0113 | 0 |
| Gemini 3.1 Flash-Lite | Python + skills | 1/1 | 30.2 | 63,712 | $0.0212 | $0.0212 | 0 |
| Gemini 3.1 Flash-Lite | Skills only | 0/1 | 105.5 | 212,022 | $0.0685 | — | 0 |
| Ministral 3 3B | Python only | 0/1 | 155.0 | 219,805 | $0.0061 | — | 0 |
| Ministral 3 3B | Python + skills | 0/1 | 77.3 | 210,995 | $0.0050 | — | 0 |
| Ministral 3 3B | Skills only | 0/1 | 35.8 | 220,615 | $0.0041 | — | 0 |
| Qwen3.5 9B | Python only | 1/1 | 485.0 | 184,115 | $0.0211 | $0.0211 | 0 |
| Qwen3.5 9B | Python + skills | 0/1 | 600.3 | 142,337 | Unknown | — | 0 |
| Qwen3.5 9B | Skills only | 0/1 | 526.3 | 210,364 | $0.0240 | — | 0 |

Reported study charges: **$2.6171**. Unconfirmed charges are additional; the $0.0276 reserve is a budget precaution, not billed spend. Preflight charges are recorded separately in `results/preflight-refined-panel-v4.json`.

## Paired comparisons

| Model | Evaluable pairs | Skills wins | Python only wins | Exact McNemar p | Holm-adjusted p |
|---|---:|---:|---:|---:|---:|
| Claude Fable 5.1 | 1 | 0 | 0 | 1.0000 | 1.0000 |
| Claude Sonnet 5.5 | 1 | 0 | 0 | 1.0000 | 1.0000 |
| DeepSeek V4.1 Flash | 1 | 0 | 0 | 1.0000 | 1.0000 |
| Gemini 3.1 Flash-Lite | 1 | 0 | 0 | 1.0000 | 1.0000 |
| Ministral 3 3B | 1 | 0 | 0 | 1.0000 | 1.0000 |
| Qwen3.5 9B | 1 | 0 | 1 | 1.0000 | 1.0000 |

These are exploratory comparisons on a small, deliberately chosen archived real-forecast task set. An insignificant difference does not establish equivalence. Interim rows have unequal coverage and should not be used to rank models.

## Interpretation boundaries

- Scientific calculations, output-contract failures, action-format rejections, and provider failures are different phenomena. Inspect the linked run traces before attributing a failed task to weather reasoning.
- The skills-only host requires earlier guide reads and catalog calls, blocks model-written Python, and serializes answers from produced artifacts. Early failures can occur before any skill is executed.
- The Python comparator can inspect inputs, execute programs, receive errors, and retry. The JSON-action harness approximates that workflow; it does not run the complete Codex or Claude Code clients.
- Reading long guides, repeated context, CLI discovery and extra calls can increase resource use. Provider-applied caching is recorded, but explicit cache breakpoints are not requested.
- This study does not establish operational forecast quality in Africa, local-hosting feasibility, or performance on African networks. See [model review](MODEL_REVIEW.md), [methodology](METHODOLOGY.md), and [statistics](STATISTICS.md).

The original availability-only pilot and its explanation remain in [FINDINGS.md](FINDINGS.md). The [dashboard](docs/index.html) contains task briefs, exact answers, clickable comparisons, and per-run traces.

Raw forecast bytes are served from a verified read-only local cache. Plotting is timed; download and setup are excluded. Catalog defects are patched in a separate version. Agents share no intermediate artifacts. See configs/refined-heat-v3.json.
