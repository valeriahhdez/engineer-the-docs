"""
Phase 3 (Alt text): Groq vision verification, one call per image.

Sends each "generate"-classified image (bytes + heading breadcrumb +
section-bounded context) to Groq's vision model (qwen/qwen3.6-27b —
Groq's only vision-capable model, per ALT_TEXT_ARCHITECTURE.md, one call
per image rather than batching to avoid cross-talk between images in one
prompt). On vision failure (API error, timeout, unsupported format,
model unavailable), falls back to context-only generation via a text
model (openai/gpt-oss-120b, already used by the other two agents) — same
prompt inputs minus the image. If even that fails (e.g. no GROQ_API_KEY
at all), degrades one step further to a deterministic, non-LLM string
built from the breadcrumb and filename, still tagged source
'context_fallback' — it's the same fallback path internally exhausting
its own options, not a third source type (ALT_TEXT_ARCHITECTURE.md
specifies exactly two: 'vision' / 'context_fallback').

get_groq_client() is imported from agents.groq_verifier rather than
reimplemented here, same as agents/seo_verifier.py.
"""

import base64
import json
import mimetypes
import sys
from pathlib import Path
from typing import Tuple

from pydantic import BaseModel, Field, ValidationError

from agents.documents import AltTextCandidate, AltTextIssue
from agents.groq_verifier import get_groq_client

VISION_MODEL = "qwen/qwen3.6-27b"
FALLBACK_TEXT_MODEL = "openai/gpt-oss-120b"

# Raster formats Groq's vision API accepts. SVGs (decorative icons, which
# are normally skipped as "decorative" before reaching this phase) aren't
# well-supported by vision LLMs, so a genuinely content-bearing SVG goes
# straight to context-only generation instead of attempting a vision call
# likely to fail.
_SUPPORTED_VISION_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


# ============================================================================
# Prompts
# ============================================================================

VISION_SYSTEM_PROMPT = """You are a technical documentation accessibility auditor, specialized in WCAG 2.1 Criterion 1.1.1 (Non-Text Content).

  

Your job: write concise, accurate alt text for an image within a technical documentation page. The alt text should be WCAG 1.1.1-compliant and grounded in

the visual content of the image and surrounding context.
 

Rules:

- Focus on function and meaning: Describe the visual information, structural relationships (e.g., nested components, directional arrows, UI states), or text contained in the image.
- Forbidden prefixes: Never start with "Image of", "Screenshot of", "Diagram showing", or similar metadata phrases. Start directly with the description.
- Context grounding: Use the heading breadcrumb and surrounding prose for topical framing
(what the reader is trying to learn), not as a substitute for looking
at the image itself.
- Be accurate: Do not invent details that aren't visible in the image.
- Report confidence: 'low' if the image is blurry, ambiguous, generic, or contains illegible text; 'high' otherwise.
- Reasoning: Name the specific visual detail that led to this description
and confidence level. Do not restate suggested_alt in different words —
that's not reasoning, it's a paraphrase.
- Length and content: Length scales with what the image actually contains, not a fixed count.
Name the components you can identify and describe the relationships you can trace trace without hesitation. If a specific relationship is ambiguous, omit it rather than guess.
Prioritize naming components and relationships over describing visual styling (colors, line weights, shapes) unless the styling itself carries meaning (for example, a status color-code).
A listener should be able to form an accurate mental picture of what this image conveys in this context from your description alone.
Output strictly valid JSON. No preamble, no markdown, no code blocks.

"""

CONTEXT_ONLY_SYSTEM_PROMPT = """You are a technical documentation accessibility auditor, specialized in WCAG 2.1 Criterion 1.1.1 (Non-Text Content).

You are operating in **CONTEXT-ONLY FALLBACK MODE** because the primary vision provider is currently unavailable. You do NOT have access to the image file itself.

- Your objective: Infer a high-level, WCAG-compliant alt text description using ONLY the image filename, heading breadcrumb, and the surrounding prose. 

Rules:
- Focus on function, not visuals: Describe the conceptual purpose of the image within the section. Do NOT guess colors, visual layouts, component counts, or specific UI elements you cannot see.
- Conservative language: Use structural, purpose-driven phrases. For example, use "database replication with a primary node and two replica nodes" rather than "conceptual diagram of database replication." 
- Forbidden prefixes: Do NOT start with "Image of", "Screenshot of", or "Photo of".
- Forbidden speculation: Do NOT invent labels, arrows, or step-by-step flows that are not explicitly stated in the surrounding prose.
- Report confidence: 'high' only if the surrounding prose explicitly and specifically describes the image's visual content (names labeled elements, layout, or a specific sequence).
'low' if you are inferring the image's likely content from general topical context without an explicit description.
- Reasoning: name the specific surrounding text that led to this description and confidence level. Do not restate suggested_alt in different words, that's not reasoning, it's a paraphrase.
- Length and content: Length and content are bounded by what the surrounding text explicitly supports, not by how visually complex the image might be, which you cannot assess. 
Default to one sentence describing the image's conceptual purpose within this section. Extend to two sentences only if the text explicitly names multiple distinct elements the image depicts.
In that case, name only the elements the text actually states, and do not describe how they relate to each other unless the text explicitly says so too. If the text implies structure, layout, or relationships it doesn't spell out, do not infer them.
Fall back to describing the image's general purpose rather than a specific structure you can't verify. An accurate but shallow description is always preferable to a detailed but speculative one.

Output ONLY valid JSON. No preamble, no markdown, no code blocks.
"""

