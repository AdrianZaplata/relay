"""Asset lifecycle domain logic.

Pure, dependency-free state-machine rules — no database, no framework — so the
core invariant (which lifecycle transitions are legal) is trivially testable and
lives in one obvious place. The API and any future caller enforce the same rules
by going through here. See docs/adr/0004.
"""

from enum import StrEnum


class AssetStatus(StrEnum):
    PROVISIONED = "provisioned"
    ACTIVE = "active"
    MAINTENANCE = "maintenance"
    RETIRED = "retired"


# Allowed forward transitions. Anything not listed is rejected.
ALLOWED_TRANSITIONS: dict[AssetStatus, set[AssetStatus]] = {
    AssetStatus.PROVISIONED: {AssetStatus.ACTIVE},
    AssetStatus.ACTIVE: {AssetStatus.MAINTENANCE, AssetStatus.RETIRED},
    AssetStatus.MAINTENANCE: {AssetStatus.ACTIVE, AssetStatus.RETIRED},
    AssetStatus.RETIRED: set(),  # terminal
}


class IllegalTransition(Exception):
    """Raised when a lifecycle transition violates the state machine."""

    def __init__(self, frm: AssetStatus, to: AssetStatus) -> None:
        self.frm = frm
        self.to = to
        super().__init__(f"illegal transition: {frm} -> {to}")


def can_transition(frm: AssetStatus | str, to: AssetStatus | str) -> bool:
    return AssetStatus(to) in ALLOWED_TRANSITIONS.get(AssetStatus(frm), set())


def assert_transition(frm: AssetStatus | str, to: AssetStatus | str) -> None:
    if not can_transition(frm, to):
        raise IllegalTransition(AssetStatus(frm), AssetStatus(to))
