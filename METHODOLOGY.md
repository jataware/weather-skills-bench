# Experiment design

## Question and hypotheses

Does access to the weather skill catalog improve scientific task success or reduce tokens, billed cost, and completion time compared with the same agent using scientific Python alone? These are hypotheses to measure, not assumed outcomes. Skills may cost more tokens or time when discovery and CLI retries outweigh their benefit.

The experimental unit is one `(model, case, condition, repetition)` run. Each run gets a fresh conversation and workspace. Pair conditions by model, case, and repetition; randomize their execution order with a recorded seed. The current runner executes runs sequentially to avoid concurrent API demand and host load confounding latency.

## Conditions

| Condition | Python | Catalog docs | Actual skill calls | Execution feedback |
|---|---|---|---|---|
| `skills` | Yes | On demand, with a name/description discovery index | Yes | Yes |
| `python` | Yes | No | No | Yes |
| `python_one_shot` | One generated program | No | No | No |
| `docs_only` (optional) | Yes | On demand | No | Yes |

The main two conditions have equal maximum model calls, total code/skill executions, output tokens per request, cumulative tokens, context bytes, task time, execution time, CPU, and memory. These are ceilings, not equal actual resource consumption. Documentation reads consume a model turn and prompt tokens but no execution slot. The one-shot condition intentionally changes feedback and retry availability and must not be used to attribute all differences to skills.

The Python environment is the same across conditions and includes NumPy, pandas, xarray, SciPy, cftime, pint, and xarray-regrid. The skill service adds the pinned core and catalog scripts. Thus the experiment measures reusable expert guidance and implementation, not exclusive access to a numerical library. All conditions receive the same task metadata, including dimensions, variable attributes, and coordinate labels. Values are read from identical input files. No condition is shown the answer key or reference recipe.

A provider-neutral action protocol supports JSON actions and a single fenced Python program. Minor JSON newline formatting is tolerated. This avoids requiring a particular vendor's native function-calling API. Actual Python execution, rather than a prose answer, is available in every condition. The model must save `answer.json`. The reported pilot uses one action per response. Optional batched actions are available for future experiments: a model can plan several sequential actions in one response, the host traces each child and stops on error, and execution budgets still count every child. `python_one_shot` remains one program with no feedback. Batching changes the protocol and must be studied separately from the existing pilot.

## Tasks and ground truth

The first ten tasks are synthetic diagnostic fixtures focused on transformation and composition. They deliberately stress errors that can change a scientific conclusion:

1. Regional rainfall: clip bounds, weekly rate aggregation, incomplete periods, cosine latitude weighting.
2. Ensemble flux spread: water-density conversion, member-wise weekly totals, sample standard deviation.
3. Legacy accumulations: difference amounts before weekly aggregation and ensemble median.
4. Forecast bias: valid-date conversion, Kelvin offset, naming, date intersection, temporal mean.
5. IOD: build a climatology, subtract before spatial weighting, use the two correct dipole boxes.
6. Model disagreement: select a matching lead, normalize units, concatenate, sample spread.
7. Rolling rainfall: select disjoint windows before rate-to-total conversion.
8. Calendar alignment: noleap versus Gregorian, preserve dates and exclude the unmatched leap day.
9. Spatial alignment: interpolate onto the reference grid before differencing.
10. Irregular precipitation: integrate duration-weighted rates from CF bounds.

Oracles use direct NumPy/stdlib arithmetic and do not call catalog functions. Each is cross-checked by an actual pinned catalog pipeline, including execution in the production Docker environment. Dates, keys, units, and array shapes match exactly. All numerical values must be finite and within `abs_tol=1e-6` or `rel_tol=1e-6` using `math.isclose`. Boolean-as-number and NaN/Infinity answers are rejected. These tolerances account for numerical implementations; they do not use an LLM judge. Identical answers always receive the same verdict.

Input archives have fixed Zip metadata and per-store SHA-256 hashes. No live download, current date, geocoding, unpublished data, or provider credentials enter a graded case. This makes the ground truth reproducible without access to external weather services. It also limits the scope of the conclusions: this suite does not measure live source discovery, retrieval, map aesthetics, or operational forecast skill.