RESPONSE_FORMAT_INSTRUCTIONS = """Also report:
- confidence: "high" if the description is well-grounded (vision: clearly
  visible in the image; context-only: strongly implied by the surrounding
  text), "low" if you're inferring or guessing.
- reasoning: one brief sentence explaining why you chose this description
  and confidence level.
"""

# Structured Outputs: constrains the model's JSON at generation time rather
# than hoping it follows a free-text example (RESPONSE_FORMAT_INSTRUCTIONS
# above now only has to explain what the fields MEAN, not their shape).
# Verified against both models: openai/gpt-oss-120b accepts it immediately;
# qwen/qwen3.6-27b also accepts it, but — like plain-text mode — needs
# max_tokens high enough to cover its hidden reasoning trace first, or the
# request fails validation with an empty response.
RESPONSE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "alt_text_response",
        "schema": {
            "type": "object",
            "properties": {
                "suggested_alt": {
                    "type": "string",
                    "description": "Concise alt text for this image",
                },
                "confidence": {
                    "type": "string",
                    "enum": ["high", "low"],
                    "description": "One sentence citing the specific evidence — visual or textual — behind suggested_alt and confidence. Not a restatement of suggested_alt.",
                },
                "reasoning": {
                    "type": "string",
                    "description": "Brief 1-sentence explanation of the description and confidence level",
                },
            },
            "required": ["suggested_alt", "confidence", "reasoning"],
        },
    },
}


class GroqAltTextResponse(BaseModel):
    """Single alt-text suggestion from Groq."""

    suggested_alt: str = Field(..., description="Generated alt text")
    confidence: str = Field(..., description="'high' or 'low'")
    reasoning: str = Field(..., description="Brief explanation of the description and confidence level")

    class Config:
        strict = True


# ============================================================================
# Helpers
# ============================================================================


def _encode_image(path: Path) -> Tuple[str, str]:
    """Read an image file and return (base64_data, mime_type)."""
    mime_type, _ = mimetypes.guess_type(str(path))
    if mime_type is None:
        mime_type = "image/png"
    return base64.b64encode(path.read_bytes()).decode("ascii"), mime_type


def _build_user_prompt(candidate: AltTextCandidate) -> str:
    return f"""Image filename: {Path(candidate.image_path).name}
Heading breadcrumb: {candidate.heading_breadcrumb or "(none - image appears before any heading)"}
Surrounding text:
{candidate.context_text or "(no surrounding text found)"}

{RESPONSE_FORMAT_INSTRUCTIONS}"""


def _heuristic_alt_text(candidate: AltTextCandidate) -> str:
    """
    Last-resort, no-LLM alt text: humanize the filename, framed by the
    nearest heading topic. Used only if both the vision call and the
    context-only fallback call fail (e.g. no GROQ_API_KEY at all).
    """
    stem = Path(candidate.image_path).stem
    humanized = stem.replace("-", " ").replace("_", " ").strip().capitalize()
    if candidate.heading_breadcrumb:
        topic = candidate.heading_breadcrumb.split(" > ")[-1]
        return f"{humanized} ({topic})"
    return humanized


# ============================================================================
# Groq API Integration
# ============================================================================


