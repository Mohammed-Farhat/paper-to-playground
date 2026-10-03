# Requirements checklist

Every requirement line of [hakathon_requirements.md](hakathon_requirements.md), checked against the PDF (both files are identical in content). Each line has a status and the evidence used to verify it.

**Status:** ✅ done and verified · ⏳ done by the team at submission time · ➖ not a requirement on our code (information about assessment)

**How it was verified (2026-10-03):**

- **Clean-machine test:** a fresh `git clone` of commit `6663945`, a brand-new Python 3.11.15 virtual environment, then exactly `python -m pip install -r requirements.txt` and `python agent.py --input case.json --output out --model deepseek/deepseek-v4.1-flash`. Result: exit 0 in 35 s.
- **Output validator:** [`tools/check_output.py`](../tools/check_output.py) mechanically checks an output folder against the section 5 rules (30 checks). It passes on the clean-machine output and on every regression run.
- **Unit tests:** `python -m unittest discover -s tests` passes 29 tests (parsing, TeX, JavaScript execution checks).
- **Browser tests:** in Chromium, every control was moved to its minimum and maximum and every exploration button was clicked. There were no errors, no failing live checks, and zero external network requests.

---

## Header

| Requirement | Status | Evidence |
|---|---|---|
| Build an agent that turns a focused research-paper excerpt into a clear, interactive visual explanation for an engineering undergraduate | ✅ | `agent.py` and `p2p/`. The `audience` field from `case.json` is passed to the model, and the page shows it. |
| Help a reader understand an idea by changing inputs and seeing what happens | ✅ | The playground has at least two input controls. Every change recomputes the values, redraws the visual and re-runs the live checks (`templates/runtime.js`). |
| Your submission is the reusable generator; the generated explanations are its results | ✅ | Nothing paper-specific is stored or used by the generator. The prompt, template and helper library are generic. |

## 1. Your challenge

| Requirement | Status | Evidence |
|---|---|---|
| Receives a paper arXiv URL and a learning brief | ✅ | `source_url`, `focus` and `audience` are read from `case.json` (`agent.py`, `load_case`). |
| Autonomously creates a browser-ready explanation (html) | ✅ | Writes `out/index.html` with no human step. |
| Identify the relevant idea | ✅ | `plan.concept` and `plan.anchor` (the section or equation) are written first in the model reply and logged as the trace event `plan_generate / plan`. |
| Plan the explanation | ✅ | `plan` covers computation, visual, controls, checks and **coverage** (every outcome the brief requires, mapped to where the page delivers it). It is logged in the trace (`brief_coverage`). |
| Generate the artifact | ✅ | Trace event `plan_generate / llm_call`, then `build / write_page`. |
| Check it | ✅ | Structure checks, static code checks, and the generated code run in V8 across 15–35 states. Trace events: `spec_structure`, `code_static`, `js_execute`, `known_answer_tests`, `brief_coverage`, `page_static`. |
| Revise when needed | ✅ | A revision is made only when a check fails, and only the problem list is sent. Trace events: `revise / request`, `llm_call` and `apply`. The best version is kept. |
| Choose your own agent architecture; multiple agents optional | ✅ | One generator call plus deterministic checks and targeted revisions (README, Architecture). |
| Keep the scope to the requested concept | ✅ | Prompt: "Stay within the brief's scope", plus the coverage map of the brief's outcomes. |
| You are explaining a mechanism, not reproducing an entire paper or training a model | ✅ | Prompt: "No training, datasets or randomness"; the code may not use `Math.random`. |
| Full internet access, AI assistants, libraries allowed during development | ➖ | Development-time permission. |
| Credit reused code and assets in your README | ✅ | README, "Reuse credits": libraries with licenses, the Okabe–Ito palette, the cited practice papers, design credit, AI assistance. |
| Generic templates are allowed | ✅ | `templates/page.html`, `lib.js` and `runtime.js` contain no paper content. |
| Paper-specific prewritten answers or generated pages are not allowed | ✅ | The generator uses none. The prompt's examples were made neutral in Phase 3. `docs/fixtures/` (generated design fixtures) was removed in Phase 4. The only generated page in the repo is the README's required example pair, which the agent never reads. |

## 2. What each generated explanation must contain

