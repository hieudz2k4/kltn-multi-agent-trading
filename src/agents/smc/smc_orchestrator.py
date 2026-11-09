"""SMC Multi-Agent Orchestrator — Branch 2 (Opportunistic SMC).

Coordinates the Hybrid Multi-Agent trading workflow:
1. Macro News & Sentiment Agent -> checks macro regime & tier-1 news cooldown
2. SMC Strategy Synthesizer Agent -> invokes deterministic SMC tools (BOS, FVG, OB, Sizer) to produce SMCSetup
3. Adversarial Risk Auditor Agent -> adversarial red-team audit; VETO or execute order on MT5

Follows Google ADK hierarchical sub_agents pattern.
"""

import os

from google.adk.agents.llm_agent import Agent

from src.agents.smc.adversarial_risk_agent import create_adversarial_risk_agent
from src.agents.smc.macro_sentiment_agent import create_macro_sentiment_agent
from src.agents.smc.smc_strategy_agent import create_smc_strategy_agent

SMC_ORCHESTRATOR_INSTRUCTION = """
You are the SMC Multi-Agent Executive Orchestrator coordinating the quantitative trading workflow.

Workflow Execution Order:
Stage 1: Delegate to `macro_sentiment_agent` to assess global risk climate and tier-1 economic news events.
Stage 2: Delegate to `smc_strategy_agent` to invoke deterministic SMC tools and formulate a mathematically sound SMCSetup.
Stage 3: Delegate to `adversarial_risk_agent` to audit all risk gates, challenge the setup, and either VETO or dispatch the order to MT5.

Once all sub-agents finish their turns, synthesize a comprehensive executive summary detailing:
- The macro risk regime and news impact
- The technical SMC setup rationale (BOS/CHoCH, POI, Entry, SL, TP, R:R)
- The final Risk Verdict (Approved or Vetoed with reason)
"""


def create_smc_orchestrator(model_name: str | None = None) -> Agent:
    """Create the Root Executive Orchestrator for the SMC Multi-Agent strategy branch."""
    model = model_name or os.getenv("SMC_LLM_MODEL", "gemini-4-argon")

    macro_agent = create_macro_sentiment_agent(model_name=model)
    strategy_agent = create_smc_strategy_agent(model_name=model)
    risk_agent = create_adversarial_risk_agent(model_name=model)

    return Agent(
        name="smc_orchestrator",
        model=model,
        description="Coordinates the 3-stage Hybrid Multi-Agent SMC quantitative trading pipeline.",
        instruction=SMC_ORCHESTRATOR_INSTRUCTION,
        sub_agents=[
            macro_agent,
            strategy_agent,
            risk_agent,
        ],
    )
