import pytest

from fap_goal_loop.staged_canary import BoundedStagedCanary, CanaryObservation


def obs(key, digest="abc", success=True, quality=0.1, latency=1.0):
    return CanaryObservation(key, digest, success, quality, latency)


def test_stage_evidence_is_isolated_and_bounded():
    canary = BoundedStagedCanary("abc", min_evidence=2, min_success_rate=1.0)
    assert canary.add(obs("a")) == "monitoring"
    assert canary.add(obs("b")) == "advanced"
    assert canary.stage == 0.20
    assert canary.evaluate() == "monitoring"


def test_regression_requests_rollback_without_executing_it():
    canary = BoundedStagedCanary("abc", min_evidence=2, min_success_rate=1.0)
    canary.add(obs("a"))
    assert canary.add(obs("b", success=False)) == "rollback"
    assert not hasattr(canary, "execute")
    assert not hasattr(canary, "verified")
    assert not hasattr(canary, "completed")


def test_latency_regression_requests_rollback():
    canary = BoundedStagedCanary("abc", min_evidence=2, max_latency_ratio=1.25)
    canary.add(obs("a", latency=1.0))
    assert canary.add(obs("b", latency=1.5)) == "rollback"


def test_duplicate_evidence_cannot_fill_stage():
    canary = BoundedStagedCanary("abc", min_evidence=2)
    assert canary.add(obs("same")) == "monitoring"
    assert canary.add(obs("same")) == "monitoring"
    assert canary.stage == 0.05


def test_invalid_or_cross_candidate_evidence_fails_closed():
    with pytest.raises(ValueError):
        BoundedStagedCanary("")
    with pytest.raises(ValueError):
        BoundedStagedCanary("abc", min_success_rate=1.1)
    canary = BoundedStagedCanary("abc", min_evidence=1)
    with pytest.raises(ValueError):
        canary.add(obs("x", digest="other"))
    with pytest.raises(ValueError):
        canary.add(obs("x", latency=0.0))
