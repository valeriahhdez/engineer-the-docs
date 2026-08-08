"""
Engineer the docs agentic documentation system.

This package implements the post-build QA pipeline with three specialized agents:
1. Consistency checker: validates terminology against canonical glossary
2. Alt text generator: creates descriptions for images
3. SEO optimizer: validates heading hierarchy and clarity

All agents use production-ready config loading from agents.config.
"""

__version__ = "0.1.0"