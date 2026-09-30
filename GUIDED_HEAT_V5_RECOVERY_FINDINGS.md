# End-to-end real-forecast study

**Complete: 3/3 recorded attempts.** Study `20260930T173741Z-820084`.

GPT-6 Astra is excluded from this comparison because it helped develop the benchmark, tasks, and harness. This avoids evaluating the benchmark-authoring model; it does not establish that the remaining evaluation is free of design bias. Earlier Astra runs remain in archived experiments.

1 models, 1 real-forecast end-to-end tasks, Python + skills versus Python only (main comparison), plus Skills only (diagnostic), one repetition. One-shot is absent. Operator interruptions are unscored; provider errors remain in operational success rates. Matched capability tests exclude provider errors and interruptions.

| Model | Condition | Passed / scored | Median seconds | Mean tokens | USD / attempt | USD / success | Provider errors |
|---|---|---:|---:|---:|---:|---:|---:|
| Qwen3.5 9B | Python only | 0/1 | 131.6 | 46,943 | $0.0050 | — | 0 |
| Qwen3.5 9B | Python + skills | 0/1 | 201.8 | 118,891 | $0.0122 | — | 0 |
| Qwen3.5 9B | Skills only | 0/1 | 1800.2 | 1,023,710 | Unknown | — | 0 |

Reported study charges: **$0.1199**. Unconfirmed charges are additional; the $0.0956 reserve is a budget precaution, not billed spend. Preflight charges are recorded separately in `results/preflight-guided-qwen-recovery.json`.

## Paired comparisons

| Model | Evaluable pairs | Skills wins | Python only wins | Exact McNemar p | Holm-adjusted p |
|---|---:|---:|---:|---:|---:|
| Qwen3.5 9B | 1 | 0 | 0 | 1.0000 | 1.0000 |

These are exploratory comparisons on a small, deliberately chosen archived real-forecast task set. An insignificant difference does not establish equivalence. Interim rows have unequal coverage and should not be used to rank models.

## Interpretation boundaries

- Scientific calculations, output-contract failures, action-format rejections, and provider failures are different phenomena. Inspect the linked run traces before attributing a failed task to weather reasoning.
- The skills-only host requires earlier guide reads and catalog calls, blocks model-written Python, and serializes answers from produced artifacts. Early failures can occur before any skill is executed.
- The Python comparator can inspect inputs, execute programs, receive errors, and retry. The JSON-action harness approximates that workflow; it does not run the complete Codex or Claude Code clients.
- Reading long guides, repeated context, CLI discovery and extra calls can increase resource use. Provider-applied caching is recorded, but explicit cache breakpoints are not requested.
- This study does not establish operational forecast quality in Africa, local-hosting feasibility, or performance on African networks. See [model review](MODEL_REVIEW.md), [methodology](METHODOLOGY.md), and [statistics](STATISTICS.md).

The original availability-only pilot and its explanation remain in [FINDINGS.md](FINDINGS.md). The [dashboard](docs/index.html) contains task briefs, exact answers, clickable comparisons, and per-run traces.

Raw forecast bytes are served from a verified read-only local cache. Plotting is timed; download and setup are excluded. Catalog defects are patched in a separate version. Agents share no intermediate artifacts. See configs/refined-heat-v3.json.

Qwen recovery uses SiliconFlow FP8 and Venice FP8 after both previous BF16 hosts returned HTTP 429 capacity overload. Same model ID, but provider and quantization changed. Other models retain their original outcomes. This is a post-hoc recovery comparison, not a uniform-provider rerun.

## Provider monitoring and late billing

All three recovery attempts were monitored through completion. No HTTP 429 overload recurred. Python only submitted an incorrect result after omitting the requested regional clip. Python + skills clipped correctly but its Python calculation did not apply the latitude weights it computed. Skills only exhausted the 30-minute task deadline after two recovered five-minute request timeouts; a final 178-second request ended at the remaining task deadline. The public task-timeout label retains the raw transport errors in its trace and does not mean the transport was error-free.

Original guided cohort, recovery, route checks, and two late timeout receipts total at least **$1.4481**. The last timeout receipt is unavailable; its charge remains unknown and reserved. The response logs remain unchanged. See `results/guided-heat-v5-provider-diagnosis.json` and `results/guided-qwen-timeout-billing-receipts.json`.
