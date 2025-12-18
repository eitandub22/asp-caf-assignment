"""Checkout module for applying diffs to the working directory."""
import shutil
from collections.abc import Sequence
from pathlib import Path

from . import Tree, TreeRecordType
from .diff import (
    AddedDiff,
    Diff,
    ModifiedDiff,
    MovedFromDiff,
    MovedToDiff,
    RemovedDiff,
)
from .plumbing import load_tree, open_content_for_reading


class TraversalError(Exception):
    """Exception raised when traversal of a tree structure fails."""

class MissingMovedFromError(Exception):
    """Exception raised when a moved-from node is missing."""

class MoveError(Exception):
    """Exception raised when a move operation fails."""


def read_object_bytes(objects_dir: Path, hash_value: str) -> bytes:
    """Read the bytes of an object from the object store."""
    with open_content_for_reading(objects_dir, hash_value) as f:
        return f.read()

def rewrite_modified_file(working_dir: Path, objects_dir: Path, target_path: Path, target_tree: Tree) -> None:
    """Find the correct blob in the target tree and rewrite the file at target_path.

    :param working_dir: The root of the working directory.
    :param objects_dir: The directory where objects are stored.
    :param target_path: The path to the file to rewrite.
    :param target_tree: The root tree of the target commit.
    """
    try:
        rel_path = target_path.relative_to(working_dir)
    except ValueError:
        msg = f'Target path {target_path} is not inside working directory {working_dir}'
        raise TraversalError(msg)

    current_tree = target_tree
    for part in rel_path.parts[:-1]:
        record = current_tree.records.get(part)
        if record is None or record.type != TreeRecordType.TREE:
            msg = f'Path does not resolve to a directory: {target_path}'
            raise TraversalError(msg)
        current_tree = load_tree(objects_dir, record.hash)

    leaf = rel_path.parts[-1]
    if leaf is None:
        msg = f'Invalid target path: {target_path}'
        raise TraversalError(msg)
    record = current_tree.records.get(leaf)
    if record is None or record.type != TreeRecordType.BLOB:
        msg = f'Path does not resolve to a file: {target_path}'
        raise TraversalError(msg)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(read_object_bytes(objects_dir, record.hash))

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

def apply_diffs(diffs: Sequence[Diff], working_dir: Path, objects_dir: Path, target_tree: Tree) -> None:
    """Apply a sequence of diffs to the working directory.

    :param diffs: The sequence of Diff objects to apply.
    :raises RepositoryError: If applying any of the diffs fails.
    """
    cwd = working_dir
    stack = [(diff, cwd / diff.record.name) for diff in reversed(diffs)]

    while stack:
        current_diff, curr_path = stack.pop()

        match current_diff:
            case AddedDiff():
                if current_diff.record.type == TreeRecordType.TREE:
                    curr_path.mkdir(parents=True, exist_ok=True)
                else:
                    curr_path.parent.mkdir(parents=True, exist_ok=True)
                    curr_path.write_bytes(read_object_bytes(objects_dir, current_diff.record.hash))

            case RemovedDiff():
                if curr_path.exists():
                    if curr_path.is_dir():
                        has_moves = any(isinstance(c, MovedToDiff) for c in current_diff.children)
                        if not has_moves:
                            shutil.rmtree(curr_path)
                            continue
                    else:
                        curr_path.unlink()

            case ModifiedDiff():
                if current_diff.record.type == TreeRecordType.TREE:
                    curr_path.mkdir(parents=True, exist_ok=True)
                else:
                    rewrite_modified_file(working_dir, objects_dir, curr_path, target_tree)

            case MovedFromDiff():
                moved_from = current_diff.moved_from
                if moved_from is None:
                    continue

                old_path = working_dir / get_moved_to_path(moved_from)

                if not old_path.exists():
                    msg = f'Cannot move missing path: {old_path.relative_to(working_dir)}'
                    raise MissingMovedFromError(msg)

                curr_path.parent.mkdir(parents=True, exist_ok=True)

                try:
                    shutil.move(str(old_path), str(curr_path))
                except Exception as e:
                    msg = f'Failed to move {old_path.relative_to(working_dir)} to {curr_path.relative_to(working_dir)}'
                    raise MoveError(msg) from e

            case MovedToDiff():
                # Handled in MovedFromDiff so we don't process moves twice
                pass

        for diff in reversed(current_diff.children):
            stack.append((diff, curr_path / diff.record.name))