## Workflow measurement

The host records every document read, Python execution, and skill invocation, with arguments, duration, exit code, and errors. Python never sees the skill code: calls are brokered into a separate container sharing only the current task's files. Failed calls remain visible. Skill logs cannot be forged by writing a claimed history inside `answer.json`.

Process conformance is a separate binary score. It requires distinct successful calls matching reference nodes and important argument values, with upstream artifacts feeding downstream calls. Only required dependency edges are ordered; independent branches can be interleaved. Attempts to deaccumulate already-rate inputs are flagged. This is deliberately stricter than numerical correctness: index selection instead of coordinate selection, different equivalent period spellings, Python substitutions, or alternative valid algorithms can pass the answer check and miss recipe conformance. It is not proof that the final JSON was derived from those artifacts, and is not used to declare a numerical failure. Future versions can add validated equivalence classes without rewriting older scores.

## Isolation and reproducibility

Each run has fresh `/inputs` (read-only) and `/work` mounts, a new conversation, and new containers. No repository root, answer module, previous output, API key, Docker socket, or host home directory is mounted. Containers use a read-only root, no network, no Linux capabilities, no-new-privileges, non-root UID, one CPU, 1 GB RAM, a PID cap, and bounded execution time. A timed-out exec kills its container rather than leaving code running. Output is read through the container to avoid following agent-created symlinks on the host.

The host alone sends requests to OpenRouter. Historical provider routes are fixed per model. The separately versioned recovery cohort uses explicit provider allowlists and price caps; model fallback remains disabled. Exact returned model/provider names, request IDs, usage, finish reasons, catalog/core commits, dependency pins, code hash, fixture hashes, and image IDs are recorded. Image setup and dependency installation happen before measured inference; per-run container startup is tracked separately from solve time.

Model generations are not guaranteed deterministic: sampling, routing infrastructure, and provider kernels can vary. Provider-side prompt caching is also not eliminated by a fresh local workspace; cache-read tokens are recorded and reported separately. Repetitions are necessary. The deterministic guarantee applies to inputs, expected answers, and grading, not to LLM behavior or service latency.

## Measurements and reporting

- **Task success:** all required numerical and structural checks pass. Every attempted run stays in the denominator. Infrastructure errors and budget stops have explicit statuses.
- **Workflow conformance:** reference nodes and artifact dependency edges pass, separately from success.
- **Tokens:** sum prompt and completion tokens over every request. Reasoning and cache-read tokens are recorded as subsets, not added again to the total.
- **Cost:** sum `usage.cost` reported by OpenRouter. Missing cost is unknown, never free; the study stops unless a configured conservative reserve bounds the unconfirmed charge. Cost per success includes spend on failed attempts.
- **Latency:** wall time, container setup, solve loop, API time, and execution time; show median and p90. Timed-out and unsuccessful attempts remain in resource metrics.
- **Paired effects:** within a selected experiment, compare shared `(case, repetition)` attempts for each model. Show success percentage-point difference and skills/Python time, token, and cost ratios. Pairs containing a provider error on either side are excluded from capability comparisons; those failures remain in the operational attempt table. Do not pool unequal task coverage or conflate pilot experiments with changed harness versions.

The pilot is one repetition on three cases. It is descriptive, with raw denominators, and has no significance claim. For a briefing-grade study, run all ten cases and at least three repetitions, expand task families and fixture variants, include `docs_only`, and add task-clustered bootstrap intervals. A larger sample of repeated runs on the same three fixtures alone does not establish generalization. Public fixtures may eventually enter training corpora; maintain private variants for later held-out evaluation.

## Accounting sources

The runner follows OpenRouter's [usage accounting documentation](https://openrouter.ai/docs/cookbook/administration/usage-accounting): usage is returned automatically, and `usage.cost` is the amount charged. It snapshots the [model catalog](https://openrouter.ai/docs/api/api-reference/models/list-all-models-and-their-properties) at study start. Price-derived estimates are not substituted for billed cost.

