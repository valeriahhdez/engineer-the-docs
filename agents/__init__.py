"""
Engineer the docs agentic documentation system.

This package implements the post-build QA pipeline with three specialized agents:
1. Consistency checker: validates terminology against canonical glossary
2. Alt text generator: creates descriptions for images
3. SEO optimizer: validates heading hierarchy and clarity

PHASE ROADMAP:
  Phase 1: Document scanning (glob + markers) - COMPLETE ✓
  Phase 2: Term candidate detection (Python regex) - IN PROGRESS
  Phase 3: LLM verification (Groq semantic validation) - PLANNED
  Phase 4: Result formatting - PLANNED

All agents use production-ready config loading from agents.config.
"""

from agents.config import load_config, load_glossary
from agents.documents import (
    DocumentInput,
    Candidate,
    ConsistencyIssue,
    ConsistencyReport,
)
from agents.scan import scan_docs

__version__ = "0.1.0"

__all__ = [
    "load_config",
    "load_glossary",
    "DocumentInput",
    "Candidate",
    "ConsistencyIssue",
    "ConsistencyReport",
    "scan_docs",
]
