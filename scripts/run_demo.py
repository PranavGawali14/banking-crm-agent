"""Scripted multi-turn demo covering the evaluated use cases.

    python scripts/run_demo.py               # prints to terminal
    python scripts/run_demo.py --save        # also writes docs/sample_run.md

Use case 1 – the assignment prompt (personal loan + WhatsApp) and conversational follow-ups
Use case 2 – cross-sell a different product (credit card) + switch channel
Use case 3 – explainability / customer 360 / FD for retirees with self-correcting reflection
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rich.console import Console  # noqa: E402
from rich.markdown import Markdown  # noqa: E402
from rich.rule import Rule  # noqa: E402

from crm_agent.agent.orchestrator import CRMAgent  # noqa: E402
from crm_agent.agent.responder import to_markdown  # noqa: E402

SCENARIOS = {
    "Use case 1 – Personal-loan prospecting with personalised WhatsApp outreach": [
        "Find high-value customers likely to convert for a personal loan this month and generate personalized WhatsApp messages.",
        "Only show the ones in Delhi or Mumbai",
        "Rewrite the messages in Hindi",
        "Why was {first} selected?",
    ],
    "Use case 2 – Credit-card upgrade campaign, then switch channel": [
        "Which salaried customers should get a credit card upgrade? Top 5",
        "Send them as email instead",
        "Export this campaign",
    ],
    "Use case 3 – Customer 360, explainability and self-correction": [
        "Tell me about C0042",
        "Find fixed deposit prospects among retirees in Chennai and draft SMS messages",
        "What products do we have?",
    ],
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", action="store_true", help="write a markdown transcript to docs/sample_run.md")
    ap.add_argument("--trace", action="store_true", help="print the reasoning trace for each turn")
    args = ap.parse_args()

    console = Console(width=140)
    agent = CRMAgent(session_id="demo", persist=False)
    agent.reset()
    transcript = [f"# Sample run\n\nLLM: `{agent.llm.name}` · data as of {agent.ctx.repo.as_of_date}\n"]
    for title, turns in SCENARIOS.items():
        console.print(Rule(f"[bold magenta]{title}"))
        transcript.append(f"\n---\n\n## {title}\n")
        agent.reset()
        for q in turns:
            if "{first}" in q:
                q = q.format(first=agent.state.prospects[0]["full_name"] if agent.state.prospects else "Priya")
            console.print(f"\n[bold cyan]RM ›[/] {q}")
            resp = agent.chat(q)
            if args.trace:
                for e in resp.trace:
                    console.print(f"  [dim]{e.step_id:<8} {e.tool:<28} {e.summary}[/]")
            md = to_markdown(resp)
            console.print(Markdown(md))
            trace_md = "\n".join(f"| {e.step_id} | `{e.tool}` | {e.description} | {e.summary} |" for e in resp.trace)
            transcript.append(f"\n### 🧑‍💼 RM: {q}\n\n<details><summary>Reasoning trace ({len(resp.trace)} steps)</summary>\n\n"
                              f"| step | tool | why | result |\n|---|---|---|---|\n{trace_md}\n\n</details>\n\n{md}\n")
    if args.save:
        out = ROOT / "docs" / "sample_run.md"
        out.write_text("\n".join(transcript), encoding="utf-8")
        console.print(f"\n[green]Transcript saved to {out}[/]")


if __name__ == "__main__":
    main()
