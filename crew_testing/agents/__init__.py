"""
MT Testing Crew Agents

Phase 2 Agents (Test Generation):
- 🎯 Architect: Test Scenario Designer
- 🎨 Mocker: Test Data Craftsman
- 🔧 Forge: Test Code Generator
- ⚡ Flash: Test Executor
- 🔨 Mechanic: Test Fixer (NEW)
"""

from crew_testing.agents.swagger import create_swagger_agent, create_swagger_scan_task
from crew_testing.agents.architect import create_architect_agent, get_architect_task_description
from crew_testing.agents.mocker import create_mocker_agent, get_mocker_task_description
from crew_testing.agents.forge import create_forge_agent, get_forge_task_description
from crew_testing.agents.flash import create_flash_agent, get_flash_task_description
from crew_testing.agents.mechanic import create_mechanic_agent, get_mechanic_task_description

__all__ = [
    # Phase 1
    "create_swagger_agent",
    "create_swagger_scan_task",
    # Phase 2
    "create_architect_agent",
    "get_architect_task_description",
    "create_mocker_agent",
    "get_mocker_task_description",
    "create_forge_agent",
    "get_forge_task_description",
    "create_flash_agent",
    "get_flash_task_description",
    "create_mechanic_agent",
    "get_mechanic_task_description",
]
