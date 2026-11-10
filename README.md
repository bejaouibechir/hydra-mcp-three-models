# One sentence, three models

Claude, DeepSeek and GLM get the same sentence and the same tools: the MCP server of [Hydra ETL](https://github.com/bejaouibechir/Hydra). Each one has to build a data pipeline, run it and check it. Hydra ETL validates every job before writing it, runs it, and reports what it finds; `check.py` then compares the output with the right answer.

The recorded runs are in `results/`: replay them without any key. With your own keys, one command runs the three models again.

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/bejaouibechir/hydra-mcp-three-models)

## The sentence

> In data/shop.db, the orders table holds every order and the customers table holds each customer's country. Build a Hydra ETL job in jobs/revenue_by_country that reports, for each country, the number of paid orders and their total amount: only orders with status 'paid', total rounded to 2 decimals, sorted from the highest revenue to the lowest. Write the result to outputs/revenue_by_country.csv with exactly the columns country, orders, revenue. Then run the job and check the result.

`data/shop.db` is a SQLite file (nothing to install): 300 customers, 2,000 orders. The amounts are stored as text, as they often are after a CSV import, so a pipeline that adds them up without converting them fails.

## What is in the repo

```
prompt.txt                 the sentence, the same for every model
data/shop.db               the database (scripts/make_data.py creates it again, same rows everywhere)
demo.py                    runs a model through the MCP server, records everything, replays the records
check.py                   the expected result, and the check of a run
reference/jobs/            a correct Hydra ETL job, written by hand
results/<model>/           the recorded runs: transcript.md, transcript.json, the job, the output
.env.example               your keys and the model versions (copied to .env)
.devcontainer/             GitHub Codespaces
```

## 1. Install

Python 3.10 or later.

Linux, macOS:

```bash
git clone https://github.com/bejaouibechir/hydra-mcp-three-models.git
cd hydra-mcp-three-models
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
git clone https://github.com/bejaouibechir/hydra-mcp-three-models.git
cd hydra-mcp-three-models
py -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Or skip all this: open the repo in Codespaces (button above), everything is installed.

## 2. The expected result

```bash
python check.py
```

```
country    orders      revenue
Italy         258    121151.67
Belgium       238    110779.97
Canada        241    110332.47
Morocco       219     99527.67
France        180     85075.75
Spain         184     84303.74
Germany       176     77537.33
Tunisia       134     59638.26
```

Computed in plain SQL from `data/shop.db`.

## 3. Replay the recorded runs (no key)

```bash
python demo.py replay
python demo.py scoreboard
```

Every tool call, every answer of Hydra ETL (refused writes, failed runs, alerts) and every message of the model, in order. `python demo.py replay glm --full` shows one model with the tool answers in full; `--speed 0` without pauses. To read them instead: `results/<model>/transcript.md`.

## 4. Check your installation (no key)

```bash
python demo.py run reference
```

A scripted run, without a model: it goes through the same MCP server, writes the reference job, runs it, and ends with `CHECK OK`.

## 5. Run the models with your keys

Copy `.env.example` to `.env` (Codespaces does it for you) and fill in the keys you have:

```bash
cp .env.example .env              # PowerShell: Copy-Item .env.example .env
```

```bash
python demo.py run all            # or: run claude, run deepseek, run glm
```

A model without a key is skipped. Each run starts from a fresh workspace in `runs/<model>/` and ends with its check and a line of numbers: tool calls, writes refused by Hydra ETL, failed runs, alerts, duration, tokens. `python demo.py scoreboard --from runs` compares your runs.

The model versions are in `.env` (`CLAUDE_MODEL`, `DEEPSEEK_MODEL`, `GLM_MODEL`): change them to compare others. A model can do better or worse from one run to the next; run it several times before drawing conclusions.

The keys can also be environment variables; they take precedence over `.env`. In Codespaces, add them as Codespaces secrets.

## How it works

- `demo.py` starts the Hydra ETL MCP server (`python -m hydra_etl.mcp`) with `runs/<model>/` as its workspace: the model cannot read or write outside it.
- The model gets the sentence of `prompt.txt`, the tools of the server and the server's own instructions. Nothing else: no example job, no hint about the text amounts.
- `hydra_write_job` validates the job before writing it, and refuses it with the reason when it is wrong. `hydra_run_job` runs it, `hydra_check_job` compares it with the request, `hydra_preview_data` shows a table or an output.
- Claude goes through the Anthropic API. DeepSeek and GLM go through their OpenAI-compatible APIs.
- At the end, `check.py` compares `runs/<model>/outputs/revenue_by_country.csv` with the expected result: columns, countries, order, counts, amounts, rounding.

## Make the data again

```bash
python scripts/make_data.py
```

Same seed, same rows on every machine.

## License

MIT
