"""Decisioning tools: value scoring, eligibility, conversion propensity, product recommendation."""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any, Optional

from crm_agent.models import ToolResult
from crm_agent.scoring.eligibility import check_eligibility
from crm_agent.scoring.offers import build_offer
from crm_agent.scoring.propensity import HeuristicPropensityModel, calibrate_monthly, explain
from crm_agent.scoring.value import score_value
from crm_agent.tools.base import Tool, ToolArgs, ToolContext


def _valid_product(ctx: ToolContext, product_id: str) -> None:
    if product_id not in ctx.products:
        raise ValueError(f"unknown product '{product_id}'. Known: {', '.join(ctx.products)}")


REASON_KEYS = [("age", "age"), ("income", "low income"), ("credit score", "credit score"), ("debt-to-income", "high DTI"),
               ("employment", "employment type"), ("already holds", "already holds product"), ("KYC", "KYC pending"),
               ("already contacted", "contact cool-down")]


def _reason_key(reason: str) -> str:
    return next((label for prefix, label in REASON_KEYS if reason.startswith(prefix)), reason)


class ScoreCustomerValue(Tool):
    name = "score_customer_value"
    description = "Score each customer's value to the bank (income, balances, tenure, product depth, engagement) and keep those above a threshold."

    class Args(ToolArgs):
        customers: list[dict[str, Any]]
        features: dict[str, Any] = {}
        min_score: float = 0.0

    def run(self, ctx: ToolContext, args: Args) -> ToolResult:
        scored = [{**c, **score_value(c, args.features.get(c["customer_id"]))} for c in args.customers]
        kept = sorted((c for c in scored if c["value_score"] >= args.min_score), key=lambda c: c["value_score"], reverse=True)
        tiers = Counter(c["value_tier"] for c in kept)
        mix = f" ({', '.join(f'{k}: {v}' for k, v in tiers.most_common())})" if kept else ""
        return ToolResult(data=kept, halt=not kept,
                          summary=f"{len(kept)}/{len(scored)} customers have value score ≥ {args.min_score:g}{mix}")


class CheckProductEligibility(Tool):
    name = "check_product_eligibility"
    description = "Apply the product's hard credit-policy rules (age, income, credit score, DTI, KYC, existing holdings, contact cool-down)."

    class Args(ToolArgs):
        customers: list[dict[str, Any]]
        features: dict[str, Any] = {}
        product_id: str

    def run(self, ctx: ToolContext, args: Args) -> ToolResult:
        _valid_product(ctx, args.product_id)
        cfg, as_of = ctx.products[args.product_id], ctx.repo.as_of_date
        eligible, rejected, counts = [], [], Counter()
        for c in args.customers:
            res = check_eligibility(c, args.features.get(c["customer_id"]), args.product_id, cfg, as_of, ctx.settings.contact_cooldown_days)
            if res["eligible"]:
                eligible.append({**c, "eligibility_warnings": res["warnings"]})
            else:
                rejected.append({"customer_id": c["customer_id"], "full_name": c["full_name"], "reasons": res["fail_reasons"]})
                for r in res["fail_reasons"]:
                    counts[_reason_key(r)] += 1
        top = ", ".join(f"{k}: {v}" for k, v in counts.most_common(4))
        return ToolResult(data={"eligible": eligible, "rejected": rejected, "rejection_counts": dict(counts)}, halt=not eligible,
                          summary=f"{len(eligible)} eligible for {cfg['name']}, {len(rejected)} rejected" + (f" (top reasons – {top})" if top else ""))


