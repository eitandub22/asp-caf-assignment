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

class RemoveError(Exception):
    """Exception raised when a remove operation fails."""

class WriteError(Exception):
    """Exception raised when a write operation fails."""


def read_object_bytes(objects_dir: Path, hash_value: str) -> bytes:
    """Read the bytes of an object from the object store."""
    with open_content_for_reading(objects_dir, hash_value) as f:
        return f.read()

def rewrite_modified_file(working_dir: Path, objects_dir: Path, target_path: Path, target_tree: Tree | None) -> None:
    """Find the correct blob in the target tree and rewrite the file at target_path.

    :param working_dir: The root of the working directory.
    :param objects_dir: The directory where objects are stored.
    :param target_path: The path to the file to rewrite.
    :param target_tree: The root tree of the target commit.
    """
    try:
        rel_path = target_path.relative_to(working_dir)
    except OSError as err:
        msg = f'Target path {target_path} is not inside working directory {working_dir}'
        raise TraversalError(msg) from err

    if target_tree is None:
        msg = f'Target tree is None when trying to rewrite file: {target_path}'
        raise TraversalError(msg)

    current_tree = target_tree
    for part in rel_path.parts[:-1]:
        record = current_tree.records.get(part)
        if record is None or record.type != TreeRecordType.TREE:
            msg = f'Path does not resolve to a directory: {target_path}'
            raise TraversalError(msg)
        current_tree = load_tree(objects_dir, record.hash)

    record = current_tree.records.get(rel_path.parts[-1])
    if record is None or record.type != TreeRecordType.BLOB:
        msg = f'Path does not resolve to a file: {target_path}'
        raise TraversalError(msg)
    target_path.parent.mkdir(parents=False, exist_ok=True)
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

def move_sort_key(item: tuple[MovedFromDiff, Path]) -> int:
    """Sort key for move operations based on the depth of the moved-to path."""
    return len(get_moved_to_path(item[0].moved_from).parts)

def traverse_post_order(diffs: Sequence[Diff], cwd: Path,
                        moves: list[tuple[MovedFromDiff, Path]],
                        removals: list[tuple[RemovedDiff, Path]],
                        writes: list[tuple[Diff, Path]]) -> None:
    """Traverse diffs in post-order and categorize them into moves, removals, and writes."""
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


def apply_diffs(diffs: Sequence[Diff], working_dir: Path, objects_dir: Path, target_tree: Tree | None) -> None:
    """Apply a sequence of diffs to the working directory.

    :param diffs: The sequence of Diff objects to apply.
    :param working_dir: The root of the working directory.
    :param objects_dir: The directory where objects are stored.
    :param target_tree: The root tree of the target commit.
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

    traverse_post_order(diffs, cwd, moves, removals, writes)

    # Process moves first to avoid conflicts with removals and writes.
    # Handle shallowest moves first to ensure parent directories exist for deeper moves.
    handle_moves(moves, cwd)

    # Process removals - deepest first.
    # This prevents erroring on a child file after its parent dir is removed.
    handle_removals(removals)

    # Process writes (Additions & Modifications)
    # No sorting required - 'writes' is already in Pre-order.
    handle_writes(writes, cwd, objects_dir, target_tree)


def handle_writes(writes: list[tuple[Diff, Path]], cwd: Path, objects_dir: Path, target_tree: Tree | None) -> None:
    """Handle write operations for additions and modifications.

    :param writes: List of tuples containing Diff nodes and their target paths.
    :param cwd: The root of the working directory.
    :param objects_dir: The directory where objects are stored.
    :param target_tree: The root tree of the target commit.
    :raises WriteError: If writing a file to the working directory fails.
    """
    for node, path in writes:
        if node.record.type == TreeRecordType.TREE:
            path.mkdir(parents=False, exist_ok=True)

        elif node.record.type == TreeRecordType.BLOB:
            path.parent.mkdir(parents=False, exist_ok=True)

            if isinstance(node, AddedDiff):
                try:
                    path.write_bytes(read_object_bytes(objects_dir, node.record.hash))
                except OSError as e:
                    msg = f'Failed to write file {path}'
                    raise WriteError(msg) from e
            elif isinstance(node, ModifiedDiff):
                rewrite_modified_file(cwd, objects_dir, path, target_tree)

def handle_removals(removals: list[tuple[RemovedDiff, Path]]) -> None:
    """Handle removal operations.

    :param removals: List of tuples containing RemovedDiff nodes and their target paths.
    :param cwd: The root of the working directory.
    :raises RemoveError: If a removal operation in the working directory fails.
    """
    removals.sort(key=lambda x: len(x[1].parts), reverse=True)

    for _, path in removals:
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
    moves.sort(key=move_sort_key)

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