def generate_alt_text(candidate: AltTextCandidate) -> AltTextIssue:
    """
    Generate alt text for one image: try Groq vision first, fall back to
    context-only generation on any failure.

    Args:
        candidate: AltTextCandidate from Phase 2 (agents/alt_text_finder.py)

    Returns:
        AltTextIssue with source 'vision' or 'context_fallback'
    """
    extension = Path(candidate.image_abs_path).suffix.lower()
    if extension not in _SUPPORTED_VISION_EXTENSIONS:
        print(
            f"[alt-text-phase-3] {candidate.file_path}:{candidate.line_number} "
            f"'{extension}' isn't a supported vision format — using context-only generation"
        )
        return _generate_context_fallback(
            candidate, f"Unsupported image format for vision: {extension}"
        )

    print(
        f"[alt-text-phase-3] Verifying {candidate.file_path}:{candidate.line_number} "
        f"({candidate.image_path}) with Groq vision..."
    )

    try:
        client = get_groq_client()
        image_b64, mime_type = _encode_image(Path(candidate.image_abs_path))
        user_prompt = _build_user_prompt(candidate)

        print(f"[alt-text-phase-3]   Calling {VISION_MODEL}...")
        response = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {"role": "system", "content": VISION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{image_b64}"},
                        },
                    ],
                },
            ],
            temperature=0,
            # qwen/qwen3.6-27b is a reasoning model: it spends tokens on a
            # <think> trace before the answer even when told to output only
            # JSON. reasoning_format="hidden" keeps that trace out of
            # `content`; max_tokens has to cover the hidden reasoning AND
            # the visible answer, or content comes back empty.
            max_tokens=1500,
            reasoning_format="hidden",
            response_format=RESPONSE_SCHEMA,
        )

        response_text = response.choices[0].message.content.strip()
        print(f"[alt-text-phase-3]   ✓ Response received")

        parsed = GroqAltTextResponse(**json.loads(response_text))
        return AltTextIssue(
            file_path=candidate.file_path,
            image_path=candidate.image_path,
            line_number=candidate.line_number,
            heading_breadcrumb=candidate.heading_breadcrumb,
            suggested_alt=parsed.suggested_alt,
            confidence=parsed.confidence,
            reasoning=parsed.reasoning,
            source="vision",
        )

    except json.JSONDecodeError as e:
        print(f"[alt-text-phase-3] ✗ Failed to parse Groq JSON response: {e}", file=sys.stderr)
        return _generate_context_fallback(candidate, "Vision response malformed")
    except ValidationError as e:
        print(f"[alt-text-phase-3] ✗ Groq response validation failed: {e}", file=sys.stderr)
        return _generate_context_fallback(candidate, "Vision response invalid")
    except ValueError as e:
        # Missing API key
        print(f"[alt-text-phase-3] ✗ {e}", file=sys.stderr)
        return _generate_context_fallback(candidate, str(e))
    except ImportError as e:
        # groq library not installed
        print(f"[alt-text-phase-3] ✗ {e}", file=sys.stderr)
        return _generate_context_fallback(candidate, str(e))
    except Exception as e:
        # Other API errors (timeout, rate limit, model unavailable, etc.)
        print(f"[alt-text-phase-3] ✗ Groq vision API error: {e}", file=sys.stderr)
        return _generate_context_fallback(candidate, f"Groq vision error: {type(e).__name__}")


def _generate_context_fallback(candidate: AltTextCandidate, reason: str) -> AltTextIssue:
    """
    Context-only generation: same breadcrumb + prose, no image bytes,
    using FALLBACK_TEXT_MODEL rather than retrying VISION_MODEL without
    an image — if the vision model itself is unavailable or deprecated,
    retrying it wouldn't help.

    Any failure here (including the same missing-API-key error the
    vision call already hit) degrades to a deterministic heuristic
    string rather than raising, so one bad image never crashes the run.
    """
    print(f"[alt-text-phase-3]   Falling back to context-only generation ({reason})")

    try:
        client = get_groq_client()
        user_prompt = _build_user_prompt(candidate)

        print(f"[alt-text-phase-3]   Calling {FALLBACK_TEXT_MODEL} (context-only)...")
        response = client.chat.completions.create(
            model=FALLBACK_TEXT_MODEL,
            messages=[
                {"role": "system", "content": CONTEXT_ONLY_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            max_tokens=300,
            response_format=RESPONSE_SCHEMA,
        )
        response_text = response.choices[0].message.content.strip()
        parsed = GroqAltTextResponse(**json.loads(response_text))
        suggested_alt = parsed.suggested_alt
        confidence = parsed.confidence
        reasoning = parsed.reasoning
        print(f"[alt-text-phase-3]   ✓ Context-only response received")

    except Exception as e:
        print(
            f"[alt-text-phase-3]   ✗ Context-only generation also failed "
            f"({type(e).__name__}); using a heuristic placeholder",
            file=sys.stderr,
        )
        suggested_alt = _heuristic_alt_text(candidate)
        confidence = "low"
        reasoning = f"No LLM available (context-only generation failed: {type(e).__name__}); alt text derived from filename and heading only."

    return AltTextIssue(
        file_path=candidate.file_path,
        image_path=candidate.image_path,
        line_number=candidate.line_number,
        heading_breadcrumb=candidate.heading_breadcrumb,
        suggested_alt=suggested_alt,
        confidence=confidence,
        reasoning=reasoning,
        source="context_fallback",
    )
