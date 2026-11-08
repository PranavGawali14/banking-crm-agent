"""Interactive terminal chat for the Relationship Manager.

    python -m crm_agent.interfaces.cli                # new session
    python -m crm_agent.interfaces.cli --session demo # resume / name a session
    python -m crm_agent.interfaces.cli --trace        # stream the reasoning trace live
    python -m crm_agent.interfaces.cli -q "Find personal loan prospects in Pune"   # one-shot
"""

from __future__ import annotations

import argparse
import json

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from crm_agent.agent.orchestrator import CRMAgent
from crm_agent.models import AgentResponse, TraceEvent

console = Console()
STATUS_STYLE = {"ok": "green", "error": "red", "skipped": "yellow", "info": "cyan"}


def render_trace(trace: list[TraceEvent]) -> None:
    table = Table(title="Reasoning trace", show_lines=False, expand=True)
    for col in ("step", "tool", "why", "result", "ms"):
        table.add_column(col, overflow="fold")
    for e in trace:
        table.add_row(e.step_id, f"[{STATUS_STYLE[e.status]}]{e.tool}[/]", e.description, e.summary, f"{e.duration_ms:.0f}")
    console.print(table)


def render(resp: AgentResponse, show_trace: bool) -> None:
    if show_trace and resp.trace:
        render_trace(resp.trace)
    console.print(Markdown(resp.text))
    for m in resp.messages:
        flag = "green" if (m.compliance_passed and m.deliverable) else "yellow"
        title = f"{m.customer_name} · {m.channel} · {m.language} · {m.generated_by}"
        body = (f"[bold]Subject:[/] {m.subject}\n\n" if m.subject else "") + m.body
        if m.compliance_notes:
            body += f"\n\n[dim]compliance: {'; '.join(m.compliance_notes)}[/]"
        console.print(Panel(body, title=title, border_style=flag, expand=False))


def main() -> None:
    ap = argparse.ArgumentParser(description="Banking CRM agent – chat")
    ap.add_argument("--session", default=None, help="session id to create/resume")
    ap.add_argument("--trace", action="store_true", help="show the reasoning trace for every turn")
    ap.add_argument("-q", "--query", default=None, help="run a single query and exit")
    args = ap.parse_args()

    live = (lambda e: console.print(f"  [dim]→ {e.step_id} {e.tool}: {e.summary}[/]")) if args.trace else None
    with console.status("Loading CRM data & models…"):
        agent = CRMAgent(session_id=args.session, on_event=live)
    if args.query:
        render(agent.chat(args.query), show_trace=False)
        return

    console.print(Panel.fit(
        f"[bold]NovaBank RM Co-pilot[/] · LLM: [cyan]{agent.llm.name}[/] · data as of {agent.ctx.repo.as_of_date} · "
        f"session [magenta]{agent.state.session_id}[/]\nType a request, or /help · /trace · /state · /tools · /reset · /quit"))
    while True:
        try:
            q = console.input("\n[bold cyan]RM ›[/] ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q:
            continue
        if q in ("/quit", "/exit", "quit", "exit"):
            break
        if q == "/trace":
            render_trace(agent.state.last_trace)
            continue
        if q == "/state":
            console.print_json(json.dumps(agent.state.context_summary(), default=str))
            continue
        if q == "/tools":
            for s in agent.registry.schemas():
                console.print(f"[bold]{s['name']}[/] – {s['description']}")
            continue
        if q == "/reset":
            agent.reset()
            console.print("[green]Memory cleared.[/]")
            continue
        q = "help" if q == "/help" else q
        with console.status("Thinking…"):
            resp = agent.chat(q)
        render(resp, show_trace=False)
    console.print("[dim]Bye![/]")


if __name__ == "__main__":
    main()
