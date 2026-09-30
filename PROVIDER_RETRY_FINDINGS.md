# End-to-end real-forecast study

**Complete: 15/15 recorded attempts.** Study `20260930T133554Z-9c118f`.

6 models, 3 real-forecast end-to-end tasks, skills-only versus No Skills (Python with execution feedback), one repetition. One-shot is absent. Operator interruptions are unscored; provider errors remain in operational success rates. Matched capability tests exclude provider errors and interruptions.

| Model | Condition | Passed / scored | Median seconds | Mean tokens | USD / attempt | USD / success | Provider errors |
|---|---|---:|---:|---:|---:|---:|---:|
| Claude Fable 5.1 | No Skills | 1/1 | 41.7 | 19,306 | $0.2666 | $0.2666 | 0 |
| DeepSeek V4.1 Flash | Skills only | 0/2 | 599.5 | 363,328 | $0.0382 | — | 0 |
| Gemini 3.1 Flash-Lite | No Skills | 0/1 | 54.4 | 64,888 | $0.0258 | — | 0 |
| Ministral 3 3B | No Skills | 0/2 | 106.7 | 124,658 | $0.0028 | — | 1 |
| Ministral 3 3B | Skills only | 0/3 | 62.9 | 364,034 | $0.0058 | — | 0 |
| GPT-6 Astra | No Skills | 2/2 | 60.7 | 31,202 | $0.2388 | $0.2388 | 0 |
| Qwen3.5 9B | No Skills | 0/2 | 245.3 | 30,197 | $0.0034 | — | 2 |
| Qwen3.5 9B | Skills only | 0/2 | 1200.3 | 172,760 | Unknown | — | 0 |

Reported study charges: **$0.9127**. Unconfirmed charges are additional; the $0.1496 reserve is a budget precaution, not billed spend. Preflight charges are recorded separately in `results/streaming-provider-probes.json`.

## Paired comparisons

| Model | Evaluable pairs | Skills wins | No Skills wins | Exact McNemar p | Holm-adjusted p |
|---|---:|---:|---:|---:|---:|
| Ministral 3 3B | 1 | 0 | 0 | 1.0000 | 1.0000 |

These are exploratory comparisons on a small, deliberately chosen archived real-forecast task set. An insignificant difference does not establish equivalence. Interim rows have unequal coverage and should not be used to rank models.

## Interpretation boundaries

- Scientific calculations, output-contract failures, action-format rejections, and provider failures are different phenomena. Inspect the linked run traces before attributing a failed task to weather reasoning.
- The skills-only host requires earlier guide reads and catalog calls, blocks model-written Python, and serializes answers from produced artifacts. Early failures can occur before any skill is executed.
- The Python comparator can inspect inputs, execute programs, receive errors, and retry. The JSON-action harness approximates that workflow; it does not run the complete Codex or Claude Code clients.
- Reading long guides, repeated context, CLI discovery and extra calls can increase resource use. Provider-applied caching is recorded, but explicit cache breakpoints are not requested.
- This study does not establish operational forecast quality in Africa, local-hosting feasibility, or performance on African networks. See [model review](MODEL_REVIEW.md), [methodology](METHODOLOGY.md), and [statistics](STATISTICS.md).

The original availability-only pilot and its explanation remain in [FINDINGS.md](FINDINGS.md). The [dashboard](docs/index.html) contains task briefs, exact answers, clickable comparisons, and per-run traces.

Live forecast retrieval and plotting are included in completion time. Source versions are checked before and after each attempt. Heat task has a documented catalog reference defect; a correct alternative remains eligible. See END_TO_END.md.
