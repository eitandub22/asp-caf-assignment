"""Checkout module for applying diffs to the working directory."""
import shutil
from collections.abc import Sequence
from pathlib import Path

from . import TreeRecordType
from .diff import (
    AddedDiff,
    Diff,
    ModifiedDiff,
    MovedFromDiff,
    MovedToDiff,
    RemovedDiff,
)
from .plumbing import open_content_for_reading


class TraversalError(Exception):
    """Exception raised when traversal of a tree structure fails."""

class MissingMovedFromError(Exception):
    """Exception raised when a moved-from node is missing."""

class MoveError(Exception):
    """Exception raised when a move operation fails."""

class RemoveError(Exception):
    """Exception raised when a remove operation fails."""

class WriteError(Exception):
    """Exception raised when a write operation fails."""

def get_moved_to_path(diff: MovedToDiff) -> Path:
    """Get the new path for a moved-to diff.

    :param diff: The MovedToDiff object.
    :return: The new path as a Path object.
    """
    parts = []
    curr = diff
    while curr and curr.parent:
        if curr.record.name:
            parts.append(curr.record.name)
        curr = curr.parent
    return Path(*reversed(parts))

def traverse_pre_order(diffs: Sequence[Diff], cwd: Path,
                        moves: list[tuple[MovedFromDiff, Path]],
                        removals: list[tuple[RemovedDiff, Path]],
                        writes: list[tuple[Diff, Path]]) -> None:
    """Traverse diffs in pre-order and categorize them into moves, removals, and writes.

    :param diffs: The sequence of Diff objects to traverse.
    :param cwd: The root of the working directory.
    :param moves: List to collect move operations.
    :param removals: List to collect removal operations.
    :param writes: List to collect write operations.
    """
    stack = [(d, cwd / d.record.name) for d in reversed(diffs)]

    while stack:
        node, path = stack.pop()

        match node:
            case AddedDiff() | ModifiedDiff():
                writes.append((node, path))
            case RemovedDiff():
                removals.append((node, path))
            case MovedFromDiff():
                if node.moved_from:
                    moves.append((node, path))
            case _:
                pass

        # Push children to stack in reverse order to ensure Pre-order popping
        if node.children:
            stack.extend(
                (child, path / child.record.name) for child in reversed(node.children)
            )
    return moves, removals, writes


def apply_diffs(diffs: Sequence[Diff], working_dir: Path, objects_dir: Path) -> None:
    """Apply a sequence of diffs to the working directory.

    :param diffs: The sequence of Diff objects to apply.
    :param working_dir: The root of the working directory.
    :param objects_dir: The directory where objects are stored.
    :raises TraversalError: If resolving paths within the target tree fails.
    :raises MissingMovedFromError: If a move operation refers to a missing source path.
    :raises MoveError: If a move operation in the working directory fails.
    :raises RemoveError: If a removal operation in the working directory fails.
    :raises WriteError: If writing a file to the working directory fails.
    """
    cwd = working_dir

    moves: list[tuple[MovedFromDiff, Path]] = []
    removals: list[tuple[RemovedDiff, Path]] = []
    writes: list[tuple[Diff, Path]] = []

    traverse_pre_order(diffs, cwd, moves, removals, writes)

    # Process moves first to avoid conflicts with removals and writes.
    handle_moves(moves, cwd)

    handle_removals(removals)

    # Process writes (Additions & Modifications)
    # No sorting required - 'writes' is already in Pre-order.
    handle_writes(writes, objects_dir)


def handle_writes(writes: list[tuple[Diff, Path]], objects_dir: Path) -> None:
    """Handle write operations for additions and modifications.

    :param writes: List of tuples containing Diff nodes and their target paths.
    :param objects_dir: The directory where objects are stored.
    :raises WriteError: If writing a file to the working directory fails.
    """
    for node, path in writes:
        if path.exists():
            target_is_dir = (node.record.type == TreeRecordType.TREE)
            disk_is_dir = path.is_dir()

            # If the disk object type is different from the target, we must delete the old one first.
            if target_is_dir != disk_is_dir:
                try:
                    if disk_is_dir:
                        shutil.rmtree(path)
                    else:
                        path.unlink()
                except OSError as e:
                    msg = f'Failed to remove conflicting object {path}'
                    raise WriteError(msg) from e

        if node.record.type == TreeRecordType.TREE:
            path.mkdir(parents=False, exist_ok=True)

        elif node.record.type == TreeRecordType.BLOB:
            path.parent.mkdir(parents=False, exist_ok=True)

            try:
                # Stream object bytes directly to a destination file without loading into RAM.
                with open_content_for_reading(objects_dir, node.record.hash) as src, path.open('wb') as dst:
                    shutil.copyfileobj(src, dst)
            except OSError as e:
                msg = f'Failed to write file {path}'
                raise WriteError(msg) from e

def handle_removals(removals: list[tuple[RemovedDiff, Path]]) -> None:
    """Handle removal operations.

    :param removals: List of tuples containing RemovedDiff nodes and their target paths.
    :param cwd: The root of the working directory.
    :raises RemoveError: If a removal operation in the working directory fails.
    """
    for _, path in removals:
        # If the parent directory was already removed, skip the internal file/directory.
        if not path.exists():
            continue
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        except Exception as e:
            msg = f'Failed to remove {path}'
            raise RemoveError(msg) from e

def handle_moves(moves: list[tuple[MovedFromDiff, Path]], cwd: Path) -> None:
    """Handle move operations.

    :param moves: List of tuples containing MovedFromDiff nodes and their target paths.
    :param cwd: The root of the working directory.
    :raises MoveError: If a move operation in the working directory fails.
    """
    for node, dest_path in moves:
        src_rel = get_moved_to_path(node.moved_from)
        src_path = cwd / src_rel

        if not src_path.exists():
            msg = f'Cannot move missing path: {src_rel}'
            raise MissingMovedFromError(msg)

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(src_path), str(dest_path))
        except Exception as e:
            msg = f'Failed to move {src_rel} to {dest_path}'
            raise MoveError(msg) from e
