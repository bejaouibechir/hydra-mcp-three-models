"""One sentence, three models: Claude, DeepSeek and GLM build the same Hydra ETL job
through Hydra ETL's MCP server.

    python demo.py replay                 # replays the recorded runs (no key needed)
    python demo.py replay deepseek        # one model only
    python demo.py run reference          # scripted run, no key: checks your installation
    python demo.py run claude             # live run with your key (see .env.example)
    python demo.py run all                # the three models, one after the other
    python demo.py scoreboard             # summary of the runs

Each run gets a fresh workspace in runs/<model>/ (a copy of data/shop.db, empty jobs/
and outputs/). The model only sees the sentence of prompt.txt and the tools of the
Hydra ETL MCP server; everything it does is written to runs/<model>/transcript.json
and transcript.md. Add --save to copy the run to results/<model>/ (the recorded runs).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from check import check

ROOT = Path(__file__).resolve().parent
PROMPT = (ROOT / "prompt.txt").read_text(encoding="utf-8").strip()
MODELS = ["claude", "deepseek", "glm"]
SYSTEM = ("You work in a Hydra ETL project through the tools of its MCP server. "
          "Paths are relative to the project root. Do the task completely, then give a short summary.")

# ---------------------------------------------------------------- settings

def load_env(path: Path = ROOT / ".env") -> None:
    """Reads .env (KEY=value lines) without overriding variables already set."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip().strip('"').strip("'")
        if v:
            os.environ.setdefault(k.strip(), v)


def settings(model: str) -> dict:
    e = os.environ.get
    if model == "claude":
        return {"kind": "anthropic", "key": e("ANTHROPIC_API_KEY"), "key_name": "ANTHROPIC_API_KEY",
                "model": e("CLAUDE_MODEL", "claude-sonnet-4-6")}
    if model == "deepseek":
        return {"kind": "openai", "key": e("DEEPSEEK_API_KEY"), "key_name": "DEEPSEEK_API_KEY",
                "model": e("DEEPSEEK_MODEL", "deepseek-v4-pro"),
                "base_url": e("DEEPSEEK_BASE_URL", "https://api.deepseek.com")}
    if model == "glm":
        return {"kind": "openai", "key": e("ZAI_API_KEY"), "key_name": "ZAI_API_KEY",
                "model": e("GLM_MODEL", "glm-5.2"),
                "base_url": e("GLM_BASE_URL", "https://api.z.ai/api/paas/v4/")}
    if model == "reference":
        return {"kind": "reference", "model": "scripted (no model)"}
    raise SystemExit(f"unknown model: {model} (claude, deepseek, glm, reference)")

# ---------------------------------------------------------------- recording

class Recorder:
    def __init__(self, model: str, provider_model: str, ws: Path):
        self.ws = ws
        self.t0 = time.time()
        self.data = {"model": model, "provider_model": provider_model, "prompt": PROMPT,
                     "started": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     "events": [], "tokens": {"input": 0, "output": 0}, "turns": 0}

    def event(self, kind: str, **kw) -> None:
        ev = {"t": round(time.time() - self.t0, 1), "kind": kind, **kw}
        self.data["events"].append(ev)
        show(ev)

    def tokens(self, inp: int | None, out: int | None) -> None:
        self.data["tokens"]["input"] += inp or 0
        self.data["tokens"]["output"] += out or 0

    def finish(self, stopped: str) -> dict:
        d = self.data
        d["duration_s"] = round(time.time() - self.t0, 1)
        d["stopped"] = stopped
        calls = [e for e in d["events"] if e["kind"] == "tool_result"]
        d["stats"] = {
            "tool_calls": len(calls),
            "writes_refused": sum(e["name"] == "hydra_write_job" and e["text"].startswith("REFUSED") for e in calls),
            "runs_failed": sum(e["name"] == "hydra_run_job" and "FAILED" in e["text"][:200] for e in calls),
            "runs_succeeded": sum(e["name"] == "hydra_run_job" and "RUN SUCCEEDED" in e["text"][:200] for e in calls),
            "alerts": sum(e["name"] == "hydra_check_job" and e["text"].startswith("ALERTS") for e in calls),
        }
        ok, problems = check(self.ws)
        d["check"] = {"ok": ok, "problems": problems}
        (self.ws / "transcript.json").write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
        (self.ws / "transcript.md").write_text(to_markdown(d), encoding="utf-8")
        return d

# ---------------------------------------------------------------- display

if os.name == "nt":
    os.system("")  # turns on ANSI colors in the Windows console
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

C = {"dim": "\033[2m", "cyan": "\033[36m", "yellow": "\033[33m", "green": "\033[32m",
     "red": "\033[31m", "bold": "\033[1m", "off": "\033[0m"}
