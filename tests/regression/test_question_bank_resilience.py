"""QuestionBank resilience under adversarial lookup keys."""
from __future__ import annotations

import pytest

from backend.app.services.question_bank import get_question_bank, reset_question_bank
from tests.regression.bad_inputs import ALL_BAD_TEXT_INPUTS


@pytest.fixture(scope="module")
def bank():
    reset_question_bank()
    return get_question_bank()


@pytest.mark.parametrize("label,key", ALL_BAD_TEXT_INPUTS)
def test_get_with_bad_key_returns_none_not_crash(bank, label, key):
    """QuestionBank.get(bad_key) returns None instead of raising."""
    result = bank.get(key)
    assert result is None or isinstance(result, dict)


@pytest.mark.parametrize("label,key", ALL_BAD_TEXT_INPUTS)
def test_by_kp_with_bad_key_returns_empty_list(bank, label, key):
    """Filtering by an adversarial kp_id must return [] not raise."""
    result = bank.by_kp(key)
    assert isinstance(result, list)


@pytest.mark.parametrize("label,key", ALL_BAD_TEXT_INPUTS)
def test_by_bloom_with_bad_key_returns_empty_list(bank, label, key):
    result = bank.by_bloom(key)
    assert isinstance(result, list)


def test_filter_with_unknown_difficulty_returns_empty(bank):
    """Difficulty outside 1-5 must not crash."""
    assert bank.filter(difficulty=99) == []
    assert bank.filter(difficulty=-1) == []


def test_sample_with_zero_returns_empty(bank):
    """Edge case: n=0 should return [] not crash."""
    assert bank.sample(0) == []


def test_sample_n_larger_than_pool_returns_pool(bank):
    """If we ask for more than exists, return the full pool without crashing."""
    pool = bank.by_kp("cnn")
    result = bank.sample(10_000, kp_id="cnn")
    assert len(result) == len(pool)


def test_filter_with_combinatorially_impossible_filter_returns_empty(bank):
    """KP that exists + Bloom that exists, but no question with both."""
    impossible = bank.filter(kp_id="cnn", bloom="Create", difficulty=99)
    assert impossible == []
