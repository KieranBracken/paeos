"""Focused unit tests for classify_obj (IP-0006 §4 / Milestone 42)."""

from __future__ import annotations

import pytest
from runtime.lifetime import LifetimeClass, classify_obj
from runtime.task_package import ExecutionContext


def test_classify_obj_known_types() -> None:
    assert classify_obj(ExecutionContext()) is LifetimeClass.L1


def test_classify_obj_unregistered_raises() -> None:
    class _UnregisteredObject:
        pass

    with pytest.raises(KeyError, match="has no declared lifetime_class"):
        classify_obj(_UnregisteredObject())