if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
    C = {k: "" for k in C}
FULL = False


def clip(text: str, n: int = 14) -> str:
    lines = text.rstrip().splitlines()
    if FULL or len(lines) <= n:
        return "\n".join(lines)
    return "\n".join(lines[:n] + [f"... ({len(lines) - n} more lines, --full to see them)"])


def indent(text: str, pad: str = "    ") -> str:
    return "\n".join(pad + l for l in text.splitlines())


def show(ev: dict) -> None:
    k, t = ev["kind"], f"{C['dim']}[{ev['t']:>6.1f}s]{C['off']}"
    if k == "assistant" and ev["text"].strip():
        print(f"{t} {C['bold']}model{C['off']}\n{indent(ev['text'].strip())}")
    elif k == "tool_call":
        args = ", ".join(f"{a}={short(v)}" for a, v in ev["args"].items())
        print(f"{t} {C['cyan']}→ {ev['name']}({args}){C['off']}")
    elif k == "tool_result":
        head = ev["text"].lstrip()[:40]
        color = C["red"] if head.startswith(("REFUSED", "FAILED", "ALERTS", "Error")) else \
            C["green"] if head.startswith(("WRITTEN", "RUN SUCCEEDED", "NO ALERT", "VALID")) else C["dim"]
        print(f"{color}{indent(clip(ev['text']), '      ')}{C['off']}")
    elif k == "error":
        print(f"{t} {C['red']}{ev['text']}{C['off']}")
    sys.stdout.flush()


def short(v) -> str:
    s = v if isinstance(v, str) else json.dumps(v)
    s = s.replace("\n", "⏎")
    return repr(s if len(s) <= 60 else s[:57] + "...")


def to_markdown(d: dict) -> str:
    out = [f"# {d['model']} ({d['provider_model']})", "", f"> {d['prompt']}", ""]
    for ev in d["events"]:
        if ev["kind"] == "assistant" and ev["text"].strip():
            out += [f"**model** ({ev['t']}s)", "", ev["text"].strip(), ""]
        elif ev["kind"] == "tool_call":
            out += [f"**→ {ev['name']}** ({ev['t']}s)", "", "```json", json.dumps(ev["args"], indent=2, ensure_ascii=False), "```", ""]
        elif ev["kind"] == "tool_result":
            out += ["```text", ev["text"].rstrip(), "```", ""]
        elif ev["kind"] == "error":
            out += [f"**error**: {ev['text']}", ""]
    s, c = d["stats"], d["check"]
    out += ["## Result", "",
            f"- check: {'OK' if c['ok'] else 'FAILED'}" + "".join(f"\n  - {p}" for p in c["problems"]),
            f"- tool calls: {s['tool_calls']}, writes refused by Hydra ETL: {s['writes_refused']}, "
            f"failed runs: {s['runs_failed']}, alerts: {s['alerts']}",
            f"- duration: {d['duration_s']} s, model turns: {d['turns']}, "
            f"tokens: {d['tokens']['input']} in / {d['tokens']['output']} out",
            f"- stopped: {d['stopped']}", ""]
    return "\n".join(out)

# ---------------------------------------------------------------- MCP

def workspace(model: str) -> Path:
    ws = ROOT / "runs" / model
    if ws.exists():
        shutil.rmtree(ws)
    (ws / "data").mkdir(parents=True)
    (ws / "jobs").mkdir()
    (ws / "outputs").mkdir()
    shutil.copy2(ROOT / "data" / "shop.db", ws / "data" / "shop.db")
    return ws


def schema_of(tool) -> dict:
    return getattr(tool, "input_schema", None) or getattr(tool, "inputSchema", None) or {"type": "object"}


def result_text(res) -> str:
    parts = [getattr(c, "text", "") for c in res.content]
    text = "\n".join(p for p in parts if p)
    if getattr(res, "is_error", getattr(res, "isError", False)):
        text = "Error: " + text
    return text


async def with_server(ws: Path, body):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    env = dict(os.environ, HYDRA_MCP_WORKSPACE=str(ws), PYTHONIOENCODING="utf-8")
    params = StdioServerParameters(command=sys.executable, args=["-m", "hydra_etl.mcp"], env=env, cwd=str(ws))
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as session:
            init = await session.initialize()
            tools = (await session.list_tools()).tools
            return await body(session, tools, getattr(init, "instructions", "") or "")


async def call(session, rec: Recorder, name: str, args: dict) -> str:
    rec.event("tool_call", name=name, args=args)
    try:
        text = result_text(await session.call_tool(name, args))
    except Exception as exc:  # a tool that crashes is reported to the model, not fatal
        text = f"Error: {type(exc).__name__}: {exc}"
    rec.event("tool_result", name=name, text=text)
    return text

