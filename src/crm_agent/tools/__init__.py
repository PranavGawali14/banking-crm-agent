from crm_agent.tools.base import Tool, ToolContext, ToolRegistry
from crm_agent.tools.crm_tools import AnalyzeTransactions, GetCustomerProfile, SearchCustomers
from crm_agent.tools.outreach_tools import CheckMessageCompliance, ExportCampaign, GenerateOutreachMessages
from crm_agent.tools.scoring_tools import (CheckProductEligibility, ListProducts, RecommendProducts,
                                           ScoreConversionPropensity, ScoreCustomerValue)

ALL_TOOLS = [
    SearchCustomers, GetCustomerProfile, AnalyzeTransactions, ScoreCustomerValue, CheckProductEligibility,
    ScoreConversionPropensity, RecommendProducts, GenerateOutreachMessages, CheckMessageCompliance,
    ExportCampaign, ListProducts,
]


def default_registry() -> ToolRegistry:
    reg = ToolRegistry()
    for cls in ALL_TOOLS:
        reg.register(cls())
    return reg


__all__ = ["Tool", "ToolContext", "ToolRegistry", "default_registry", "ALL_TOOLS"]
