"""Legacy Baseline SMC Multi-Agent Suite.

Preserved original pure-LLM multi-agent implementation for academic ablation
study and empirical comparison with the Hybrid Multi-Agent architecture.
"""

from src.agents.smc.legacy_baseline.htf_bias_agent import create_htf_bias_agent
from src.agents.smc.legacy_baseline.poi_agent import create_poi_agent
from src.agents.smc.legacy_baseline.sizer_agent import create_sizer_agent
from src.agents.smc.legacy_baseline.smc_orchestrator import create_smc_orchestrator
from src.agents.smc.legacy_baseline.structure_agent import create_structure_agent

__all__ = [
    "create_htf_bias_agent",
    "create_structure_agent",
    "create_poi_agent",
    "create_sizer_agent",
    "create_smc_orchestrator",
]
