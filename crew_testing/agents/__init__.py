"""
MT Testing Crew Agents

Meet the 8-agent crew for autonomous testing:
- 📚 Swagger: API Documentation Expert
- 🎯 Architect: Test Scenario Designer
- 🎨 Mocker: Test Data Craftsman
- ⚡ Flash: Test Executor
- 🔬 Inspector: Quality Analyst
- 📊 Herald: Test Reporter
- 🔧 Forge: Test Infrastructure Engineer
- 🐛 Sherlock: Test Debugger
"""

from crew_testing.agents.swagger import create_swagger_agent, create_swagger_scan_task

__all__ = [
    "create_swagger_agent",
    "create_swagger_scan_task",
]
