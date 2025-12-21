"""Defines the different types of diffs that can occur between two commits."""
from dataclasses import dataclass

from . import TreeRecord


@dataclass
class Diff:
    """A class representing a difference between two tree records."""

    record: TreeRecord
    parent: 'Diff | None'
    children: list['Diff']


@dataclass
class AddedDiff(Diff):
    """An added tree record diff as part of a commit."""


@dataclass
class RemovedDiff(Diff):
    """A removed tree record diff as part of a commit."""


@dataclass
class ModifiedDiff(Diff):
    """A modified tree record diff as part of a commit."""


@dataclass
class MovedToDiff(Diff):
    """A tree record diff that has been moved elsewhere as part of a commit."""

    moved_to: 'MovedFromDiff | None'


@dataclass
class MovedFromDiff(Diff):
    """A tree record diff that has been moved from elsewhere as part of a commit."""

    moved_from: MovedToDiff | None
