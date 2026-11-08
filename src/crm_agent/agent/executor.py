"""Executor: runs a ``Plan`` step-by-step against the tool registry.

* Resolves each step's ``inputs`` from the blackboard (supports dotted paths, e.g.
  ``eligibility.eligible``) and merges them with static ``args``.
* Records a ``TraceEvent`` per step (status, summary, latency) – the reasoning trace shown to the RM.
* Fails fast: if a tool errors, later dependent steps are marked ``skipped``.
* Early exit: a tool can return ``halt=True`` (e.g. the funnel is empty) – remaining steps are
  skipped without being an error, which lets the orchestrator's reflection step take over.
"""

from __future__ import annotations

import time
from typing import Any, Callable

from crm_agent.models import Plan, ToolResult, TraceEvent
from crm_agent.tools.base import ToolContext, ToolRegistry


def resolve_path(blackboard: dict, path: str) -> Any:
    value: Any = blackboard
    for part in path.split("."):
        if isinstance(value, dict):
            value = value[part]
        else:
            value = getattr(value, part)
    return value


class Executor:
    def __init__(self, registry: ToolRegistry, ctx: ToolContext, on_event: Callable[[TraceEvent], None] | None = None):
        self.registry = registry
        self.ctx = ctx
        self.on_event = on_event

    def run(self, plan: Plan, blackboard: dict) -> tuple[dict, list[TraceEvent], dict[str, ToolResult]]:
        trace: list[TraceEvent] = []
        results: dict[str, ToolResult] = {}
        failed = halted = False
        for step in plan.steps:
            if failed or halted:
                reason = "an earlier step failed" if failed else "no candidates left to act on"
                ev = TraceEvent(step_id=step.id, tool=step.tool, description=step.description, status="skipped",
                                summary=f"skipped – {reason}")
                trace.append(ev)
                self._emit(ev)
                continue
            start = time.perf_counter()
            try:
                kwargs = {**step.args, **{arg: resolve_path(blackboard, ref) for arg, ref in step.inputs.items()}}
                result = self.registry.get(step.tool)(self.ctx, **kwargs)
            except (KeyError, AttributeError) as exc:
                result = ToolResult(ok=False, error=f"missing input {exc}", summary="could not resolve inputs")
            ms = (time.perf_counter() - start) * 1000
            results[step.id] = result
            if result.ok and step.output_key:
                blackboard[step.output_key] = result.data
            ev = TraceEvent(step_id=step.id, tool=step.tool, description=step.description,
                            status="ok" if result.ok else "error",
                            summary=result.summary if result.ok else f"{result.summary}: {result.error}", duration_ms=round(ms, 1))
            trace.append(ev)
            self._emit(ev)
            failed = not result.ok
            halted = result.ok and result.halt
        return blackboard, trace, results

    def _emit(self, ev: TraceEvent) -> None:
        if self.on_event:
            self.on_event(ev)