# ---------------------------------------------------------------- models

async def run_anthropic(cfg, session, tools, instructions, rec, max_turns):
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=cfg["key"])
    tdefs = [{"name": t.name, "description": t.description or "", "input_schema": schema_of(t)} for t in tools]
    messages = [{"role": "user", "content": PROMPT}]
    system = SYSTEM + ("\n\n" + instructions if instructions else "")
    for _ in range(max_turns):
        rec.data["turns"] += 1
        resp = await client.messages.create(model=cfg["model"], max_tokens=4096, system=system,
                                            tools=tdefs, messages=messages)
        rec.tokens(resp.usage.input_tokens, resp.usage.output_tokens)
        text = "".join(b.text for b in resp.content if b.type == "text")
        rec.event("assistant", text=text)
        messages.append({"role": "assistant", "content": [b.model_dump(exclude_none=True) for b in resp.content]})
        uses = [b for b in resp.content if b.type == "tool_use"]
        if not uses:
            return "the model finished"
        results = []
        for u in uses:
            out = await call(session, rec, u.name, dict(u.input or {}))
            results.append({"type": "tool_result", "tool_use_id": u.id, "content": out})
        messages.append({"role": "user", "content": results})
    return f"max turns reached ({max_turns})"


async def run_openai(cfg, session, tools, instructions, rec, max_turns):
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=cfg["key"], base_url=cfg["base_url"])
    tdefs = [{"type": "function", "function": {"name": t.name, "description": t.description or "",
                                               "parameters": schema_of(t)}} for t in tools]
    system = SYSTEM + ("\n\n" + instructions if instructions else "")
    messages = [{"role": "system", "content": system}, {"role": "user", "content": PROMPT}]
    for _ in range(max_turns):
        rec.data["turns"] += 1
        resp = await client.chat.completions.create(model=cfg["model"], messages=messages, tools=tdefs)
        if resp.usage:
            rec.tokens(resp.usage.prompt_tokens, resp.usage.completion_tokens)
        msg = resp.choices[0].message
        rec.event("assistant", text=msg.content or "")
        calls = msg.tool_calls or []
        entry = {"role": "assistant", "content": msg.content or ""}
        if calls:
            entry["tool_calls"] = [{"id": c.id, "type": "function",
                                    "function": {"name": c.function.name, "arguments": c.function.arguments or "{}"}}
                                   for c in calls]
        messages.append(entry)
        if not calls:
            return "the model finished"
        for c in calls:
            try:
                args = json.loads(c.function.arguments or "{}")
            except json.JSONDecodeError as exc:
                out = f"Error: the arguments are not valid JSON ({exc})"
                rec.event("tool_call", name=c.function.name, args={"_raw": c.function.arguments})
                rec.event("tool_result", name=c.function.name, text=out)
            else:
                out = await call(session, rec, c.function.name, args)
            messages.append({"role": "tool", "tool_call_id": c.id, "content": out})
    return f"max turns reached ({max_turns})"


async def run_reference(cfg, session, tools, instructions, rec, max_turns):
    """No model: the calls a model is expected to make, with the reference job."""
    job = ROOT / "reference" / "jobs" / "revenue_by_country"
    y = {f.stem: f.read_text(encoding="utf-8") for f in job.glob("*.yaml")}
    rec.event("assistant", text="(scripted reference run: no model, the expected tool calls)")
    await call(session, rec, "hydra_preview_data", {"file_path": "data/shop.db"})
    await call(session, rec, "hydra_list_operations", {})
    await call(session, rec, "hydra_write_job", {
        "job_path": "jobs/revenue_by_country", "sources_yaml": y["sources"],
        "transformations_yaml": y["transformations"], "destinations_yaml": y["destinations"],
        "pipeline_yaml": y["pipeline"]})
    await call(session, rec, "hydra_check_job", {"user_request": PROMPT, "job_path": "jobs/revenue_by_country"})
    await call(session, rec, "hydra_run_job", {"job_path": "jobs/revenue_by_country"})
    await call(session, rec, "hydra_preview_data", {"file_path": "outputs/revenue_by_country.csv", "rows": 10})
    rec.event("assistant", text="Job written, checked and run.")
    return "script finished"


RUNNERS = {"anthropic": run_anthropic, "openai": run_openai, "reference": run_reference}


