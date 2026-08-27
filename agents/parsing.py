"""
Heading extraction utility, shared across agents that need markdown
structure: the SEO optimizer (hierarchy) and the alt text generator
(section-bounded context, breadcrumbs).

Parses ATX-style Markdown headings (`#` through `######`) with hierarchy
context (parent heading tracking) and skips headings that appear inside
fenced code blocks. Setext-style headings (underlined with `===`/`---`)
are not detected — this project's docs use ATX headings exclusively.
"""

import re
from typing import List

from agents.documents import HeadingNode

_ATX_HEADING = re.compile(r'^(#{1,6})\s+(.+?)\s*#*\s*$')


def is_in_code_block(lines: List[str], line_number: int) -> bool:
    """
    Check if a line is inside a multiline code block (``` ... ```).

    Public (not agent-specific): used by parse_headings_from_markdown here
    and by agents/alt_text_finder.py to skip image references inside code
    fences, so image detection doesn't reimplement fence-counting.

    Args:
        lines: Full list of lines from document (0-indexed)
        line_number: 1-indexed line number to check

    Returns:
        True if line is inside a code block, False otherwise
    """
    line_idx = line_number - 1
    fence_count = sum(lines[i].count("```") for i in range(line_idx))
    return fence_count % 2 == 1


def parse_headings_from_markdown(content: str) -> List[HeadingNode]:
    """
    Extract all ATX headings from markdown with hierarchy context.

    Args:
        content: Full markdown file content

    Returns:
        HeadingNode list in document order. Each node's parent_heading is
        the text of the nearest preceding heading with a lower level
        (None for H1s, or any heading with no enclosing heading).

    Example:
        # Installation
        ## Prerequisites
        ### Docker Setup

        Returns:
        [
          HeadingNode(level=1, text="Installation", line_number=1, parent_heading=None),
          HeadingNode(level=2, text="Prerequisites", line_number=2, parent_heading="Installation"),
          HeadingNode(level=3, text="Docker Setup", line_number=3, parent_heading="Prerequisites"),
        ]
    """
    lines = content.split("\n")
    headings: List[HeadingNode] = []
    ancestor_stack: List[HeadingNode] = []

    for line_idx, line in enumerate(lines):
        line_number = line_idx + 1

        if is_in_code_block(lines, line_number):
            continue

        match = _ATX_HEADING.match(line)
        if not match:
            continue

        level = len(match.group(1))
        text = match.group(2).strip()

        # Pop ancestors at the same level or deeper; the remaining stack is
        # the full ancestor chain (outermost first), top-of-stack is the
        # nearest enclosing heading with a lower level.
        while ancestor_stack and ancestor_stack[-1].level >= level:
            ancestor_stack.pop()

        ancestors = [h.text for h in ancestor_stack]
        parent_heading = ancestors[-1] if ancestors else None

        node = HeadingNode(
            level=level,
            text=text,
            line_number=line_number,
            parent_heading=parent_heading,
            ancestors=ancestors,
        )
        headings.append(node)
        ancestor_stack.append(node)

    return headings
