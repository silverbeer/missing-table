"""
Configuration for CrewAI Testing System

This module handles configuration for the MT Testing Crew including:
- Multi-LLM provider support (Anthropic, OpenAI)
- Per-agent LLM selection and optimization
- API key management
- Backend URL configuration
- Logging settings

Supports mixing different LLM providers for cost and performance optimization.
"""

import os
from typing import Optional, Dict, Any, Literal
from enum import Enum

from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env.local (falls back to .env)
env_path = Path(__file__).parent.parent / "backend" / ".env.local"
load_dotenv(dotenv_path=env_path if env_path.exists() else None)


class LLMProvider(str, Enum):
    """Supported LLM providers"""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


class CrewConfig:
    """Configuration for CrewAI Testing System with Multi-LLM Support"""

    # ============================================================================
    # LLM Provider Configuration
    # ============================================================================

    # Default provider (can override per-agent)
    DEFAULT_PROVIDER: LLMProvider = LLMProvider(
        os.getenv("CREW_LLM_PROVIDER", "anthropic")
    )

    # Anthropic Configuration
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_DEFAULT_MODEL: str = "claude-3-haiku-20240307"  # $0.25/$1.25 per M tokens
    ANTHROPIC_SMART_MODEL: str = "claude-3-5-sonnet-20241022"  # $3/$15 per M tokens

    # OpenAI Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_DEFAULT_MODEL: str = "gpt-4o-mini"  # $0.15/$0.60 per M tokens
    OPENAI_SMART_MODEL: str = "gpt-4o"  # $2.50/$10 per M tokens

    # ============================================================================
    # Per-Agent LLM Strategy
    # ============================================================================
    # Optimize cost vs performance by assigning best LLM to each agent

    AGENT_LLM_CONFIG: Dict[str, Dict[str, Any]] = {
        # 📚 Swagger - API Documentation Expert
        # Simple cataloging task, use cheapest option
        "swagger": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "reasoning": "Simple API parsing, GPT-4o-mini is fast and cheap",
            "cost_per_run": 0.03,
        },

        # 🎯 Architect - Test Scenario Designer
        # Complex reasoning, worth using smarter model
        "architect": {
            "provider": "openai",
            "model": "gpt-4o",
            "reasoning": "Test design requires deep reasoning, GPT-4o excels",
            "cost_per_run": 0.20,
        },

        # 🎨 Mocker - Test Data Craftsman
        # Structured data generation, GPT-4o-mini is fine
        "mocker": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "reasoning": "Data generation is straightforward, GPT-4o-mini works well",
            "cost_per_run": 0.03,
        },

        # ⚡ Flash - Test Executor
        # Simple execution orchestration
        "flash": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "reasoning": "Test execution is procedural, GPT-4o-mini is sufficient",
            "cost_per_run": 0.03,
        },

        # 🔧 Forge - Test Infrastructure Engineer
        # Code generation - OpenAI typically better
        "forge": {
            "provider": "openai",
            "model": "gpt-4o",
            "reasoning": "Code generation, OpenAI often superior",
            "cost_per_run": 0.20,
        },

        # 🔬 Inspector - Quality Analyst
        # Pattern analysis, Haiku can handle
        "inspector": {
            "provider": "anthropic",
            "model": "claude-3-haiku-20240307",
            "reasoning": "Pattern analysis is systematic",
            "cost_per_run": 0.05,
        },

        # 📊 Herald - Test Reporter
        # Formatting and reporting, simple task
        "herald": {
            "provider": "anthropic",
            "model": "claude-3-haiku-20240307",
            "reasoning": "Report generation is straightforward",
            "cost_per_run": 0.05,
        },

        # 🐛 Sherlock - Test Debugger
        # Complex debugging, worth premium model
        "sherlock": {
            "provider": "openai",
            "model": "gpt-4o",
            "reasoning": "Debugging requires deep reasoning",
            "cost_per_run": 0.20,
        },
    }

    # ============================================================================
    # MT Backend Configuration
    # ============================================================================

    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")
    OPENAPI_ENDPOINT: str = f"{BACKEND_URL}/openapi.json"

    # ============================================================================
    # Paths
    # ============================================================================

    API_CLIENT_PATH: str = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "api_client"
    )
    TESTS_PATH: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tests")
    REPORTS_PATH: str = os.path.join(os.path.dirname(__file__), "reports")

    # ============================================================================
    # Agent Settings
    # ============================================================================

    VERBOSE: bool = os.getenv("CREW_VERBOSE", "false").lower() == "true"
    MAX_ITERATIONS: int = int(os.getenv("CREW_MAX_ITERATIONS", "5"))

    # ============================================================================
    # Logging
    # ============================================================================

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # ============================================================================
    # Validation & Helper Methods
    # ============================================================================

    @classmethod
    def validate(cls) -> None:
        """
        Validate required configuration

        At least one LLM provider must be configured.
        Warns about missing providers but doesn't fail.
        """
        has_anthropic = bool(cls.ANTHROPIC_API_KEY)
        has_openai = bool(cls.OPENAI_API_KEY)

        if not has_anthropic and not has_openai:
            raise ValueError(
                "No LLM provider configured! Set either:\n"
                "  - ANTHROPIC_API_KEY for Claude models\n"
                "  - OPENAI_API_KEY for GPT models\n"
                "  - Both for maximum flexibility"
            )

        # Warn about missing providers
        if not has_anthropic:
            print("⚠️  ANTHROPIC_API_KEY not set - Anthropic models unavailable")
        if not has_openai:
            print("ℹ️  OPENAI_API_KEY not set - OpenAI models unavailable")

        # Validate agent configs
        for agent_name, config in cls.AGENT_LLM_CONFIG.items():
            provider = config["provider"]
            if provider == "anthropic" and not has_anthropic:
                print(f"⚠️  Agent '{agent_name}' requires Anthropic but key not set")
            elif provider == "openai" and not has_openai:
                print(f"⚠️  Agent '{agent_name}' requires OpenAI but key not set")

    @classmethod
    def get_llm_for_agent(cls, agent_name: str):
        """
        Get the appropriate LLM instance for a specific agent

        Args:
            agent_name: Name of the agent (e.g., "swagger", "architect")

        Returns:
            Configured LLM instance (ChatAnthropic or ChatOpenAI)

        Raises:
            ValueError: If agent not found or provider not configured
        """
        from langchain_anthropic import ChatAnthropic
        from langchain_openai import ChatOpenAI

        agent_name_lower = agent_name.lower()

        # Get agent config
        config = cls.AGENT_LLM_CONFIG.get(agent_name_lower)
        if not config:
            # Default to Anthropic Haiku
            print(f"⚠️  No config for agent '{agent_name}', using default (Anthropic Haiku)")
            config = {
                "provider": "anthropic",
                "model": cls.ANTHROPIC_DEFAULT_MODEL,
            }

        provider = config["provider"]
        model = config["model"]

        # Create LLM instance based on provider
        if provider == "anthropic":
            if not cls.ANTHROPIC_API_KEY:
                raise ValueError(
                    f"Agent '{agent_name}' requires Anthropic but ANTHROPIC_API_KEY not set"
                )

            return ChatAnthropic(
                model=model,
                anthropic_api_key=cls.ANTHROPIC_API_KEY,
                temperature=0.1,  # Low temperature for consistent results
                max_tokens=4096,
            )

        elif provider == "openai":
            if not cls.OPENAI_API_KEY:
                raise ValueError(
                    f"Agent '{agent_name}' requires OpenAI but OPENAI_API_KEY not set"
                )

            return ChatOpenAI(
                model=model,
                openai_api_key=cls.OPENAI_API_KEY,
                temperature=0.1,  # Low temperature for consistent results
                max_tokens=4096,
            )

        else:
            raise ValueError(f"Unknown provider: {provider}")

    @classmethod
    def get_agent_info(cls, agent_name: str) -> Dict[str, Any]:
        """
        Get configuration info for an agent

        Args:
            agent_name: Name of the agent

        Returns:
            Dictionary with provider, model, cost, and reasoning
        """
        config = cls.AGENT_LLM_CONFIG.get(agent_name.lower(), {})
        return {
            "agent": agent_name,
            "provider": config.get("provider", "unknown"),
            "model": config.get("model", "unknown"),
            "cost_per_run": config.get("cost_per_run", 0.0),
            "reasoning": config.get("reasoning", "No reasoning provided"),
        }

    @classmethod
    def get_total_cost_estimate(cls) -> float:
        """
        Calculate estimated cost per full crew run

        Returns:
            Estimated cost in USD
        """
        return sum(
            config.get("cost_per_run", 0.0)
            for config in cls.AGENT_LLM_CONFIG.values()
        )

    @classmethod
    def print_llm_config(cls) -> None:
        """Print current LLM configuration for all agents"""
        print("\n🤖 MT Testing Crew - LLM Configuration")
        print("=" * 70)
        print(f"\nDefault Provider: {cls.DEFAULT_PROVIDER.value}")
        print(f"\nProviders Available:")
        print(f"  Anthropic: {'✅ Configured' if cls.ANTHROPIC_API_KEY else '❌ Not configured'}")
        print(f"  OpenAI:    {'✅ Configured' if cls.OPENAI_API_KEY else '❌ Not configured'}")
        print(f"\nPer-Agent Configuration:")
        print("-" * 70)

        for agent_name in ["swagger", "architect", "mocker", "flash", "forge", "inspector", "herald", "sherlock"]:
            info = cls.get_agent_info(agent_name)
            emoji_map = {
                "swagger": "📚",
                "architect": "🎯",
                "mocker": "🎨",
                "flash": "⚡",
                "forge": "🔧",
                "inspector": "🔬",
                "herald": "📊",
                "sherlock": "🐛",
            }
            emoji = emoji_map.get(agent_name, "🤖")

            print(f"\n{emoji} {agent_name.capitalize()}")
            print(f"   Provider: {info['provider']}")
            print(f"   Model: {info['model']}")
            print(f"   Cost/run: ${info['cost_per_run']:.2f}")
            print(f"   Why: {info['reasoning']}")

        print(f"\n{'=' * 70}")
        print(f"Estimated Total Cost per Full Run: ${cls.get_total_cost_estimate():.2f}")
        print()


# Validate configuration on import
try:
    CrewConfig.validate()
except ValueError as e:
    print(f"❌ Configuration Error: {e}")
    print("ℹ️  Set API keys in .env.local to use CrewAI testing")