class ScoreConversionPropensity(Tool):
    name = "score_conversion_propensity"
    description = ("Estimate each customer's probability of converting on the product this month with an explainable model "
                   "(logistic regression trained on past campaigns, or heuristic for cold-start products); rank and shortlist.")

    class Args(ToolArgs):
        customers: list[dict[str, Any]]
        features: dict[str, Any]
        product_id: str
        min_propensity: float = 0.0
        top_k: Optional[int] = None

    def run(self, ctx: ToolContext, args: Args) -> ToolResult:
        _valid_product(ctx, args.product_id)
        model = ctx.models.get(args.product_id)
        as_of: date = ctx.repo.as_of_date
        ranked = []
        for c in args.customers:
            f = args.features[c["customer_id"]]
            prob, contrib = model.predict(f)
            days = None
            if c.get("last_contacted_date"):
                days = (as_of - date.fromisoformat(c["last_contacted_date"])).days
            prob = calibrate_monthly(prob, days)
            drivers, risks = explain(contrib)
            value = c.get("value_score", 50.0)
            ranked.append({
                **c, "propensity": round(prob, 3), "propensity_pct": round(prob * 100),
                "priority_score": round(0.7 * prob + 0.3 * value / 100, 3),
                "drivers": drivers, "risk_factors": risks,
                "contributions": {k: round(v, 3) for k, v in contrib.items()},
                "signals": f["signals"], "feature_summary": f["summary"], "model": model.name,
            })
        ranked.sort(key=lambda r: r["priority_score"], reverse=True)
        above = [r for r in ranked if r["propensity"] >= args.min_propensity]
        shortlist = above[: args.top_k] if args.top_k else above
        metrics = getattr(model, "metrics", {})
        mtxt = f", held-out AUC {metrics['test_auc']}" if metrics.get("test_auc") else ""
        return ToolResult(
            halt=not shortlist,
            data={"ranked": shortlist, "below_threshold": len(ranked) - len(above), "scored": len(ranked),
                  "model": model.name, "model_metrics": metrics},
            summary=(f"Scored {len(ranked)} customers with {model.name}{mtxt}; {len(above)} ≥ {args.min_propensity:.0%} propensity, "
                     f"shortlisted {len(shortlist)}"))


class RecommendProducts(Tool):
    name = "recommend_products"
    description = "Build an indicative offer (amount, rate, EMI / limit) for the requested product and find the next-best product to cross-sell."

    class Args(ToolArgs):
        customers: list[dict[str, Any]]
        features: dict[str, Any]
        primary_product_id: Optional[str] = None

    def _next_best(self, ctx: ToolContext, c: dict, f: dict, exclude: set[str]) -> list[tuple[str, float]]:
        from crm_agent.scoring.eligibility import check_eligibility

        out = []
        for pid, cfg in ctx.products.items():
            if pid in exclude or pid in c.get("existing_products", []):
                continue
            if not check_eligibility(c, f, pid, cfg, ctx.repo.as_of_date, ctx.settings.contact_cooldown_days)["eligible"]:
                continue
            p, _ = HeuristicPropensityModel(pid, cfg["signals"]).predict(f)
            out.append((pid, p))
        return sorted(out, key=lambda x: x[1], reverse=True)

    def run(self, ctx: ToolContext, args: Args) -> ToolResult:
        if args.primary_product_id:
            _valid_product(ctx, args.primary_product_id)
        out, cross = [], Counter()
        for c in args.customers:
            f = args.features.get(c["customer_id"])
            primary = args.primary_product_id
            options = self._next_best(ctx, c, f, {primary} if primary else set())
            if not primary and options:
                primary = options.pop(0)[0]
            offer = build_offer(c, f, ctx.products[primary]) if primary else None
            nb = options[0] if options else None
            if nb:
                cross[ctx.products[nb[0]]["name"]] += 1
            out.append({**c, "recommended_product": primary,
                        "recommended_product_name": ctx.products[primary]["name"] if primary else None,
                        "offer": offer,
                        "next_best_product": nb[0] if nb else None,
                        "next_best_product_name": ctx.products[nb[0]]["name"] if nb else None,
                        "next_best_propensity": round(nb[1], 2) if nb else None})
        summary = f"Built offers for {sum(1 for o in out if o['offer'])}/{len(out)} customers"
        if cross:
            summary += "; top cross-sell: " + ", ".join(f"{k} ({v})" for k, v in cross.most_common(2))
        return ToolResult(data=out, summary=summary)


class ListProducts(Tool):
    name = "list_products"
    description = "List the bank's product catalogue with key eligibility criteria."

    class Args(ToolArgs):
        pass

    def run(self, ctx: ToolContext, args: Args) -> ToolResult:
        rows = [{"product_id": pid, "name": p["name"], "category": p["category"],
                 "min_income": p["eligibility"]["min_annual_income"], "min_credit_score": p["eligibility"]["min_credit_score"],
                 "age": f"{p['eligibility']['min_age']}-{p['eligibility']['max_age']}",
                 "model": ctx.models.get(pid).name} for pid, p in ctx.products.items()]
        return ToolResult(data=rows, summary=f"{len(rows)} products in catalogue")
