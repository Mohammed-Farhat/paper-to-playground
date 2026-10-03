# paper-to-playground

Agent that turns a research-paper excerpt and a learning brief into one interactive, self-contained HTML explanation (EECE503P/798S Agentic Systems hackathon).

## Team members

- Mohammed Farhat: agent, checks, prompts, pipeline
- Mohamad Natafgi: page design (`templates/page.html`)

## Model

`MODEL_ID` = **`deepseek/deepseek-v4.1-flash`** (DeepSeek V4.1 Flash via OpenRouter)

## Setup and run

Requires **Python 3.11**. Set your key in the environment variable `OPENROUTER_API_KEY`. The key is never written to disk, logged, or embedded in the page.

```bash
python -m pip install -r requirements.txt
python agent.py --input case.json --output out --model deepseek/deepseek-v4.1-flash
```

- **Input:** `case.json` is a UTF-8 JSON object. The fields `source_url`, `focus` and `audience` are required. Every other string field (for example `title`) is passed to the model. The excerpt is read from `excerpt`, or from a similar name (`passage`, `text`, `content`, …), or else from the longest other text field.
- **Output:**
  - `out/index.html` is a single self-contained page (inline CSS, JavaScript and SVG; equations in MathML; no network access).
  - `out/trace.jsonl` holds one JSON event per line.
- **Exit codes:** 0 = success, 1 = generation failure, 2 = bad input or missing key.

## Example input/output pair

[`examples/attention/`](examples/attention/) holds `case.json` (Attention Is All You Need, Section 3.2.1) and the `out/` it produced with the command above: 2 API requests, about 20.6k tokens, about 28 s. Its trace shows the check-and-revise loop working: the first version's `checks()` crashed when run in V8, the error was sent back in one revision, and the fixed version passed every check.

## Architecture

```
case.json → understand → plan + generate (1 LLM call) → check → [revise, only if a check fails] → build → out/
```

1. **Understand:** finds the excerpt in `case.json`. Very long excerpts are trimmed to the paragraphs most relevant to the brief.
2. **Plan + generate:** a single OpenRouter call (reasoning off, streamed). The model first writes a `plan`: the concept, the section or equation anchor, and a coverage map from every outcome the brief requires to the control, exploration or check that delivers it. It then writes a JSON page spec (idea, why it matters, equations, symbols, controls, two explorations, a caveat, grounding) and four pure JavaScript functions: `compute`, `render` (SVG), `show` (intermediate values) and `checks` (live invariants). A generic template and helper library (`templates/`) do the layout, controls and charts, so the model writes only what is specific to the paper.
3. **Check:** these checks are deterministic and cost no tokens. Every result is written to the trace.
   - **Spec structure:** all required parts are present.
   - **Static code rules:** offline, pure, deterministic code.
   - **Execution in V8 (`mini-racer`)** of the default state, both exploration presets, edge values of every control and the known-answer tests. It catches exceptions, NaN or Infinity, malformed SVG, cut-off labels, failing live checks, and controls that have no effect.
4. **Revise:** only on failure, at most 2 rounds. The model receives the problem list and a compact snapshot of the current version. The best version seen is kept, and revising stops early when a round makes no progress.
5. **Build:** fills `templates/page.html`. Model text is HTML-escaped and `$TeX$` is converted to MathML at build time.

**Limits** (`p2p/llm.py`): every HTTP attempt counts toward the 10-request limit. `max_tokens` is capped at the remainder of the 30,000 completion tokens. A streaming deadline keeps each run under 10 minutes. Providers are requested in the order BaseTen, then Together (fallback allowed; the model ID is unchanged), because they were measured fastest.

**Trace:** each event has `stage`, `action`, `result` and `t` (seconds since start). Each model call adds prompt, completion, reasoning and cached tokens, the OpenRouter `generation_id`, the provider and its elapsed time. Check events, revisions and a final summary are logged too. No key and no reasoning text is ever logged.

**Repository layout:**
- `agent.py`: command-line entry point
- `p2p/`: pipeline, OpenRouter client, prompts, parsing, checks, V8 runner, TeX→MathML, page builder
- `templates/`: page design, helper library, browser runtime
- `cases/`: our practice inputs
- `tests/`: unit tests (`python -m unittest discover -s tests`)
- `tools/check_output.py`: validates an output folder against the output rules
- `docs/`: assignment text and requirements checklist

## Reuse credits

- **Libraries:**
  - `requests`: Apache-2.0
  - `mini-racer`: ISC; it embeds Google V8, BSD-3-Clause
  - `urllib3`: MIT
  - `charset-normalizer`: MIT
  - `idna`: BSD-3-Clause
  - `certifi`: MPL-2.0
- **Chart colours:** the Okabe–Ito colour-blind-safe palette (Okabe & Ito, 2008).
- **Our own code:** the TeX→MathML converter, the helper library, the runtime and all other code were written for this project; no third-party code was copied. The page design is by Mohamad Natafgi.
- **Practice inputs:** paraphrased excerpts from the cited papers: Vaswani et al. 2017; Shannon 1948; Kingma & Ba 2015; Hinton et al. 2015; Ioffe & Szegedy 2015; Hinton et al. 2012.
- **AI assistance:** development used an AI coding assistant (Claude Code), as the hackathon permits.