## Pilot infrastructure recovery

The first provider route for DeepSeek returned 429 errors, including errors nested inside HTTP-200 completion objects. A recovery run retains every completed non-DeepSeek result and reschedules **all** DeepSeek conditions on one verified route before any DeepSeek agent action. Original transport failures remain archived and are not silently converted to model reasoning failures. This is a provider recovery, not selective rerunning of wrong numerical answers.

Two operator interruptions during infrastructure repair left one Gemini and one DeepSeek request without returned generation IDs. Completed charges from interrupted attempts are recorded separately; their final in-flight charges are explicitly unknown. A cumulative $0.20 reserve protects the study stop threshold and is not reported as actual billed cost. The final completed pilot excludes DeepSeek as a whole after repeated provider failures on two routes. Its partial outcomes, including a numerical failure, remain in earlier records. The completed comparison contains 27 attempts across the other three models.

The configured cumulative token limit is checked between requests and can be crossed by one response. HTTP read timeouts are inactivity limits; a provider that sends keepalive traffic can exceed that duration. Recorded wall time is therefore the measurement to use for the pilot's UX comparison, not a claim that every request met a hard total deadline.

## Publication boundary

The dashboard export uses an allowlist. It includes task briefs, reference answers, numeric run metrics, stop reasons, provider names, and action/argument sequences. The user-requested run log export also includes executed Python, recorded stdout/stderr, visible model responses, agent system instructions, and per-request usage. It excludes hidden reasoning text, raw API envelopes, request headers, credentials, and account identifiers; credential-shaped text and host user paths are redacted. The runner bounds stdout at 16,000 characters and stderr at the last 8,000 characters, so these are the recorded logs rather than unlimited process transcripts. Model calls and execution events remain separate ordered sequences; historical event-to-call timing is not invented. Archived records without detailed logs are explicitly marked unavailable. Reference answers are public for human auditing, but the isolated evaluation runtime cannot access the dashboard or repository. GitHub Pages deployment is a manual workflow, not an automatic side effect of running experiments.

## Skills-only v2: expanded operational comparison

`configs/expanded-v2.json` specifies 120 attempts: Fable 5.1, GPT-6 Astra, Sonnet 5.5, Gemini 3.1 Flash-Lite, DeepSeek V4.1 Flash, and Qwen3.5 9B; all ten tasks; skills-only and iterative Python; one repetition. Provider routes passed an independent protocol preflight. DeepSeek uses Fireworks because its direct route conflicted with the account's existing data policy. Preflight billing is recorded separately in `results/preflight-v2.json`.

The new `skills_only` condition requires reading each invoked guide in an earlier model response. The host rejects Python actions, including Python nested in a batch, and its sandbox has no general Python execution service. The agent can invoke only allowlisted catalog scripts. It submits a declarative mapping from output artifacts to answer fields; a fixed, case-independent serializer reads values and formats dates/timedeltas. It cannot calculate, select, aggregate, evaluate code or reference inputs as computed outputs. The host checks that referenced stores came from successful skill calls. All ten reference tasks pass through this exact mechanism (`results/skills-only-validation.json`).

The system prompt includes three catalog-wide compatibility notes documented before model evaluation: use the working standard-unit conversion path, pass concat inputs as one list, and preserve time bounds during aggregation. These are disclosed runtime errata, not case-specific recipes or answer values. The catalog and numerical grading remain unchanged.

Both new conditions allow sequential batching, retries, 24 model responses, 24 executions, 250,000 cumulative tokens, 8,192 output tokens per response, and the same time limits. The skills agent receives the catalog guidance and the Python agent receives the scientific Python environment. This is a comparison of two deployable agent configurations; it no longer isolates the marginal effect of adding skills while keeping code execution available in both arms. The baseline approximates an iterative coding-agent workflow, not the complete Codex or Claude Code product. One-shot is absent from the new study and from the primary leaderboard; its historic runs remain archived.

The new study is separately versioned and must not be pooled with the original availability-only pilot. See [STATISTICS.md](STATISTICS.md) for Wilson intervals, exact paired McNemar tests, multiplicity adjustment, and limits from the small diagnostic suite.

