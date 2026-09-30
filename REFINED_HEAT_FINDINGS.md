# End-to-end real-forecast study

**Complete: 9/9 recorded attempts.** Study `20260930T151924Z-3a0c3f`.

3 models, 1 real-forecast end-to-end tasks, Skills + Python versus No Skills (main comparison), plus Skills only (diagnostic), one repetition. One-shot is absent. Operator interruptions are unscored; provider errors remain in operational success rates. Matched capability tests exclude provider errors and interruptions.

| Model | Condition | Passed / scored | Median seconds | Mean tokens | USD / attempt | USD / success | Provider errors |
|---|---|---:|---:|---:|---:|---:|---:|
| Gemini 3.1 Flash-Lite | No Skills | 1/1 | 21.2 | 22,931 | $0.0111 | $0.0111 | 0 |
| Gemini 3.1 Flash-Lite | Skills + Python | 0/1 | 30.5 | 53,166 | $0.0190 | — | 0 |
| Gemini 3.1 Flash-Lite | Skills only | 0/1 | 122.7 | 206,634 | $0.0757 | — | 0 |
| Ministral 3 3B | No Skills | 0/1 | 103.1 | 152,217 | $0.0032 | — | 0 |
| Ministral 3 3B | Skills + Python | 0/1 | 123.3 | 202,627 | $0.0047 | — | 0 |
| Ministral 3 3B | Skills only | 0/1 | 29.8 | 215,006 | $0.0038 | — | 0 |
| GPT-6 Astra | No Skills | 1/1 | 21.5 | 11,147 | $0.1080 | $0.1080 | 0 |
| GPT-6 Astra | Skills + Python | 1/1 | 29.7 | 20,629 | $0.1494 | $0.1494 | 0 |
| GPT-6 Astra | Skills only | 1/1 | 85.6 | 87,528 | $0.3905 | $0.3905 | 0 |

Reported study charges: **$0.7654**. Unconfirmed charges are additional; the $0.0000 reserve is a budget precaution, not billed spend. Preflight charges are recorded separately in `results/preflight-v2.json`.

## Paired comparisons

| Model | Evaluable pairs | Skills wins | No Skills wins | Exact McNemar p | Holm-adjusted p |
|---|---:|---:|---:|---:|---:|
| Gemini 3.1 Flash-Lite | 1 | 0 | 1 | 1.0000 | 1.0000 |
| Ministral 3 3B | 1 | 0 | 0 | 1.0000 | 1.0000 |
| GPT-6 Astra | 1 | 0 | 0 | 1.0000 | 1.0000 |

These are exploratory comparisons on a small, deliberately chosen archived real-forecast task set. An insignificant difference does not establish equivalence. Interim rows have unequal coverage and should not be used to rank models.

## Interpretation boundaries

- Scientific calculations, output-contract failures, action-format rejections, and provider failures are different phenomena. Inspect the linked run traces before attributing a failed task to weather reasoning.
- The skills-only host requires earlier guide reads and catalog calls, blocks model-written Python, and serializes answers from produced artifacts. Early failures can occur before any skill is executed.
- The Python comparator can inspect inputs, execute programs, receive errors, and retry. The JSON-action harness approximates that workflow; it does not run the complete Codex or Claude Code clients.
- Reading long guides, repeated context, CLI discovery and extra calls can increase resource use. Provider-applied caching is recorded, but explicit cache breakpoints are not requested.
- This study does not establish operational forecast quality in Africa, local-hosting feasibility, or performance on African networks. See [model review](MODEL_REVIEW.md), [methodology](METHODOLOGY.md), and [statistics](STATISTICS.md).

The original availability-only pilot and its explanation remain in [FINDINGS.md](FINDINGS.md). The [dashboard](docs/index.html) contains task briefs, exact answers, clickable comparisons, and per-run traces.

Raw forecast bytes are served from a verified read-only local cache. Plotting is timed; download and setup are excluded. Catalog defects are patched in a separate version. Agents share no intermediate artifacts. See configs/refined-heat-v3.json.
