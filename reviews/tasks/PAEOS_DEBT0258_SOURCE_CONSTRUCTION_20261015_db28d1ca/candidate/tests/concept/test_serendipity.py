from __future__ import annotations

import math

from concept.inspiration import score_serendipity


def test_serendipity_is_geometric_relevance_novelty_moderated_by_factors():
    result = score_serendipity(
        {
            "relevance": 0.81,
            "novelty": 0.64,
            "coherence": 0.5,
            "provenance_completeness": 0.8,
        },
        {},
    )
    assert result.unscorable is False
    assert result.relevance == 0.81
    assert result.novelty == 0.64
    assert result.serendipity_score == round(math.sqrt(0.81 * 0.64) * 0.5 * 0.8, 6)


def test_missing_relevance_or_novelty_is_unscorable():
    result = score_serendipity({"relevance": 0.8}, {})
    assert result.unscorable is True
    assert result.serendipity_score is None


def test_serendipity_clamps_declared_factors_to_unit_interval():
    result = score_serendipity(
        {"relevance": 2.0, "novelty": -1.0, "coherence": 4.0, "provenance_completeness": -2.0},
        {"novelty": 0.25},
    )
    assert result.relevance == 1.0
    assert result.novelty == 0.0
    assert result.coherence == 1.0
    assert result.provenance_completeness == 0.0
    assert result.serendipity_score == 0.0
