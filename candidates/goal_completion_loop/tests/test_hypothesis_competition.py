from fap_goal_loop.hypothesis_competition import BoundedHypothesisCompetition, Hypothesis


def test_competition_is_bounded_and_prefers_supported_low_conflict_candidates():
    competition = BoundedHypothesisCompetition(max_active=2)
    selected = competition.select([
        Hypothesis("cheap-supported", 0.70, support=2, verification_cost=1.0),
        Hypothesis("conflicted", 0.90, support=1, contradictions=2),
        Hypothesis("novel", 0.65, novelty=1.0, verification_cost=1.0),
    ])
    assert [item.key for item in selected] == ["cheap-supported", "novel"]


def test_duplicate_key_keeps_strongest_candidate():
    competition = BoundedHypothesisCompetition(max_active=4)
    selected = competition.select([
        Hypothesis("same", 0.4),
        Hypothesis("same", 0.8, support=1),
    ])
    assert len(selected) == 1
    assert selected[0].confidence == 0.8


def test_hypothesis_does_not_expose_completion_or_verification_state():
    candidate = Hypothesis("candidate", 0.8)
    assert not hasattr(candidate, "verified")
    assert not hasattr(candidate, "completed")


def test_invalid_inputs_fail_closed():
    import pytest

    with pytest.raises(ValueError):
        BoundedHypothesisCompetition(0)
    with pytest.raises(ValueError):
        Hypothesis("", 0.5)
    with pytest.raises(ValueError):
        Hypothesis("bad-confidence", 1.1)
    with pytest.raises(ValueError):
        Hypothesis("bad-cost", 0.5, verification_cost=-1.0)
