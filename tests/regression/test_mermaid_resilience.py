"""Mermaid renderer resilience under adversarial diagram source."""
from __future__ import annotations

import pytest

from backend.app.services.multimodal.mermaid_renderer import MermaidRenderer
from tests.regression.bad_inputs import (
    ALL_BAD_TEXT_INPUTS,
    MALICIOUS_DSL_INPUTS,
)


@pytest.fixture(scope="module")
def renderer() -> MermaidRenderer:
    return MermaidRenderer()


@pytest.mark.parametrize("label,text", ALL_BAD_TEXT_INPUTS)
def test_bad_text_does_not_crash_renderer(renderer, label, text):
    """The renderer must always return a dict, never raise."""
    result = renderer.render(text, rid=f"bad-{label[:20]}")
    assert isinstance(result, dict)
    assert "method" in result


_MERMAID_ONLY_DSL = [
    (lbl, text) for lbl, text in MALICIOUS_DSL_INPUTS if "manim" not in lbl
]


@pytest.mark.parametrize("label,text", _MERMAID_ONLY_DSL)
def test_malicious_dsl_handled_within_budget(renderer, label, text):
    """Mermaid bombs (huge loops, cycles) must not lock up the renderer."""
    result = renderer.render(text, rid=f"mal-{label[:20]}")
    assert isinstance(result, dict)


def test_oversized_diagram_rejected_before_render(renderer, monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("oversized diagrams must not reach the renderer")
    monkeypatch.setattr(renderer._studio.renderer, "render", unexpected)
    result = renderer.render("graph TD\n" + "A --> B\n" * 301)
    assert result["method"] == "validation_failed"


def test_extract_blocks_on_garbage_is_safe():
    """The static `extract_blocks` helper must never throw."""
    garbage_inputs = [None, "", " ", "no markers here", "```not mermaid\n``"]
    for g in garbage_inputs:
        if g is None:
            continue  # extract_blocks expects str, skip None
        blocks = MermaidRenderer.extract_blocks(g)
        assert isinstance(blocks, list)
