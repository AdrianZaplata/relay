"""Pure unit tests for the asset lifecycle state machine — no DB, no framework."""

import pytest

from relay.domain import (
    AssetStatus,
    IllegalTransition,
    assert_transition,
    can_transition,
)

LEGAL = [
    (AssetStatus.PROVISIONED, AssetStatus.ACTIVE),
    (AssetStatus.ACTIVE, AssetStatus.MAINTENANCE),
    (AssetStatus.MAINTENANCE, AssetStatus.ACTIVE),
    (AssetStatus.ACTIVE, AssetStatus.RETIRED),
    (AssetStatus.MAINTENANCE, AssetStatus.RETIRED),
]

ILLEGAL = [
    (AssetStatus.PROVISIONED, AssetStatus.MAINTENANCE),
    (AssetStatus.PROVISIONED, AssetStatus.RETIRED),
    (AssetStatus.RETIRED, AssetStatus.ACTIVE),  # terminal
    (AssetStatus.ACTIVE, AssetStatus.ACTIVE),  # no-op is not a transition
]


@pytest.mark.parametrize("frm,to", LEGAL)
def test_legal_transitions_allowed(frm, to):
    assert can_transition(frm, to) is True


@pytest.mark.parametrize("frm,to", ILLEGAL)
def test_illegal_transitions_rejected(frm, to):
    assert can_transition(frm, to) is False
    with pytest.raises(IllegalTransition):
        assert_transition(frm, to)


def test_can_transition_accepts_raw_strings():
    assert can_transition("provisioned", "active") is True
    assert can_transition("retired", "active") is False
