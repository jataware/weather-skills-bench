# End-to-end real-forecast study

**Complete: 12/12 recorded attempts.** Study `20260930T163942Z-f41875`.

GPT-6 Astra is excluded from this comparison because it helped develop the benchmark, tasks, and harness. This avoids evaluating the benchmark-authoring model; it does not establish that the remaining evaluation is free of design bias. Earlier Astra runs remain in archived experiments.

4 models, 1 real-forecast end-to-end tasks, Python + skills versus Python only (main comparison), plus Skills only (diagnostic), one repetition. One-shot is absent. Operator interruptions are unscored; provider errors remain in operational success rates. Matched capability tests exclude provider errors and interruptions.

| Model | Condition | Passed / scored | Median seconds | Mean tokens | USD / attempt | USD / success | Provider errors |
|---|---|---:|---:|---:|---:|---:|---:|
| Llama 3.1 8B | Python only | 0/1 | 600.4 | 0 | Unknown | — | 0 |
| Llama 3.1 8B | Python + skills | 0/1 | 600.2 | 0 | Unknown | — | 0 |
| Llama 3.1 8B | Skills only | 0/1 | 600.3 | 41,015 | Unknown | — | 0 |
| Llama 3.2 1B | Python only | 0/1 | 600.3 | 52,743 | Unknown | — | 0 |
| Llama 3.2 1B | Python + skills | 0/1 | 212.1 | 203,259 | $0.0076 | — | 0 |
| Llama 3.2 1B | Skills only | 0/1 | 104.7 | 203,259 | $0.0061 | — | 0 |
| Llama 3.2 3B | Python only | 0/1 | 93.3 | 163,547 | Unknown | — | 0 |
| Llama 3.2 3B | Python + skills | 0/1 | 6.1 | 8,479 | $0.0007 | — | 0 |
| Llama 3.2 3B | Skills only | 0/1 | 63.5 | 221,121 | $0.0136 | — | 0 |
| Qwen2.5 7B | Python only | 0/1 | 70.6 | 46,492 | $0.0052 | — | 0 |
| Qwen2.5 7B | Python + skills | 0/1 | 166.0 | 203,967 | $0.0217 | — | 0 |
| Qwen2.5 7B | Skills only | 0/1 | 171.4 | 209,953 | $0.0226 | — | 0 |

Reported study charges: **$0.0962**. Unconfirmed charges are additional; the $0.0962 reserve is a budget precaution, not billed spend. Preflight charges are recorded separately in `results/preflight-refined-small-v4.json`.

## Paired comparisons

| Model | Evaluable pairs | Skills wins | Python only wins | Exact McNemar p | Holm-adjusted p |
|---|---:|---:|---:|---:|---:|
| Llama 3.1 8B | 1 | 0 | 0 | 1.0000 | 1.0000 |
| Llama 3.2 1B | 1 | 0 | 0 | 1.0000 | 1.0000 |
| Llama 3.2 3B | 1 | 0 | 0 | 1.0000 | 1.0000 |
| Qwen2.5 7B | 1 | 0 | 0 | 1.0000 | 1.0000 |

These are exploratory comparisons on a small, deliberately chosen archived real-forecast task set. An insignificant difference does not establish equivalence. Interim rows have unequal coverage and should not be used to rank models.

## Interpretation boundaries

- Scientific calculations, output-contract failures, action-format rejections, and provider failures are different phenomena. Inspect the linked run traces before attributing a failed task to weather reasoning.
- The skills-only host requires earlier guide reads and catalog calls, blocks model-written Python, and serializes answers from produced artifacts. Early failures can occur before any skill is executed.
- The Python comparator can inspect inputs, execute programs, receive errors, and retry. The JSON-action harness approximates that workflow; it does not run the complete Codex or Claude Code clients.
- Reading long guides, repeated context, CLI discovery and extra calls can increase resource use. Provider-applied caching is recorded, but explicit cache breakpoints are not requested.
- This study does not establish operational forecast quality in Africa, local-hosting feasibility, or performance on African networks. See [model review](MODEL_REVIEW.md), [methodology](METHODOLOGY.md), and [statistics](STATISTICS.md).

The original availability-only pilot and its explanation remain in [FINDINGS.md](FINDINGS.md). The [dashboard](docs/index.html) contains task briefs, exact answers, clickable comparisons, and per-run traces.

Raw forecast bytes are served from a verified read-only local cache. Plotting is timed; download and setup are excluded. Catalog defects are patched in a separate version. Agents share no intermediate artifacts. See configs/refined-heat-v3.json.

Llama 3.2 1B and 3B endpoints do not support API-enforced JSON mode. They receive the same JSON-action instructions, parsing, and recovery feedback, without the unsupported response_format parameter. This endpoint difference is retained in configuration and applies equally to all three conditions.
