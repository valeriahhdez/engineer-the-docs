"""
Configuration loading for Zensical agentic documentation system.

This module provides production-ready configuration management for the three-agent
pipeline (consistency checker, alt text generator, SEO optimizer). It enforces
fail-fast semantics with clear error messages and strict validation.

Functions:
    load_config: Load and validate agents.yaml configuration
    load_glossary: Load and validate glossary YAML file

Design principles:
    - Single source of truth: agents.yaml points to all config files
    - Fail fast: validation errors raise immediately with clear messages
    - Opt-in discovery: only files explicitly listed are processed
    - No mocking: pure file I/O (testable in isolation)
"""

import os
from pathlib import Path
from typing import Any, Dict

import yaml


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load and validate agents.yaml configuration file.

    This function reads the agent discovery configuration, validates YAML syntax,
    and enforces structural requirements for all three agents. It serves as the
    single source of truth for agent discovery and agent-specific settings.

    Expected structure:
    {
        "agents": {
            "consistency_checker": {
                "enabled": bool,
                "description": str,
                "sources": ["docs/**/*.md", "!docs/generated/**/*.md"],  # ← Two-pass glob
                "config": {
                    "glossary_path": "reference/glossary.yaml",
                    "exclude_markers": ["# --no-consistency-check"]     # ← List of markers
                }
            },
            "alt_text_generator": { ... },
            "seo_optimizer": { ... }
        },
        "output": {                                                      # ← Optional
            "artifact_name": str,
            "format": str,
            ...
        }
    }

    Args:
        config_path: Path to agents.yaml (relative or absolute)

    Returns:
        Validated configuration dictionary.

    Raises:
        FileNotFoundError: If config_path does not exist
        ValueError: If YAML is malformed or structure is invalid

    Example:
        >>> config = load_config("agents.yaml")
        >>> glossary_path = config["agents"]["consistency_checker"]["config"]["glossary_path"]
    """
    # Validate file existence
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Config file not found: {config_path}\n"
            f"Expected at: {os.path.abspath(config_path)}"
        )

    # Load YAML
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(
            f"Invalid YAML syntax in {config_path}:\n{str(e)}"
        ) from e
    except Exception as e:
        raise ValueError(
            f"Failed to read {config_path}: {str(e)}"
        ) from e

    # Validate structure: agents key exists
    if not isinstance(config, dict) or "agents" not in config:
        raise ValueError(
            f"Invalid config structure in {config_path}: "
            "expected top-level 'agents' key (dict)"
        )

    agents = config["agents"]
    if not isinstance(agents, dict):
        raise ValueError(
            f"Invalid config structure in {config_path}: "
            "'agents' must be a dict, got {type(agents).__name__}"
        )

    # Validate consistency_checker structure
    if "consistency_checker" not in agents:
        raise ValueError(
            f"Missing required agent 'consistency_checker' in {config_path}"
        )

    cc_config = agents["consistency_checker"]
    if not isinstance(cc_config, dict):
        raise ValueError(
            f"Invalid structure: agents.consistency_checker must be a dict, "
            f"got {type(cc_config).__name__}"
        )

    if "config" not in cc_config:
        raise ValueError(
            f"Missing 'config' key in agents.consistency_checker in {config_path}"
        )

    cc_inner = cc_config["config"]
    if not isinstance(cc_inner, dict):
        raise ValueError(
            f"Invalid structure: agents.consistency_checker.config must be a dict, "
            f"got {type(cc_inner).__name__}"
        )

    if "glossary_path" not in cc_inner:
        raise ValueError(
            f"Missing 'glossary_path' in agents.consistency_checker.config "
            f"in {config_path}"
        )

    glossary_path = cc_inner["glossary_path"]
    if not isinstance(glossary_path, str):
        raise ValueError(
            f"Invalid value: glossary_path must be a string, "
            f"got {type(glossary_path).__name__}"
        )

    if not glossary_path.strip():
        raise ValueError(
            f"Invalid value: glossary_path cannot be empty in {config_path}"
        )

    # Validate agent-specific fields (optional but good for portfolio)
    for agent_name, agent_config in config["agents"].items():
        if agent_config.get("enabled", False):
            # Validate sources (must be a list)
            if "sources" in agent_config:
                if not isinstance(agent_config["sources"], list):
                    raise ValueError(
                        f"agents.{agent_name}.sources must be a list, "
                        f"got {type(agent_config['sources']).__name__}"
                    )
            
            # Validate config.exclude_markers (must be a list of strings)
            if "config" in agent_config:
                if "exclude_markers" in agent_config["config"]:
                    markers = agent_config["config"]["exclude_markers"]
                    if not isinstance(markers, list):
                        raise ValueError(
                            f"agents.{agent_name}.config.exclude_markers must be a list"
                        )
                    for marker in markers:
                        if not isinstance(marker, str):
                            raise ValueError(
                                f"agents.{agent_name}.config.exclude_markers: "
                                f"all markers must be strings, got {type(marker).__name__}"
                            )

    return config


def load_glossary(glossary_path: str) -> Dict[str, str]:
    """
    Load and validate glossary YAML file.

    This function reads the canonical terminology glossary for the consistency
    checker agent. It enforces strict validation: all keys and values must be
    strings, the glossary must not be empty, and at least 3 terms must be defined.

    Args:
        glossary_path: Path to glossary YAML file (relative or absolute)

    Returns:
        Validated glossary dictionary with structure:
            {
                "term_name": "Term definition",
                ...
            }

    Raises:
        FileNotFoundError: If glossary_path does not exist
        ValueError: If YAML is malformed, content is invalid, or too few terms exist

    Example:
        >>> glossary = load_glossary("reference/glossary.yaml")
        >>> term_def = glossary.get("documentation")
    """
    # Validate file existence
    if not os.path.exists(glossary_path):
        raise FileNotFoundError(
            f"Glossary file not found: {glossary_path}\n"
            f"Expected at: {os.path.abspath(glossary_path)}"
        )

    # Load YAML
    try:
        with open(glossary_path, "r", encoding="utf-8") as f:
            glossary = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(
            f"Invalid YAML syntax in {glossary_path}:\n{str(e)}"
        ) from e
    except Exception as e:
        raise ValueError(
            f"Failed to read {glossary_path}: {str(e)}"
        ) from e

    # Validate structure: glossary must be a dict
    if not isinstance(glossary, dict):
        raise ValueError(
            f"Invalid glossary structure in {glossary_path}: "
            f"expected dict, got {type(glossary).__name__}"
        )

    # Validate: not empty
    if not glossary:
        raise ValueError(
            f"Empty glossary in {glossary_path}: at least 1 term required"
        )

    # Validate: at least 3 terms
    if len(glossary) < 3:
        raise ValueError(
            f"Insufficient glossary terms in {glossary_path}: "
            f"found {len(glossary)}, need ≥3"
        )

    # Validate: all keys and values are strings
    for key, value in glossary.items():
        if not isinstance(key, str):
            raise ValueError(
                f"Invalid key type in {glossary_path}: "
                f"all keys must be strings, got {type(key).__name__}"
            )
        if not isinstance(value, str):
            raise ValueError(
                f"Invalid value type in {glossary_path}: "
                f"term '{key}' value must be string, got {type(value).__name__}"
            )

    return glossary