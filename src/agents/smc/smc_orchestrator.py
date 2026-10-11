"""SMC Sub-Orchestrator — Branch 2 (Opportunistic SMC).

Chains the 5 sequential SMC trading stages:
1. HTF Bias Analyzer -> state['htf_bias']
2. Market Structure Agent -> state['market_structure']
3. POI & Liquidity Detector -> state['poi_zone']
4. Position Sizer Agent -> state['smc_setup']
5. Risk Gatekeeper Agent -> state['risk_verdict'] -> MT5 execution if approved

Follows Google ADK hierarchical sub_agents pattern.
"""

import os

from google.adk.agents.llm_agent import Agent

from src.agents.shared.risk_gatekeeper import create_risk_gatekeeper
from src.agents.smc.htf_bias_agent import create_htf_bias_agent
from src.agents.smc.poi_agent import create_poi_agent
from src.agents.smc.sizer_agent import create_sizer_agent
from src.agents.smc.structure_agent import create_structure_agent

SMC_ORCHESTRATOR_INSTRUCTION = """
You are the SMC Pipeline Orchestrator coordinating the complete Smart Money Concepts trading workflow for the requested symbol.

Mandatory 5-Step Sequential Pipeline:
Step 1: Delegate to `htf_bias_agent` to determine macro H4/D1 bias (BULLISH/BEARISH/RANGING).
Step 2: Delegate to `structure_agent` to inspect M15 micro structure and identify BOS or CHoCH.
Step 3: Delegate to `poi_agent` to locate high-probability Order Blocks (OB), FVGs, and Liquidity Sweeps.
Step 4: Delegate to `sizer_agent` to calculate Entry, Stop Loss, Take Profit, R:R ratio, and 1R position sizing.
Step 5: Delegate to `risk_gatekeeper` to independently audit all VETO risk gates and execute orders on MT5 if approved.

Summarize the final status and decisions of the complete pipeline once all 5 stages conclude.
"""


def create_smc_orchestrator(model_name: str | None = None) -> Agent:
    """Create the Root Sub-Orchestrator for the SMC strategy branch."""
    model = model_name or os.getenv("SMC_LLM_MODEL", "gemini-2.5-flash")

    htf_agent = create_htf_bias_agent(model_name=model)
    struct_agent = create_structure_agent(model_name=model)
    poi_agent = create_poi_agent(model_name=model)
    sizer_agent = create_sizer_agent(model_name=model)
    gatekeeper = create_risk_gatekeeper(model_name=model)

    return Agent(
        name="smc_orchestrator",
        model=model,
        description="Coordinates the 5-step automated Smart Money Concepts trading pipeline.",
        instruction=SMC_ORCHESTRATOR_INSTRUCTION,
        sub_agents=[
            htf_agent,
            struct_agent,
            poi_agent,
            sizer_agent,
            gatekeeper,
        ],
    )
