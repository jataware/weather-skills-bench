# End-to-end real-forecast study

**Complete: 12/12 recorded attempts.** Study `20260930T170131Z-423336`.

GPT-6 Astra is excluded from this comparison because it helped develop the benchmark, tasks, and harness. This avoids evaluating the benchmark-authoring model; it does not establish that the remaining evaluation is free of design bias. Earlier Astra runs remain in archived experiments.

4 models, 1 real-forecast end-to-end tasks, Python + skills versus Python only (main comparison), plus Skills only (diagnostic), one repetition. One-shot is absent. Operator interruptions are unscored; provider errors remain in operational success rates. Matched capability tests exclude provider errors and interruptions.

| Model | Condition | Passed / scored | Median seconds | Mean tokens | USD / attempt | USD / success | Provider errors |
|---|---|---:|---:|---:|---:|---:|---:|
| Claude Sonnet 5.5 | Python only | 1/1 | 23.2 | 32,984 | $0.0834 | $0.0834 | 0 |
| Claude Sonnet 5.5 | Python + skills | 1/1 | 97.7 | 154,224 | $0.4533 | $0.4533 | 0 |
| Claude Sonnet 5.5 | Skills only | 1/1 | 58.2 | 236,256 | $0.5013 | $0.5013 | 0 |
| Gemini 3.1 Flash-Lite | Python only | 1/1 | 24.3 | 29,728 | $0.0127 | $0.0127 | 0 |
| Gemini 3.1 Flash-Lite | Python + skills | 1/1 | 28.2 | 73,696 | $0.0183 | $0.0183 | 0 |
| Gemini 3.1 Flash-Lite | Skills only | 0/1 | 236.1 | 1,971,984 | $0.2031 | — | 0 |
| Ministral 3 3B | Python only | 0/1 | 134.6 | 154,319 | $0.0037 | — | 0 |
| Ministral 3 3B | Python + skills | 0/1 | 104.0 | 600,708 | $0.0107 | — | 0 |
| Ministral 3 3B | Skills only | 0/1 | 154.1 | 2,347,709 | $0.0278 | — | 0 |
| Qwen3.5 9B | Python only | 0/1 | 169.7 | 41,929 | $0.0053 | — | 1 |
| Qwen3.5 9B | Python + skills | 0/1 | 114.5 | 4,251 | $0.0005 | — | 1 |
| Qwen3.5 9B | Skills only | 0/1 | 9.1 | 0 | $0.0000 | — | 1 |

Reported study charges: **$1.3202**. Unconfirmed charges are additional; the $0.0000 reserve is a budget precaution, not billed spend. Preflight charges are recorded separately in `results/preflight-v2.json`.

## Paired comparisons

| Model | Evaluable pairs | Skills wins | Python only wins | Exact McNemar p | Holm-adjusted p |
|---|---:|---:|---:|---:|---:|
| Claude Sonnet 5.5 | 1 | 0 | 0 | 1.0000 | 1.0000 |
| Gemini 3.1 Flash-Lite | 1 | 0 | 0 | 1.0000 | 1.0000 |
| Ministral 3 3B | 1 | 0 | 0 | 1.0000 | 1.0000 |

These are exploratory comparisons on a small, deliberately chosen archived real-forecast task set. An insignificant difference does not establish equivalence. Interim rows have unequal coverage and should not be used to rank models.

## Interpretation boundaries

- Scientific calculations, output-contract failures, action-format rejections, and provider failures are different phenomena. Inspect the linked run traces before attributing a failed task to weather reasoning.
- The skills-only host requires earlier guide reads and catalog calls, blocks model-written Python, and serializes answers from produced artifacts. Early failures can occur before any skill is executed.
- The Python comparator can inspect inputs, execute programs, receive errors, and retry. The JSON-action harness approximates that workflow; it does not run the complete Codex or Claude Code clients.
- Reading long guides, repeated context, CLI discovery and extra calls can increase resource use. Provider-applied caching is recorded, but explicit cache breakpoints are not requested.
- This study does not establish operational forecast quality in Africa, local-hosting feasibility, or performance on African networks. See [model review](MODEL_REVIEW.md), [methodology](METHODOLOGY.md), and [statistics](STATISTICS.md).

The original availability-only pilot and its explanation remain in [FINDINGS.md](FINDINGS.md). The [dashboard](docs/index.html) contains task briefs, exact answers, clickable comparisons, and per-run traces.

Raw forecast bytes are served from a verified read-only local cache. Plotting is timed; download and setup are excluded. Catalog defects are patched in a separate version. Agents share no intermediate artifacts. See configs/refined-heat-v3.json.
