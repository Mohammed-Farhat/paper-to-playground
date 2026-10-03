# paper-to-playground

Agent that turns a research-paper excerpt into an interactive, self-contained HTML explanation (EECE503P/798S Agentic Systems hackathon).

## Team members

- Mohammed Farhat
- Mohamad Natafgi

## Model

`MODEL_ID` = **`deepseek/deepseek-v4.1-flash`** (DeepSeek V4.1 Flash via OpenRouter)

## Setup and run

Requires **Python 3.11**.

```bash
python -m pip install -r requirements.txt
python agent.py --input case.json --output out --model deepseek/deepseek-v4.1-flash
```

The OpenRouter key is read from the `OPENROUTER_API_KEY` environment variable. It is never written to disk, logged, or embedded in the page.

## Input format

`case.json` is a UTF-8 JSON object of string fields. `source_url`, `focus` and `audience` are required. Any other string fields (for example `title` or `excerpt`) are passed to the agent as extra source context. Practice inputs are in [`cases/`](cases/).

## Output

- `out/index.html`: a single self-contained page (embedded CSS/JS/SVG, no network access needed).
- `out/trace.jsonl`: one JSON event per line (stage, action, result, token usage, elapsed seconds, checks, failures, revisions).

## Architecture

_(to be completed)_

## Reuse credits

_(to be completed)_
