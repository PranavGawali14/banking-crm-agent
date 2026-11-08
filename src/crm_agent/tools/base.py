"""Tool abstraction + registry.

Every capability the agent has is a ``Tool``: a name, a natural-language description, a
Pydantic argument model (=> JSON-schema, usable for LLM function-calling) and a ``run`` method
that returns a uniform ``ToolResult``. Adding a capability = add one class + register it.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, ValidationError

from crm_agent.config import Settings
from crm_agent.data.repository import CustomerRepository
from crm_agent.llm.base import LLMClient
from crm_agent.models import ToolResult
from crm_agent.outreach.compliance import ComplianceChecker
from crm_agent.outreach.composer import OutreachComposer
from crm_agent.scoring.propensity import PropensityModelRegistry


class ToolArgs(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")


@dataclass
class ToolContext:
    """Shared dependencies injected into tools (dependency-injection, no globals)."""

    settings: Settings
    repo: CustomerRepository
    products: dict
    compliance_rules: dict
    models: PropensityModelRegistry
    composer: OutreachComposer
    checker: ComplianceChecker
    llm: LLMClient

    @classmethod
    def build(cls, settings: Settings, llm: LLMClient, repo: CustomerRepository | None = None) -> "ToolContext":
        repo = repo or CustomerRepository(settings.db_path)
        products = json.loads(Path(settings.products_path).read_text())
        rules = json.loads(Path(settings.compliance_path).read_text())
        return cls(settings=settings, repo=repo, products=products, compliance_rules=rules,
                   models=PropensityModelRegistry(repo, products, settings.model_dir),
                   composer=OutreachComposer(llm, settings, rules), checker=ComplianceChecker(rules), llm=llm)


class Tool(ABC):
    name: ClassVar[str]
    description: ClassVar[str]
    Args: ClassVar[type[ToolArgs]]

    def __call__(self, ctx: ToolContext, **kwargs: Any) -> ToolResult:
        try:
            args = self.Args(**kwargs)
        except ValidationError as exc:
            return ToolResult(ok=False, error=f"invalid arguments: {exc.errors()[:2]}", summary="argument validation failed")
        try:
            return self.run(ctx, args)
        except Exception as exc:  # tools must never crash the agent loop
            return ToolResult(ok=False, error=f"{type(exc).__name__}: {exc}", summary="tool raised an error")

    @abstractmethod
    def run(self, ctx: ToolContext, args: Any) -> ToolResult: ...

    @classmethod
    def schema(cls) -> dict:
        return {"name": cls.name, "description": cls.description, "parameters": cls.Args.model_json_schema()}


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise KeyError(f"unknown tool '{name}'")
        return self._tools[name]

    def names(self) -> list[str]:
        return list(self._tools)

    def schemas(self) -> list[dict]:
        return [t.schema() for t in self._tools.values()]