### Transport repair during the expanded study

The first ten attempts are preserved in `20260929T184130Z-9023ed`. Its tenth attempt was interrupted after provider keepalive traffic bypassed the HTTP inactivity timeout. The resumed study retains all ten attempts, including the interruption; it does not rerun failures. Subsequent requests have a total wall-clock deadline. Failed request duration is included in recorded model time. Partial batch feedback is retained if a later action in that batch is invalid. Prompts, model routes, task data, scientific operations and answer grading are unchanged; both code revisions are recorded.

Unconfirmed requests remain explicitly unknown in cost metrics. A conservative reserve based on message bytes, maximum output length and fixed endpoint prices protects the $25 stop threshold; it is not reported as billed cost. The stop threshold is checked between requests and is not a provider-enforced hard spending cap. Provider errors remain in operational results and resource measurements, but their matched pairs are excluded from the exploratory capability test. Operator-interrupted attempts remain in the logs and recorded spend but are unscored and excluded from model success/resource averages. The inherited interruption retains its original elapsed time.

The first two Sonnet requests exposed a separate configuration error: model-level capability metadata included temperature, while the pinned Anthropic endpoint did not support it. Endpoint-specific parameter selection now omits temperature for this route. All six routes subsequently passed preflight with the exact scored-request parameters (`results/preflight-v2.json`). Those two rejections occurred before any response or agent action and remain archived as infrastructure; the untouched Sonnet tasks are scheduled again. A Fable request interrupted before its first response during this repair is treated the same way. Substantive attempts, including the earlier Qwen interruption, are retained without rerunning them. The resumption records the full code-revision history.

The reporting layer labels a `ReadTimeout` at or beyond the shared task deadline as `task_timeout`; its raw transport status is preserved as `original_status`. Such a run exhausted the agent's task budget and is not removed from the paired analysis as a provider-only failure. Earlier request timeouts remain provider errors. This changes stop-reason classification, not saved answers or numerical grading.

### Agent-interface scope

The runner uses text JSON actions, not vendor-native function calling or the complete Codex/Claude Code clients. Malformed actions, wrong action names and extra wrappers can consume retries before any scientific code executes. Report those observed protocol failures separately from wrong numerical answers. Results measure this explicit agent loop and its tool interfaces; they do not establish how the same models would perform in a different production agent framework. A native-tool or more tolerant adapter is a distinct experimental factor for a subsequent, separately versioned comparison.

The client does not request explicit prompt-cache breakpoints. Any provider-applied caching is recorded through returned usage; cached input is still included in total tokens and actual billing remains the cost measure. A production client that configures caching differently can have different costs, especially for long skill guides repeated in conversation history. The equal maximum budgets do not imply equal prompt length or equal numbers of model round trips.

## Real forecast tasks and provider recovery

The three end-to-end cases use real archived ECMWF forecast data for Kenya. Unlike the synthetic cases above, these agents retrieve data from the public source, process it and deliver a PNG figure. Source object versions are checked before and after each attempt and preserved snapshots support an independent offline oracle. Figure delivery is checked deterministically; visual scientific correctness still needs human review. The heat reference recipe exposes a retained Celsius-weighting limitation in the catalog, although an alternative skill workflow has passed.

`end-to-end-v2` is an independent, 30-attempt provider recovery cohort with the same five model IDs and two arms. Each arm has 40 HTTP requests, 40 executions, 350,000 cumulative tokens, 8,192 output tokens per request, 220,000 context bytes, a 1,200-second solve deadline and a 240-second execution deadline. Rainfall briefs explicitly require clipping negative daily increments before aggregation; original pilot scores remain unchanged. Both arms use JSON output mode and the same bounded transport recovery policy.

The new routing uses tested providers within the same model and limits route prices. HTTP 429/500/502/503/504 can retry at most three times per run, twice consecutively, within the existing request and time budgets. Retry-After is honored; a delay exceeding the 30-second wait cap or remaining task time ends the attempt. Authentication, validation failures and ambiguous network timeouts are not retried. Error-designated model responses are never executed; malformed responses may receive correction feedback within the ordinary request budget. Retry waits are included in solve time, reported charges in cost, and unconfirmed charges in a separate conservative reserve against the $15 stop threshold.