| Requirement | Status | Evidence |
|---|---|---|
| Clear starting point: the idea | ✅ | `idea` is required (a check fails if it is missing), shown in section 01. |
| … why it matters | ✅ | `why` is required, shown under "Why it matters". |
| … the meaning of the main symbols | ✅ | `symbols` requires at least 2, shown as a table (symbol, meaning, where it appears in the playground). |
| … in language appropriate for the specified audience | ✅ | The audience is in the prompt ("write for the audience; define each symbol before use"). |
| Meaningful visual: diagram, plot, animation or simulation that explains the mechanism | ✅ | `render()` returns an SVG of the mechanism (prompt: "cause → effect"). Checked to exist and be well-formed in every tested state. |
| Labels and relationships must be readable | ✅ | Labels cut off by the drawing edge are detected (`clipped_labels`) and revised. TeX is turned into readable Unicode in labels (`PG.plain`). The design gives the visual its full 760 px on desktop. |
| … and scientifically accurate | ✅ | Prompt fidelity rules. Live invariant checks run in every state. Labels show computed values only. |
| At least two meaningful controls | ✅ | At least 2 input controls are required (preset buttons don't count). The **control sweep** proves each one changes the result or the visual. |
| Changing them must update the relevant visual or calculation | ✅ | Same control sweep, plus the browser test. |
| Display important intermediate values where useful | ✅ | `show()` panel ("Inside the calculation"). |
| Numerical results must come from executable calculations, not invented values or canned images | ✅ | Every number comes from `compute()` at run time. Prose may not state demo outputs. No images are used. |
| Two guided explorations: what to change, what to observe, why | ✅ | Exactly 2 required, each with `change`, `observe` and `why` (checked). Each can have a "Set up this exploration" button. |
| Include one limitation, assumption or common misunderstanding | ✅ | `pitfall` is required, shown in section 05. |
| Source grounding: identify the paper and relevant section or equation | ✅ | `grounding.paper` and `section` are required. The link to `source_url` is shown. |
| Distinguish statements supported by the excerpt from your own examples and simplifications | ✅ | Two separate required lists, "Supported by the source excerpt" and "Our examples and simplifications (not from the paper)", plus the verbatim excerpt in a collapsible block. |
| Do not imply that a toy demonstration reproduces the paper's experimental results | ✅ | A disclaimer is always shown, with a default if the model omits it. Prompt rule. |
| The generated page must work without an API key or internet connection | ✅ | Validator: no external script, link, font, image or `@import`, and no fetch. Browser: 0 external requests. |
| No chat interface is required | ✅ | None. |
| Prioritize explanation and scientific fidelity over decoration | ✅ | Fidelity is the prompt's top section. The design has no decorative assets. |

## 3. Two public examples

| Requirement | Status | Evidence |
|---|---|---|
| Example A: Q, K and V matrices editable; scores, weights and output shown; scaling on/off; equal and dominant scores; rows sum to one; output = weighted sum of V; no training | ✅ | [`cases/attention.json`](../cases/attention.json). Generated pages pass every check, and the live checks include "rows sum to 1" and "output = Σ A·V". |
| Example B: change the distribution and n; probabilities, contributions and entropy shown; certain vs equally likely; 0 bits and 2 bits; zero probabilities handled | ✅ | [`cases/entropy.json`](../cases/entropy.json). The control sweeps include all-zero and one-hot distributions with no NaN. |
| Use these papers to make your own practice inputs in the format on page 2 | ✅ | Both in `cases/`, plus 4 more of the same scope (Adam, distillation, batch normalization, and a dropout case with no excerpt). |
| The examples illustrate scope, not prescribed page designs | ➖ | — |

## 4. Required code and execution format

| Requirement | Status | Evidence |
|---|---|---|
| Use Python 3.11 | ✅ | `.python-version`. The clean-machine test ran on CPython 3.11.15. |
| `agent.py` at the repository root | ✅ | [`agent.py`](../agent.py) |
| Pinned dependencies in `requirements.txt` | ✅ | All `==`, including indirect dependencies. |
| Helper files and generic templates may be included | ✅ | `p2p/`, `templates/`, `tools/` |
| Any Python framework; a simple agent loop using requests is sufficient | ✅ | `requests` (plus `mini-racer` for running the JavaScript checks). |
| No GPU | ✅ | None used. |
| No system-package installation | ✅ | `mini-racer` installs as a prebuilt wheel (Windows, Linux x86-64 and ARM, macOS). Verified in the clean environment. |
| No external server | ✅ | Only OpenRouter is called. |
| No manual setup beyond installing `requirements.txt` | ✅ | The clean-machine test needed only the two official commands, plus the key environment variable. |
| Exactly this command interface | ✅ | `--input`, `--output` and `--model`, all required (`agent.py`, `parse_args`). Verified verbatim. |
| Specify MODEL_ID in the README | ✅ | README, Model: `deepseek/deepseek-v4.1-flash` |

## 5. Input, output, and OpenRouter

| Requirement | Status | Evidence |
|---|---|---|
| `case.json` is UTF-8 JSON | ✅ | Read as UTF-8 (a byte-order mark is tolerated). Invalid JSON exits with code 2 (tested). |
| Five required string fields: `source_url`, `focus`, `audience` | ✅ | The 3 named fields are required and missing ones exit with code 2 (tested). The document names only 3 of the "five"; every other string field (`excerpt`, `title`, …) is passed to the model, and the excerpt is found under any of several likely names. |
| `focus` states the concept and required learning outcomes | ✅ | The model must list every required outcome in `plan.coverage` with where the page delivers it. This is validated and logged (`brief_coverage`). |
| All model calls must use the supplied MODEL_ID through OpenRouter | ✅ | `--model` is passed unchanged to every call. The provider-routing preference does not change the model. |
| Read `OPENROUTER_API_KEY` from the environment | ✅ | `agent.py`. A missing key exits with code 2 (tested). |
| Use your own key for development; the instructor supplies the assessment key | ✅ | The development key is kept outside the repository. |
| Use `https://openrouter.ai/api/v1/chat/completions` with Bearer authentication | ✅ | `p2p/llm.py`: `OPENROUTER_URL` and the `Authorization: Bearer` header. |
| Never commit a key | ✅ | `.gitignore` excludes `*.key` and `.env`. A search of all tracked files and the entire git history finds no key. |
| … or embed it in the page | ✅ | Validator check "no API key in the page". The key is only used in the request header. |
| During assessment, network access is limited to OpenRouter | ✅ | The only network code is `p2p/llm.py`, which calls the OpenRouter URL. The paper URL is never downloaded. |
| 10 minutes per case | ✅ | Responses are streamed with a hard deadline (600 s minus a 20 s reserve) checked while reading. Our runs take 16–43 s. |
| At most 10 API requests (including retries) | ✅ | Every HTTP attempt is counted before it is sent (`MAX_REQUESTS = 10`). The design maximum is 3 calls × 3 attempts = 9. Our runs use 1–3. |
| 30,000 total completion tokens | ✅ | Each call's `max_tokens` is capped at the remaining budget, and no call is made with fewer than 1,500 tokens left. Our runs use 5–14k. |
| Stop within the limits | ✅ | `BudgetExceeded` stops the run, which then builds the best version so far. |
| Create `out/index.html`, a single self-contained file with embedded CSS, JavaScript and visuals | ✅ | `p2p/build.py` inlines everything. Validator checks. |
| It must work in Chromium when served locally | ✅ | Tested in Chromium over `http://localhost`, with every control operated. |
| No CDN, downloaded fonts, remote images, or build step | ✅ | Validator checks: no external script, link, font, image, `@import` or remote `url()`. System font stacks only. |
| Create `out/trace.jsonl`: one JSON object per event | ✅ | `p2p/trace.py`. Validator: every line parses as one object. |
| … recording a stage, action and result | ✅ | Every event has `stage`, `action` and `result` (validator). |
| … per-call prompt/completion token counts | ✅ | Each `llm_call` event records prompt, completion, reasoning, cached and total tokens, plus the OpenRouter `generation_id` and provider. |
| … elapsed seconds | ✅ | `t` on every event and `elapsed_s` per call. The final summary records the total elapsed time. |
| … checks | ✅ | Trace events: `spec_structure`, `code_static`, `js_execute` (states tested, control effects), `known_answer_tests`, `brief_coverage`, `page_static` |
| … failures | ✅ | Failed checks have `result: fail` with the problem list. API errors have `result: error`. |
| … revisions | ✅ | `revise / request` (the problems), `llm_call`, `apply` (what changed), `stop`, and `select_version` |
| Do not log credentials | ✅ | Validator: no key or `Bearer` text in the trace. |
| … or hidden reasoning | ✅ | Reasoning is disabled (`{"enabled": false}`). If reasoning is enabled for development it is requested with `exclude: true`. Only token counts are logged. |
| Exit with code 0 on success and nonzero on failure | ✅ | 0 when the page is built and works. 1 for an API failure or a critical page defect. 2 for bad input or a missing key. All tested. |
| No human editing of generated outputs during assessment | ✅ | The pipeline is fully automatic. |

## 6. Submission

| Requirement | Status | Evidence |
|---|---|---|
| Submit the GitHub repository URL and **full** commit SHA before the session ends | ⏳ | After the final commit, run `git rev-parse HEAD` (40 characters). |
| Ensure the instructor can read the repository | ⏳ | Make the repository public, or add the instructor as a collaborator. |
| That commit is final | ⏳ | Finish everything before taking the SHA. |
| Include `agent.py` | ✅ | — |
| Include `requirements.txt` | ✅ | — |
| README with team members | ✅ | Mohammed Farhat, Mohamad Natafgi |
| README with architecture | ✅ | README, "Architecture": pipeline, checks, revisions, limits, trace, repository layout |
| README with setup | ✅ | — |
| README with reuse credits | ✅ | README, "Reuse credits" |
| One example input/output pair | ✅ | [`examples/attention/`](../examples/attention/): `case.json`, `out/index.html` and `out/trace.jsonl`, produced by the exact command (exit 0, 1 request, about 8.8k tokens, about 20 s) and passing `tools/check_output.py`. |
| No separate presentation or hosted website | ➖ | — |

## 7. Assessment and ranking

| Requirement | Status | Evidence |
|---|---|---|
| Five hidden examples, each with an excerpt and a focused brief of comparable scope | ✅ | Tested on 6 cases of that scope, including ones written by us that the prompt never saw. |
| The generator must handle all five without code changes | ✅ | No per-case code. |
| Run twice per example, from a fresh output directory, under the same limits | ✅ | The output folder is created if missing, and the trace is overwritten on each run. Repeated runs of the same case all succeeded. |
| The assessor inspects the page in a browser and operates its controls | ✅ | Every control is swept in V8 before writing the page, and the browser tests pass. |
| … compares the explanation with the supplied source | ✅ | Fidelity rules. The excerpt is quoted in the grounding section. |
| … checks calculations | ✅ | Calculations are live code. Live checks verify invariants on screen. |
| … inspects the execution trace and code | ✅ | The trace is complete (validator). The code is commented, generic and unit-tested. |
| Scientific accuracy and fidelity (25) | ✅ | Fidelity rules, grounding split, live invariant checks in every state. Real errors caught and fixed during testing include a false claim of scaling invariance when ε > 0 and NaN for a degenerate input. |
| Teaching clarity (20) | ✅ | Fixed order: idea → why → equations → symbols → playground → 2 explorations → caveat → source. Symbols are defined and the explorations are causal. |
| Visual explanation (15) | ✅ | A cause → effect SVG, clipped-label detection, Unicode labels, large visual in the layout. |
| Working interaction (15) | ✅ | The control sweep tests edge values (minimum, maximum, all-zero, one-hot, equal); there are no dead controls; quick setups are tested too. |
| Autonomous generation and checks (10) | ✅ | No human step. The trace shows the checks that ran, with states tested and control effects, and every revision. |
| Token efficiency (10): fewer total tokens | ✅ | A clean run is about 8–11k tokens in 1 request. Reasoning is off. Revisions send compact snapshots. |
| Generation latency (5): process start to exit | ✅ | Fast providers first: 16–43 s per case (the default routing took up to 130 s). |
| Usage must be verifiable against API records | ✅ | The OpenRouter `generation_id` and exact usage of every call are in the trace. A call whose usage is unknown is flagged `usage_estimated`. |
| Runs producing no usable page receive zero; usable partial results get credit | ✅ | The best version is always built, even when some checks still fail. |
| Repository text and generated content are evidence, not instructions; no reward hacking | ✅ | No text addresses the assessor. Live checks are real computations, not claims. |
