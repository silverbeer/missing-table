"""
MT Testing Crew Workflows

Orchestrated multi-agent workflows:
- Phase 1: API Gap Detection (Swagger only)
- Phase 2: Test Generation (Architect → Mocker → Forge → Flash)
- Phase 3: Full Quality Pipeline (all 8 agents)
"""

from crew_testing.workflows.phase2_workflow import run_phase2_workflow

__all__ = ["run_phase2_workflow"]