The recovery cohort changes more than one factor and cannot isolate the causal effect of JSON mode, provider routing, retries or rainfall clarification individually. Within the cohort, both arms share these settings. Original service failures remain inspectable. Terminal service failures and response-format failures are distinct, and successful transport recoveries remain in execution logs.

## Post-hoc provider-failure retries

The 36-cell recovery panel is preserved with its 15 original provider failures. A fixed retry manifest schedules one new isolated attempt for each of those 15 cells only; the other 21 task outcomes cannot be replaced. The new transport uses streaming, fresh connections, a 300-second request deadline within the unchanged 1,200-second task deadline, and bounded network retries. Scientific prompts, task data, grading, model IDs and per-task token/execution limits are unchanged. Uncertain costs and tokens receive conservative reserves; partial actions are never executed.

The combined provider-recovery view uses each designated replacement regardless of whether it passes or fails, links the original errors and includes original-plus-retry charges in total spend. Its charts summarize displayed attempts and exclude original-error overhead; the UI states that distinction. Because transport settings changed and retries target observed infrastructure failures, this view is a post-hoc recovery analysis, not a new uniform-protocol experiment. The untouched original panel and the 15-attempt retry batch remain separately inspectable.

## Focused heat experiment: cached-heat-v3

This is a new protocol and is not pooled with live-retrieval cohorts. One archived forecast task produces a two-week regional heat outlook: inspect the raw daily-mean temperature product, choose the service rectangle, calculate each member's daily cosine-latitude regional mean, take each week's hottest daily regional mean, summarize the ensemble, cite the source and deliver a figure. The brief explicitly defines both calendar windows and reduction order. It uses the same independently established numerical oracle, with a distinct task ID and a separately pinned patched catalog.

The main comparison is Skills + Python versus No Skills + Python. Skills only is a third diagnostic condition. Skills use is observable and optional in the hybrid arm; failing to use skills remains visible rather than being relabeled as a skill benefit. All three conditions use identical task, token, request, execution and time budgets. The initial nine-run pilot has three models and one repetition; it is a feasibility experiment, not evidence of broad forecasting superiority.

Raw data are frozen source bytes verified against every object hash in `fixtures/real-sources.json`, cached locally and mounted read-only. Agents do not access the internet in this protocol. Source preparation and container setup are outside solve time; model calls, inspection, calculations, plotting and local cache checks during execution remain timed. This measures warm-data forecast analysis, not network availability or download speed. Both code-capable arms can retain their own intermediate files. The skill broker also memoizes exact successful calls within a run, keyed by arguments, input hashes and skill image; it returns a hit only while the original outputs still match their recorded hashes. Repeated calls still count against execution/request budgets. No result is shared between runs.

Reference calculations and regression validations are cached on the host under source, code, image and task fingerprints. These host outputs and answers are never mounted for agents. The patched temperature weighting/conversion and clipped-Zarr serialization paths are checked against independent array calculations. Original studies continue to describe the original catalog defects; fixing them does not retrospectively change their scores.

The follow-up `cached-heat-v4` profile keeps the same task and budgets and additionally pins `patches/rolling-temperature-followup.patch` by SHA-256. It repairs rolling temperature aggregation and the full-axis median path discovered in the v3 pilot. Its reference is independently validated under the patched image; v3 scores are preserved and are not evidence about v4 model performance.

## Expanded heat panel: model exclusion

The `refined-heat-panel-v4` study excludes GPT-6 Astra because it helped develop the benchmark, tasks, and harness. Earlier Astra results remain in archived experiments and are not pooled into this panel. This exclusion avoids evaluating the benchmark-authoring model; it does not establish independence from all design bias. The panel uses Claude Fable 5.1, Claude Sonnet 5.5, Gemini 3.1 Flash-Lite, DeepSeek V4.1 Flash, Qwen3.5 9B, and Ministral 3B in all three conditions with identical per-run budgets. It uses the v4 repaired catalog and one shared cached raw forecast archive, with isolated work directories.

