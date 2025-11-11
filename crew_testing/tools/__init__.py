"""
Tools for CrewAI Testing System

Available tools:
- OpenAPI tools: Read and analyze OpenAPI specifications
- API Client tools: Scan and generate API client methods
- Test Scanner tools: Analyze test coverage
- Schema tools: Query database schema and relationships (Phase 2)
- Code Generator tools: Generate Python test code (Phase 2)
- Pytest Runner tools: Execute tests and collect results (Phase 2)
- File Writer tools: Safely write generated code (Phase 2)
- Code Analysis tools: Parse Python code and analyze structure (Phase 3)
- Coverage Analysis tools: Read coverage reports and identify gaps (Phase 3)
- Gap Report tools: Generate prioritized test gap reports (Phase 3)
"""

# Phase 1 tools
from crew_testing.tools.openapi_tool import ReadOpenAPISpecTool, DetectGapsTool
from crew_testing.tools.api_client_tool import ScanAPIClientTool, GenerateClientMethodTool
# from crew_testing.tools.test_scanner_tool import ScanTestsTool, CalculateCoverageTool  # Not needed for Phase 2

# Phase 2 tools
from crew_testing.tools.query_schema_tool import QuerySchemaTool
from crew_testing.tools.code_generator_tool import CodeGeneratorTool
from crew_testing.tools.pytest_runner_tool import PytestRunnerTool
from crew_testing.tools.file_writer_tool import FileWriterTool, FileAppenderTool

# Phase 3 tools - Unit test generation
from crew_testing.tools.code_analyzer_tool import CodeAnalyzerTool
from crew_testing.tools.coverage_analyzer_tool import CoverageAnalyzerTool, CoverageRunnerTool
from crew_testing.tools.gap_report_tool import GapReportTool

__all__ = [
    # Phase 1
    "ReadOpenAPISpecTool",
    "DetectGapsTool",
    "ScanAPIClientTool",
    "GenerateClientMethodTool",
    # "ScanTestsTool",  # Not needed for Phase 2
    # "CalculateCoverageTool",  # Not needed for Phase 2
    # Phase 2
    "QuerySchemaTool",
    "CodeGeneratorTool",
    "PytestRunnerTool",
    "FileWriterTool",
    "FileAppenderTool",
    # Phase 3
    "CodeAnalyzerTool",
    "CoverageAnalyzerTool",
    "CoverageRunnerTool",
    "GapReportTool",
]