def run_one(model: str, max_turns: int, save: bool) -> dict | None:
    cfg = settings(model)
    if cfg["kind"] != "reference" and not cfg.get("key"):
        print(f"{C['yellow']}{model}: {cfg['key_name']} is not set (environment or .env) — skipped.{C['off']}")
        return None
    ws = workspace(model)
    print(f"\n{C['bold']}=== {model} — {cfg['model']} ==={C['off']}\n{C['dim']}{PROMPT}{C['off']}\n")
    rec = Recorder(model, cfg["model"], ws)

    async def body(session, tools, instructions):
        return await RUNNERS[cfg["kind"]](cfg, session, tools, instructions, rec, max_turns)

    try:
        stopped = asyncio.run(with_server(ws, body))
    except Exception as exc:
        rec.event("error", text=f"{type(exc).__name__}: {exc}")
        stopped = "error"
    d = rec.finish(stopped)
    summary(d)
    if save:
        dest = ROOT / "results" / model
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(ws, dest, ignore=shutil.ignore_patterns("data", "*.db", ".hydra", "__pycache__"))
        print(f"{C['dim']}saved to results/{model}/{C['off']}")
    return d


def summary(d: dict) -> None:
    s, c = d["stats"], d["check"]
    mark = f"{C['green']}CHECK OK{C['off']}" if c["ok"] else f"{C['red']}CHECK FAILED{C['off']}"
    print(f"\n{C['bold']}{d['model']}{C['off']}: {mark} — {s['tool_calls']} tool calls, "
          f"{s['writes_refused']} writes refused, {s['runs_failed']} failed runs, {s['alerts']} alerts, "
          f"{d['duration_s']} s, {d['tokens']['input']}+{d['tokens']['output']} tokens ({d['stopped']})")
    for p in c["problems"]:
        print(f"  - {p}")

# ---------------------------------------------------------------- replay

def find_transcript(model: str, source: str) -> Path | None:
    for base in ([source] if source else ["results", "runs"]):
        p = ROOT / base / model / "transcript.json"
        if p.exists():
            return p
    return None


def replay(models: list[str], speed: float, source: str) -> None:
    for m in models:
        p = find_transcript(m, source)
        if not p:
            print(f"{C['yellow']}{m}: no recorded run{C['off']}")
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        print(f"\n{C['bold']}=== {m} — {d['provider_model']} (recorded {d['started'][:10]}) ==={C['off']}")
        print(f"{C['dim']}{d['prompt']}{C['off']}\n")
        last = 0.0
        for ev in d["events"]:
            if speed > 0:
                time.sleep(min(max(ev["t"] - last, 0) / speed, 3))
            last = ev["t"]
            show(ev)
        summary(d)
        job = p.parent / "jobs" / "revenue_by_country"
        if job.exists():
            print(f"\n{C['dim']}The job it wrote: {job.relative_to(ROOT)}{C['off']}")


def scoreboard(source: str) -> None:
    rows = []
    for m in MODELS + ["reference"]:
        p = find_transcript(m, source)
        if p:
            d = json.loads(p.read_text(encoding="utf-8"))
            s = d["stats"]
            rows.append((m, d["provider_model"], "OK" if d["check"]["ok"] else "FAILED", s["tool_calls"],
                         s["writes_refused"], s["runs_failed"], s["alerts"], d["duration_s"],
                         d["tokens"]["input"] + d["tokens"]["output"]))
    if not rows:
        print("no run yet")
        return
    head = ("model", "version", "check", "tool calls", "refused", "failed runs", "alerts", "seconds", "tokens")
    w = [max(len(str(r[i])) for r in rows + [head]) for i in range(len(head))]
    for r in [head] + rows:
        print("  ".join(str(v).ljust(w[i]) for i, v in enumerate(r)))

# ---------------------------------------------------------------- main

def main() -> None:
    global FULL
    ap = argparse.ArgumentParser(description="One sentence, three models, through Hydra ETL's MCP server.")
    ap.add_argument("command", choices=["run", "replay", "scoreboard"])
    ap.add_argument("model", nargs="?", default="all", help="claude, deepseek, glm, reference or all")
    ap.add_argument("--max-turns", type=int, default=30)
    ap.add_argument("--save", action="store_true", help="run: copy the run to results/<model>/")
    ap.add_argument("--speed", type=float, default=4.0, help="replay: x times faster than real time, 0 = no pause")
    ap.add_argument("--from", dest="source", default="", choices=["", "results", "runs"],
                    help="replay/scoreboard: recorded runs (results) or your runs (runs); default: results, then runs")
    ap.add_argument("--full", action="store_true", help="show the tool answers in full")
    a = ap.parse_args()
    FULL = a.full
    load_env()
    models = MODELS if a.model == "all" else [a.model]
    if a.command == "run":
        for m in models:
            run_one(m, a.max_turns, a.save)
        if len(models) > 1:
            print()
            scoreboard("runs")
    elif a.command == "replay":
        replay(models if a.model != "all" else MODELS + ["reference"], a.speed, a.source)
    else:
        scoreboard(a.source)


if __name__ == "__main__":
    main()
