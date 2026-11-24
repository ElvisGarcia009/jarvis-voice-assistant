"""Tests for the wake-up decision (patience) with a fake openWakeWord model."""
import numpy as np
import pytest

import jarvis


class FakeModel:
    def __init__(self, scores):
        self.scores = iter(scores)

    def predict(self, _chunk):
        return {jarvis.WAKE_MODEL: next(self.scores)}

    def reset(self):
        pass


def wakes(scores, patience, monkeypatch):
    monkeypatch.setitem(jarvis.CFG, "wake",
                        {"threshold": 0.5, "patience": patience, "media_threshold": 0})
    detector = jarvis.WakeDetector(FakeModel(scores))
    chunk = np.zeros(jarvis.CHUNK, np.int16)
    return [detector.feed(chunk) for _ in scores]


@pytest.mark.parametrize("patience, woke", [(1, True), (2, False)])
def test_one_spike(patience, woke, monkeypatch):
    results = wakes([0.1, 0.9, 0.1, 0.1], patience, monkeypatch)
    assert any(results) == woke


def test_held_score_wakes_once(monkeypatch):
    results = wakes([0.1, 0.7, 0.9, 0.95, 0.2], 2, monkeypatch)
    assert [bool(r) for r in results] == [False, False, True, False, False]
