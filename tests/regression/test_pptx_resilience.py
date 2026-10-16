"""PPTX builder resilience under adversarial outline content."""
from __future__ import annotations

import pytest

from backend.app.services.multimodal.pptx_builder import (
    PPTXBuilder,
    PPTXOutline,
    SlideContent,
)
from tests.regression.bad_inputs import (
    EMPTY_INPUTS,
    PROMPT_INJECTION_INPUTS,
    UNICODE_INPUTS,
)


@pytest.fixture(scope="module")
def builder() -> PPTXBuilder:
    return PPTXBuilder()


# Combine a representative subset of bad inputs that make sense for PPTX text.
PPTX_TEXT_INPUTS = EMPTY_INPUTS + UNICODE_INPUTS + PROMPT_INJECTION_INPUTS


@pytest.mark.parametrize("label,text", PPTX_TEXT_INPUTS)
def test_bad_title_does_not_crash_build(builder, label, text):
    """An adversarial title should either build a fallback deck or raise a
    *typed* validation error -- never an uncaught internal exception."""
    outline = PPTXOutline(
        title=text or "fallback",
        slides=[SlideContent(title="ok", bullets=["safe"])],
    )
    try:
        result = builder.build(outline, f"badtitle-{label[:20]}")
        assert isinstance(result, dict)
        assert "filepath" in result
    except (ValueError, TypeError):
        # Typed validation error is acceptable; uncaught Exception is not.
        pass


@pytest.mark.parametrize("label,text", PPTX_TEXT_INPUTS)
def test_bad_bullet_does_not_crash_build(builder, label, text):
    outline = PPTXOutline(
        title="safe title",
        slides=[SlideContent(title="ok", bullets=[text or "fallback"])],
    )
    try:
        result = builder.build(outline, f"badbullet-{label[:20]}")
        assert isinstance(result, dict)
    except (ValueError, TypeError):
        pass


def test_huge_outline_does_not_crash(builder):
    """Outline with many slides must not blow up the builder.

    The builder is allowed to cap the slide count (it has a safety limit
    around 50). We just need a structured result with >=1 slide."""
    # 50 content slides + cover + agenda = 52 -- below the builder's 60 cap.
    big = PPTXOutline(
        title="huge",
        slides=[SlideContent(title=f"slide {i}", bullets=[f"b{i}"]) for i in range(50)],
    )
    result = builder.build(big, "huge-outline")
    assert isinstance(result, dict)
    assert result.get("slides_count", 0) >= 1


def test_empty_slides_list_handled(builder):
    """A deck with no content slides should still produce a valid file
    (cover + agenda at minimum)."""
    outline = PPTXOutline(title="empty deck", slides=[])
    try:
        result = builder.build(outline, "empty-slides")
        assert isinstance(result, dict)
    except (ValueError, TypeError):
        pass  # Typed rejection acceptable