The linked small-model extension adds Llama 3.2 1B, Llama 3.2 3B, Qwen2.5 7B, and Llama 3.1 8B, yielding 10 models and 30 planned attempts across the panel. Llama 3.2 endpoints lack API-enforced JSON mode, so their requests omit that unsupported parameter while retaining identical action instructions, parsing, and recovery feedback. This applies to all three conditions and is disclosed in the dashboard Conditions drawer. The extension has a $5 study stop threshold in addition to the parent panel’s $10.

Gemma 3 4B was considered for this extension but excluded before any task runs after repeated upstream capacity errors in preflight. Qwen2.5 7B replaces it; failed preflight checks are retained in `results/preflight-refined-small-v4*.json`.

## Guided skills and dollar budgets: guided-heat-v5

The targeted follow-up registers Qwen3.5 9B, Ministral 3B, Gemini 3.1 Flash-Lite, and Claude Sonnet 5.5 in all three conditions: 12 attempts, one repetition. It retains the v4 cached task, oracle, images and catalog fixes. The config's `experiment_version` identifies the new experiment; `protocol_version: cached-heat-v4` identifies its unchanged data/catalog profile. It is not pooled with earlier runs.

The hybrid prompt now leads with skill discovery and directs agents to use supported skill operations, with Python for unsupported operations, inspection, recovery and serialization. The harness requires a relevant guide read in an earlier response before any execution and each skill's guide before that skill is invoked. It enforces the presence/order of reads, not semantic relevance or whether every Python fallback was necessary. Agents are asked to explain fallbacks in code comments. Actual non-help skill invocations are measured separately; guide reading alone does not establish reuse. Scientific grading remains unchanged.

Each condition receives a $2 model-spend allowance, 30 minutes, 80 model responses, 120 executions, 16,384 output tokens per response, and 500,000 context bytes. The cumulative token limit is disabled. The study allowance is $24. Context, response and time limits remain safeguards against unbounded loops; costs at those stops are censored observations, not estimates of eventual success cost. Per-request output limits may still truncate responses. Historical token-limited failures remain unchanged.

Before sending each request, admission checks both remaining run and study dollars. The conservative request bound uses UTF-8 input bytes plus chat-framing allowance, the maximum completion length, twice the pinned per-token rates, and a one-cent margin. Allowed providers have explicit price ceilings covered by those rates. This is a harness spending control based on provider pricing assumptions, not a provider-enforced billing guarantee. A request is not sent unless the full bound fits. Ambiguous transport charges reserve the same bound, scoped to the run and included in study exposure; they are never reported as actual spend. Agents receive remaining dollars, time, responses and executions with ordinary execution feedback. A run can stop below $2 of reported charges because the next request or an unconfirmed charge needs reserved room. Actual provider charges, reservations and stop reasons remain distinct in traces and dashboard exports.

The follow-up changes both prompting and budgets. Comparisons with v4 cannot attribute differences to one change alone. The three conditions within this experiment share the new limits; one task and one repetition remain exploratory. GPT-6 Astra remains excluded for benchmark-development involvement.

The completed guided batch had three terminal infrastructure failures, all Qwen3.5 9B: its DeepInfra and Parasail BF16 routes returned HTTP 429 upstream capacity errors. `guided-heat-v5-recovery` registers exactly one new isolated attempt for each affected condition. It preserves the other nine task outcomes and the original failures, traces and charges. After two-step JSON-action probes passed, its Qwen allowlist changed to SiliconFlow FP8 and Venice FP8. The model ID is unchanged, but provider and quantization are experimental differences. The recovery view is therefore a post-hoc repair, not a uniform-provider comparison. Prompt policy, oracle, cached data, catalog and per-run limits are unchanged. The recovery has a $6 ceiling within the original $24 overall allowance; route-probe spend is reported separately. A failed recovery is retained rather than replaced by the best of multiple attempts.
