from __future__ import annotations

import pytest

from fap_critic_cascade import CascadeCritic, CriticStage
from fap_media_generation import Critique, CritiqueIssue


class CountingCritic:
    def __init__(self, score, *, fatal=False):
        self.score = score
        self.fatal = fatal
        self.calls = 0

    def critique(self, request, artifact):
        self.calls += 1
        issues = ()
        if self.fatal:
            issues = (CritiqueIssue("fatal", "fatal defect", "fatal"),)
        elif self.score < 0.9:
            issues = (CritiqueIssue("quality", "quality defect", "medium", "repair quality"),)
        return Critique(self.score, issues, evidence={"calls": self.calls})


def test_bad_candidate_skips_expensive_critics():
    cheap = CountingCritic(0.30)
    expensive = CountingCritic(0.99)
    critic = CascadeCritic([
        CriticStage("cheap", cheap, continue_floor=0.60),
        CriticStage("expensive", expensive, continue_floor=0.0),
    ])
    result = critic.critique(None, object())
    assert result.score == 0.30
    assert cheap.calls == 1
    assert expensive.calls == 0
    assert result.evidence["cascade"]["skipped"] == ("expensive",)


def test_good_candidate_runs_full_stack():
    cheap = CountingCritic(0.96)
    expensive = CountingCritic(0.93)
    critic = CascadeCritic([
        CriticStage("cheap", cheap, continue_floor=0.60),
        CriticStage("expensive", expensive),
    ])
    result = critic.critique(None, object())
    assert result.score == 0.93
    assert cheap.calls == 1
    assert expensive.calls == 1
    assert result.evidence["cascade"]["stop"] == "complete"


def test_fatal_short_circuits_immediately():
    cheap = CountingCritic(0.99, fatal=True)
    expensive = CountingCritic(1.0)
    critic = CascadeCritic([
        CriticStage("safety", cheap, continue_floor=0.0),
        CriticStage("expensive", expensive),
    ])
    result = critic.critique(None, object())
    assert result.has_fatal
    assert result.score == 0.0
    assert expensive.calls == 0


def test_minimum_score_preserved_when_complete():
    a = CountingCritic(0.98)
    b = CountingCritic(0.91)
    c = CountingCritic(0.95)
    result = CascadeCritic([
        CriticStage("a", a, 0.5),
        CriticStage("b", b, 0.5),
        CriticStage("c", c, 0.5),
    ]).critique(None, object())
    assert result.score == 0.91


def test_duplicate_stage_names_rejected():
    c = CountingCritic(1.0)
    with pytest.raises(ValueError):
        CascadeCritic([
            CriticStage("same", c),
            CriticStage("same", c),
        ])


def test_invalid_floor_rejected():
    with pytest.raises(ValueError):
        CascadeCritic([CriticStage("bad", CountingCritic(1.0), 1.1)])
