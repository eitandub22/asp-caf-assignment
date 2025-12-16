"""libcaf repository management."""

import shutil
from collections import deque
from collections.abc import Callable, Generator, Sequence
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Concatenate, Tuple
from . import Blob, Commit, Tree, TreeRecord, TreeRecordType, Tag
from .constants import (DEFAULT_BRANCH, DEFAULT_REPO_DIR, HASH_CHARSET, HASH_LENGTH, HEADS_DIR, HEAD_FILE,
                        OBJECTS_SUBDIR, REFS_DIR, TAGS_DIR)
from .plumbing import hash_object, load_commit, load_tree, open_content_for_reading, save_commit, save_file_content, save_tree, save_tag, load_tag
from .ref import HashRef, Ref, RefError, SymRef, read_ref, write_ref
from .exceptions import TagNotFound, TagExistsError, TagError, UnknownHashError, RepositoryError, RepositoryNotFoundError
from .internal import build_fsTree, MissingHashError

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


@dataclass
class LogEntry:
    """A class representing a log entry for a branch or commit history."""

    commit_ref: HashRef
    commit: Commit


class Repository:
    """Represents a libcaf repository.

    This class provides methods to initialize a repository, manage branches,
    commit changes, and perform various operations on the repository."""

    def __init__(self, working_dir: Path | str, repo_dir: Path | str | None = None) -> None:
        """Initialize a Repository instance. The repository is not created on disk until `init()` is called.

        :param working_dir: The working directory where the repository will be located.
        :param repo_dir: The name of the repository directory within the working directory. Defaults to '.caf'."""
        self.working_dir = Path(working_dir)

        if repo_dir is None:
            self.repo_dir = Path(DEFAULT_REPO_DIR)
        else:
            self.repo_dir = Path(repo_dir)

    def init(self, default_branch: str = DEFAULT_BRANCH) -> None:
        """Initialize a new CAF repository in the working directory.

        :param default_branch: The name of the default branch to create. Defaults to 'main'.
        :raises RepositoryError: If the repository already exists or if the working directory is invalid."""
        self.repo_path().mkdir(parents=True)
        self.objects_dir().mkdir()

        heads_dir = self.heads_dir()
        heads_dir.mkdir(parents=True)

        tags_dir = self.tags_dir()
        tags_dir.mkdir(parents=True)

        self.add_branch(default_branch)

        write_ref(self.head_file(), branch_ref(default_branch))

    def exists(self) -> bool:
        """Check if the repository exists in the working directory.

        :return: True if the repository exists, False otherwise."""
        return self.repo_path().exists()

    def repo_path(self) -> Path:
        """Get the path to the repository directory.

        :return: The path to the repository directory."""
        return self.working_dir / self.repo_dir

    def objects_dir(self) -> Path:
        """Get the path to the objects directory within the repository.

        :return: The path to the objects directory."""
        return self.repo_path() / OBJECTS_SUBDIR

    def refs_dir(self) -> Path:
        """Get the path to the refs directory within the repository.

        :return: The path to the refs directory."""
        return self.repo_path() / REFS_DIR

    def heads_dir(self) -> Path:
        """Get the path to the heads directory within the repository.

        :return: The path to the heads directory."""
        return self.refs_dir() / HEADS_DIR
    
    def tags_dir(self) -> Path:
        """Get the path to the tags directory within the repository.

        :return: The path to the tags directory."""
        return self.refs_dir() / TAGS_DIR

    @staticmethod
    def requires_repo[**P, R](func: Callable[Concatenate['Repository', P], R]) -> \
            Callable[Concatenate['Repository', P], R]:
        """Decorate a Repository method to ensure that the repository exists before executing the method.

        :param func: The method to decorate.
        :return: A wrapper function that checks for the repository's existence."""

        @wraps(func)
        def _verify_repo(self: 'Repository', *args: P.args, **kwargs: P.kwargs) -> R:
            if not self.exists():
                msg = f'Repository not initialized at {self.repo_path()}'
                raise RepositoryNotFoundError(msg)

            return func(self, *args, **kwargs)

        return _verify_repo

    @requires_repo
    def head_ref(self) -> Ref | None:
        """Get the current HEAD reference of the repository.

        :return: The current HEAD reference, which can be a HashRef or SymRef.
        :raises RepositoryError: If the HEAD ref file does not exist.
        :raises RepositoryNotFoundError: If the repository does not exist."""
        head_file = self.head_file()
        if not head_file.exists():
            msg = 'HEAD ref file does not exist'
            raise RepositoryError(msg)

        return read_ref(head_file)

    @requires_repo
    def head_commit(self) -> HashRef | None:
        """Return a ref to the current commit reference of the HEAD.

        :return: The current commit reference, or None if HEAD is not a commit.
        :raises RepositoryError: If the HEAD ref file does not exist.
        :raises RepositoryNotFoundError: If the repository does not exist."""
        # If HEAD is a symbolic reference, resolve it to a hash
        resolved_ref = self.resolve_ref(self.head_ref())
        if resolved_ref:
            return resolved_ref
        return None

    @requires_repo
    def refs(self) -> list[SymRef]:
        """Get a list of all symbolic references in the repository.

        :return: A list of SymRef objects representing the symbolic references.
        :raises RepositoryError: If the refs directory does not exist or is not a directory.
        :raises RepositoryNotFoundError: If the repository does not exist."""
        refs_dir = self.refs_dir()
        if not refs_dir.exists() or not refs_dir.is_dir():
            msg = f'Refs directory does not exist or is not a directory: {refs_dir}'
            raise RepositoryError(msg)

        refs: list[SymRef] = [SymRef(ref_file.name) for ref_file in refs_dir.rglob('*')
                              if ref_file.is_file()]

        return refs

    @requires_repo
    def resolve_ref(self, ref: Ref | str | None) -> HashRef | None:
        """Resolve a reference to a HashRef, following symbolic references if necessary.

        :param ref: The reference to resolve. This can be a HashRef, SymRef, or a string.
        :return: The resolved HashRef or None if the reference does not exist.
        :raises RefError: If the reference is invalid or cannot be resolved.
        :raises RepositoryNotFoundError: If the repository does not exist."""
        match ref:
            case HashRef():
                return ref
            case SymRef(ref):
                if ref.upper() == 'HEAD':
                    return self.resolve_ref(self.head_ref())

                resolved = read_ref(self.refs_dir() / ref)
                if (
                    resolved
                    and isinstance(resolved, HashRef)
                    and str(ref).startswith(f'{TAGS_DIR}/')
                ):
                    try:
                        tag_obj = load_tag(self.objects_dir(), resolved)
                    except Exception as e:
                        msg = f'Error loading tag object {resolved}'
                        raise RepositoryError(msg) from e
                    return HashRef(tag_obj.commit_hash)

                return self.resolve_ref(resolved)
            case str():
                # Try to figure out what kind of ref it is by looking at the list of refs
                # in the refs directory
                if ref.upper() == 'HEAD' or ref in self.refs():
                    return self.resolve_ref(SymRef(ref))
                if len(ref) == HASH_LENGTH and all(c in HASH_CHARSET for c in ref):
                    return HashRef(ref)

                msg = f'Invalid reference: {ref}'
                raise RefError(msg)
            case None:
                return None
            case _:
                msg = f'Invalid reference type: {type(ref)}'
                raise RefError(msg)

    @requires_repo
    def update_ref(self, ref_name: str, new_ref: Ref) -> None:
        """Update a symbolic reference in the repository.

        :param ref_name: The name of the symbolic reference to update.
        :param new_ref: The new reference value to set.
        :raises RepositoryError: If the reference does not exist.
        :raises RepositoryNotFoundError: If the repository does not exist."""
        ref_path = self.refs_dir() / ref_name

        if not ref_path.exists():
            msg = f'Reference "{ref_name}" does not exist.'
            raise RepositoryError(msg)

        write_ref(ref_path, new_ref)

    @requires_repo
    def delete_repo(self) -> None:
        """Delete the entire repository, including all objects and refs.

        :raises RepositoryNotFoundError: If the repository does not exist."""
        shutil.rmtree(self.repo_path())

    @requires_repo
    def save_file_content(self, file: Path) -> Blob:
        """Save the content of a file to the repository.

        :param file: The path to the file to save.
        :return: A Blob object representing the saved file content.
        :raises ValueError: If the file does not exist.
        :raises RepositoryNotFoundError: If the repository does not exist."""
        return save_file_content(self.objects_dir(), file)

    @requires_repo
    def add_branch(self, branch: str) -> None:
        """Add a new branch to the repository, initialized to be an empty reference.

        :param branch: The name of the branch to add.
        :raises ValueError: If the branch name is empty.
        :raises RepositoryError: If the branch already exists.
        :raises RepositoryNotFoundError: If the repository does not exist."""
        if not branch:
            msg = 'Branch name is required'
            raise ValueError(msg)
        if self.branch_exists(SymRef(branch)):
            msg = f'Branch "{branch}" already exists'
            raise RepositoryError(msg)

        (self.heads_dir() / branch).touch()

    @requires_repo
    def delete_branch(self, branch: str) -> None:
        """Delete a branch from the repository.

        :param branch: The name of the branch to delete.
        :raises ValueError: If the branch name is empty.
        :raises RepositoryError: If the branch does not exist or if it is the last branch in the repository.
        :raises RepositoryNotFoundError: If the repository does not exist."""
        if not branch:
            msg = 'Branch name is required'
            raise ValueError(msg)
        branch_path = self.heads_dir() / branch

        if not branch_path.exists():
            msg = f'Branch "{branch}" does not exist.'
            raise RepositoryError(msg)
        if len(self.branches()) == 1:
            msg = f'Cannot delete the last branch "{branch}".'
            raise RepositoryError(msg)

        branch_path.unlink()

    @requires_repo
    def branch_exists(self, branch_ref: Ref) -> bool:
        """Check if a branch exists in the repository.

        :param branch_ref: The reference to the branch to check.
        :return: True if the branch exists, False otherwise.
        :raises RepositoryNotFoundError: If the repository does not exist."""
        return (self.heads_dir() / branch_ref).exists()

    @requires_repo
    def branches(self) -> list[str]:
        """Get a list of all branch names in the repository.

        :return: A list of branch names.
        :raises RepositoryNotFoundError: If the repository does not exist."""
        return [x.name for x in self.heads_dir().iterdir() if x.is_file()]

    @requires_repo
    def save_dir(self, path: Path) -> HashRef:
        """Save the content of a directory to the repository.

        :param path: The path to the directory to save.
        :return: A HashRef object representing the saved directory tree object.
        :raises NotADirectoryError: If the path is not a directory.
        :raises RepositoryNotFoundError: If the repository does not exist."""
        if not path or not path.is_dir():
            msg = f'{path} is not a directory'
            raise NotADirectoryError(msg)

        stack = deque([path])
        hashes: dict[Path, str] = {}

        while stack:
            current_path = stack.pop()
            tree_records: dict[str, TreeRecord] = {}

            for item in current_path.iterdir():
                if item.name == self.repo_dir.name:
                    continue
                if item.is_file():
                    blob = self.save_file_content(item)
                    tree_records[item.name] = TreeRecord(TreeRecordType.BLOB, blob.hash, item.name)
                elif item.is_dir():
                    if item in hashes:  # If the directory has already been processed, use its hash
                        subtree_hash = hashes[item]
                        tree_records[item.name] = TreeRecord(TreeRecordType.TREE, subtree_hash, item.name)
                    else:
                        stack.append(current_path)
                        stack.append(item)
                        break
            else:
                tree = Tree(tree_records)
                save_tree(self.objects_dir(), tree)
                hashes[current_path] = hash_object(tree)

        return HashRef(hashes[path])

    @requires_repo
    def commit_working_dir(self, author: str, message: str) -> HashRef:
        """Commit the current working directory to the repository.

        :param author: The name of the commit author.
        :param message: The commit message.
        :return: A HashRef object representing the commit reference.
        :raises ValueError: If the author or message is empty.
        :raises RepositoryError: If the commit process fails.
        :raises RepositoryNotFoundError: If the repository does not exist."""
        if not author:
            msg = 'Author is required'
            raise ValueError(msg)
        if not message:
            msg = 'Commit message is required'
            raise ValueError(msg)

        # See if HEAD is a symbolic reference to a branch that we need to update
        # if the commit process is successful.
        # Otherwise, there is nothing to update and HEAD will continue to point
        # to the detached commit.
        # Either way the commit HEAD eventually resolves to becomes the parent of the new commit.
        head_ref = self.head_ref()
        branch = head_ref if isinstance(head_ref, SymRef) else None
        parent_commit_ref = self.head_commit()

        # Save the current working directory as a tree
        tree_hash = self.save_dir(self.working_dir)

        commit = Commit(tree_hash, author, message, int(datetime.now().timestamp()), parent_commit_ref)
        commit_ref = HashRef(hash_object(commit))

        save_commit(self.objects_dir(), commit)

        if branch:
            self.update_ref(branch, commit_ref)

        return commit_ref

    @requires_repo
    def log(self, tip: Ref | None = None) -> Generator[LogEntry, None, None]:
        """Generate a log of commits in the repository, starting from the specified tip.

        :param tip: The reference to the commit to start from. If None, defaults to the current HEAD.
        :return: A generator yielding LogEntry objects representing the commits in the log.
        :raises RepositoryError: If a commit cannot be loaded.
        :raises RepositoryNotFoundError: If the repository does not exist."""
        tip = tip or self.head_ref()
        current_hash = self.resolve_ref(tip)

        try:
            while current_hash:
                commit = load_commit(self.objects_dir(), current_hash)
                yield LogEntry(HashRef(current_hash), commit)

                current_hash = HashRef(commit.parent) if commit.parent else None
        except Exception as e:
            msg = f'Error loading commit {current_hash}'
            raise RepositoryError(msg) from e
        
        
    def _resolve_target(self, t: Ref | Path | None, tree_hashes: dict[str, Tree]) -> Tuple[Tree, str]:
        """
        Resolves a target to a tree hash.
        The target `t` can be either:
            - A `Path` object: The method builds a Tree from the filesystem at the given path,
              populates `tree_hashes` with the resulting trees, and returns the root tree hash.
            - A `Ref` object or None: The method resolves the reference to a commit hash,
              loads the corresponding commit, and returns its tree hash.
        :param t: The target to resolve, which can be a `Path`, a `Ref`, or None.
        :param tree_hashes: A dictionary to populate with tree hashes and their corresponding Tree objects.
        :return: The resolved Tree object and its hash.
        :raises RepositoryError: If the path is not a directory or if a commit cannot be loaded.
        :raises RefError: If the reference cannot be resolved.
        """
        if isinstance(t, Path):
            try:
                root, root_hash = build_fsTree(t, tree_hashes, self.repo_dir.name)
            except NotADirectoryError as e:
                msg = f'Path {t} is not a directory'
                raise RepositoryError(msg) from e
            except MissingHashError as e:
                msg = f'Error building tree from path {t}'
                raise RepositoryError(msg) from e
            return root, root_hash
        
        commit_hash = self.resolve_ref(t)
        if commit_hash is None:
            msg = f'Cannot resolve reference {t}'
            raise RefError(msg)
        
        try:
            commit = load_commit(self.objects_dir(), commit_hash)
            tree_hashes[commit.tree_hash] = load_tree(self.objects_dir(), commit.tree_hash)
        except Exception as e:
            raise RepositoryError(f"Failed to load commit {commit_hash}") from e
        return tree_hashes[commit.tree_hash], commit.tree_hash
    
    def _load_tree(self, record_hash: str, tree_hashes: dict[str, Tree]) -> Tree:
        if record_hash in tree_hashes:
            return tree_hashes[record_hash]
        # Cache miss - load from disk
        tree_hashes[record_hash] = load_tree(self.objects_dir(), record_hash)
        return tree_hashes[record_hash]
    
    @requires_repo
    def diff(self, target1: Ref | Path | None = None, target2: Ref | Path | None = None) -> Sequence[Diff]:
        """Compare two targets (commits, refs, or paths) and generate a diff.

        This method calculates the differences between two trees. The trees can be specified
        by a commit reference (hash or branch name) or a filesystem path (to any directory).

        :param target1: The first target to compare. Can be a commit hash, branch name, or Path.
        :param target2: The second target to compare. Can be a commit hash, branch name, or Path.
        :return: A list of Diff objects representing the changes.
        :raises RepositoryError: If a target cannot be resolved.
        :raises RepositoryNotFoundError: If the repository does not exist."""

        if target1 is None:
            msg = 'The first diff target must be given'
            raise ValueError(msg)
        if target2 is None:
            msg = 'The second diff target must be given'
            raise ValueError(msg)
        
        tree_hashes: dict[str, Tree] = {}

        try:
            tree1, tree1_hash = self._resolve_target(target1, tree_hashes)
            tree2, tree2_hash = self._resolve_target(target2, tree_hashes)
        except RefError as e:
            msg = 'Error resolving commit reference for diff'
            raise RepositoryError(msg) from e

        if tree1_hash == tree2_hash:
            return []

        top_level_diff = Diff(TreeRecord(TreeRecordType.TREE, '', ''), None, [])
        stack = [(tree1, tree2, top_level_diff)]

        potentially_added: dict[str, Diff] = {}
        potentially_removed: dict[str, Diff] = {}

        while stack:
            current_tree1, current_tree2, parent_diff = stack.pop()
            records1 = current_tree1.records if current_tree1 else {}
            records2 = current_tree2.records if current_tree2 else {}

            for name, record1 in records1.items():
                if name not in records2:
                    local_diff: Diff

                    # This name is no longer in the tree, so it was either moved or removed
                    # Have we seen this hash before as a potentially-added record?
                    if record1.hash in potentially_added:
                        added_diff = potentially_added[record1.hash]
                        del potentially_added[record1.hash]

                        local_diff = MovedToDiff(record1, parent_diff, [], None)
                        moved_from_diff = MovedFromDiff(added_diff.record, added_diff.parent, [], local_diff)
                        local_diff.moved_to = moved_from_diff

                        # Replace the original added diff with a moved-from diff
                        added_diff.parent.children = (
                            [_ if _.record.hash != record1.hash
                             else moved_from_diff
                             for _ in added_diff.parent.children])

                    else:
                        local_diff = RemovedDiff(record1, parent_diff, [])
                        potentially_removed[record1.hash] = local_diff

                        if record1.type == TreeRecordType.TREE:
                            try:
                                stack.append((self._load_tree(record1.hash, tree_hashes), None, local_diff))
                            except Exception as e:
                                msg = 'Error loading subtree for diff'
                                raise RepositoryError(msg) from e

                    parent_diff.children.append(local_diff)
                else:
                    record2 = records2[name]

                    # This record is identical in both trees, so no diff is needed
                    if record1.hash == record2.hash:
                        continue

                    # If the record is a tree, we need to recursively compare the trees
                    if record1.type == TreeRecordType.TREE and record2.type == TreeRecordType.TREE:
                        subtree_diff = ModifiedDiff(record1, parent_diff, [])

                        try:
                            tree1 = self._load_tree(record1.hash, tree_hashes)
                            tree2 = self._load_tree(record2.hash, tree_hashes)
                        except Exception as e:
                            msg = 'Error loading subtree for diff'
                            raise RepositoryError(msg) from e

                        stack.append((tree1, tree2, subtree_diff))
                        parent_diff.children.append(subtree_diff)
                    else:
                        modified_diff = ModifiedDiff(record1, parent_diff, [])
                        parent_diff.children.append(modified_diff)

            for name, record2 in records2.items():
                if name not in records1:
                    # This name is in the new tree but not in the old tree, so it was either
                    # added or moved
                    # If we've already seen this hash, it was moved, so convert the original
                    # added diff to a moved diff
                    if record2.hash in potentially_removed:
                        removed_diff = potentially_removed[record2.hash]
                        del potentially_removed[record2.hash]

                        local_diff = MovedFromDiff(record2, parent_diff, [], None)
                        moved_to_diff = MovedToDiff(removed_diff.record, removed_diff.parent, [], local_diff)
                        local_diff.moved_from = moved_to_diff

                        # Create a new diff for the moved record
                        removed_diff.parent.children = (
                            [_ if _.record.hash != record2.hash
                             else moved_to_diff
                             for _ in removed_diff.parent.children])

                    else:
                        local_diff = AddedDiff(record2, parent_diff, [])
                        potentially_added[record2.hash] = local_diff

                        if record2.type == TreeRecordType.TREE:
                            try:
                                stack.append((None, self._load_tree(record2.hash, tree_hashes), local_diff))
                            except Exception as e:
                                msg = 'Error loading subtree for diff'
                                raise RepositoryError(msg) from e

                    parent_diff.children.append(local_diff)

        return top_level_diff.children

    def head_file(self) -> Path:
        """Get the path to the HEAD file within the repository.

        :return: The path to the HEAD file."""
        return self.repo_path() / HEAD_FILE
    
    @requires_repo
    def tags(self) -> list[Tag]:
        """Get a list of all tags in the repository.

        :return: A list of tags.
        :raises RepositoryNotFoundError: If the repository does not exist."""
        tags = []
        tag_names = [x.name for x in self.tags_dir().iterdir() if x.is_file()]

        for tag_name in tag_names:
            tag_path = self.tags_dir() / tag_name
            tag_object_hash = read_ref(tag_path)
            tag = load_tag(self.objects_dir(), tag_object_hash)
            tags.append(tag)

        return tags
    
    @requires_repo
    def delete_tag(self, tag_name: str) -> None:
        """Delete a tag from the repository.

        :param tag_name: The name of the tag to delete.
        :raises ValueError: If the tag name is empty.
        :raises RepositoryNotFoundError: If the repository does not exist."""
        if not tag_name:
            msg = 'Tag name is required'
            raise ValueError(msg)
        tag_path = self.tags_dir() / tag_name

        if not tag_path.exists():
            raise TagNotFound(tag_name)

        tag_path.unlink()
    
    @requires_repo
    def create_tag(self, tag_name: str, commit_hash: str, author: str, message: str) -> None:
        """Add a new tag to the repository.

        :param tag_name: The name of the tag to add.
        :param commit_hash: The hash of the commit the tag will point to.
        :param author: The name of the tag author.
        :param message: The tag message.
        :raises ValueError: If the tag name is empty.
        :raises RepositoryError: If the tag already exists.
        :raises RepositoryNotFoundError: If the repository does not exist."""
        if not tag_name:
            msg = 'Tag name is required'
            raise ValueError(msg)
                
        if not commit_hash or len(commit_hash) != HASH_LENGTH or not all(c in HASH_CHARSET for c in commit_hash):
            msg = f'Invalid commit hash: {commit_hash}'
            raise ValueError(msg)
        
        if not author:
            msg = 'Tag author is required'
            raise ValueError(msg)
        
        if not message:
            msg = 'Tag message is required'
            raise ValueError(msg)
        
        # Verify that the commit exists
        if not (self.objects_dir() / commit_hash[:2] / commit_hash).is_file():
            raise UnknownHashError(commit_hash)
        
        try:
            commit = load_commit(self.objects_dir(), HashRef(commit_hash))

        except Exception as e:
            raise RepositoryError(e) from e
        
        tag_path = self.tags_dir() / tag_name

        # Check if the tag already exists, to avoid overwriting
        if tag_path.exists():
            raise TagExistsError(tag_path)

        try:
            tag_obj = Tag(tag_name, commit_hash, author, message, int(datetime.now().timestamp()))
            tag_object_hash = hash_object(tag_obj)
            save_tag(self.objects_dir(), tag_obj)
            write_ref(tag_path, tag_object_hash)
        except RefError as e:
            raise TagError(f"Failed to write tag to {tag_path}: {e}") from e
        
    @requires_repo
    def status(self) -> Sequence[Diff]:
        return self.diff(self.head_commit(), self.working_dir)
    
    def _resolve_checkout_target(self, target: str) -> Ref | None:
        """ Resolve a checkout target to a Ref.

            The resolution is done by scanning the refs directory so we can distinguish between
            branches and tags by location.
            If there is a collision between a branch and a tag name, the branch takes precedence similair to Git.

            :param target: The checkout target provided by the user.
            :return: The resolved Ref object or None if the target does not exist.
        """

        if not isinstance(target, str):
            msg = f'Invalid checkout target type: {type(target)}'
            raise RefError(msg)

        if len(target) == HASH_LENGTH and all(c in HASH_CHARSET for c in target):
            return HashRef(target)

        explicit_path = self.refs_dir() / target
        if explicit_path.exists() and explicit_path.is_file():
            return SymRef(target)

        branch_path = self.heads_dir() / target
        if branch_path.exists():
            return branch_ref(target)

        tag_path = self.tags_dir() / target
        if tag_path.exists():
            return tag_ref(target)

        return None

    def _apply_diffs(self, diffs: Sequence[Diff], target_root: Tree, tree_cache: dict[str, Tree]) -> None:
        """ 
            Apply a sequence of diffs to the working directory.

            :param diffs: The sequence of Diff objects to apply.
            :raises RepositoryError: If applying any of the diffs fails.
        """
        def relpath_for(node: Diff) -> Path:
            parts: list[str] = []
            current: Diff | None = node
            while current is not None and current.parent is not None:
                if current.record.name:
                    parts.append(current.record.name)
                current = current.parent
            return Path(*reversed(parts))

        def read_object_bytes(hash_value: str) -> bytes:
            with open_content_for_reading(self.objects_dir(), hash_value) as f:
                return f.read()

        def record_at_path(root: Tree, rel_path: Path, tree_cache: dict[str, Tree]) -> TreeRecord:
            current_tree = root
            parts = list(rel_path.parts)
            if not parts:
                msg = 'Cannot resolve record at empty path'
                raise RepositoryError(msg)

            for part in parts[:-1]:
                record = current_tree.records.get(part)
                if record is None or record.type != TreeRecordType.TREE:
                    msg = f'Path does not resolve to a directory: {rel_path}'
                    raise RepositoryError(msg)
                current_tree = self._load_tree(record.hash, tree_cache)

            leaf = current_tree.records.get(parts[-1])
            if leaf is None:
                msg = f'Record not found in target tree: {rel_path}'
                raise RepositoryError(msg)
            return leaf

        # Flatten diff tree so ordering can be applied globally.
        all_nodes: list[Diff] = []
        stack = list(diffs)
        while stack:
            node = stack.pop()
            all_nodes.append(node)
            if node.children:
                stack.extend(node.children)

        added: list[AddedDiff] = []
        removed: list[RemovedDiff] = []
        modified: list[ModifiedDiff] = []
        moved_from: list[MovedFromDiff] = []

        for node in all_nodes:
            if isinstance(node, AddedDiff):
                added.append(node)
            elif isinstance(node, RemovedDiff):
                removed.append(node)
            elif isinstance(node, ModifiedDiff):
                modified.append(node)
            elif isinstance(node, MovedFromDiff):
                moved_from.append(node)

        cwd = self.working_dir

        if target_root is None:
            msg = 'Internal error: checkout target tree not set'
            raise RepositoryError(msg)

        # Process moves first. Process only MovedFromDiff to avoid double-applying.
        for node in sorted(moved_from, key=lambda d: len(relpath_for(d).parts)):
            if node.moved_from is None:
                continue
            old_rel = relpath_for(node.moved_from)
            new_rel = relpath_for(node)
            old_path = cwd / old_rel
            new_path = cwd / new_rel

            if not old_path.exists():
                msg = f'Cannot move missing path: {old_rel}'
                raise RepositoryError(msg)

            new_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                shutil.move(str(old_path), str(new_path))
            except Exception as e:
                msg = f'Failed to move {old_rel} to {new_rel}'
                raise RepositoryError(msg) from e
            
        # Now process removals.
        # We remove from the deepest paths first to avoid issues with non-empty directories.
        for node in sorted(removed, key=lambda d: len(relpath_for(d).parts), reverse=True):
            rel = relpath_for(node)
            target_path = cwd / rel
            if not target_path.exists():
                continue

            try:
                if target_path.is_dir():
                    shutil.rmtree(target_path)
                else:
                    target_path.unlink()
            except Exception as e:
                msg = f'Failed to remove {rel}'
                raise RepositoryError(msg) from e

        # We move on to additions.
        # Directories must be created before files to ensure the path exists.
        added_dirs = [d for d in added if d.record.type == TreeRecordType.TREE]
        added_blobs = [d for d in added if d.record.type == TreeRecordType.BLOB]

        for node in sorted(added_dirs, key=lambda d: len(relpath_for(d).parts)):
            rel = relpath_for(node)
            (cwd / rel).mkdir(parents=True, exist_ok=True)

        for node in sorted(added_blobs, key=lambda d: len(relpath_for(d).parts)):
            rel = relpath_for(node)
            target_path = cwd / rel
            target_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                target_path.write_bytes(read_object_bytes(node.record.hash))
            except Exception as e:
                msg = f'Failed to add file {rel}'
                raise RepositoryError(msg) from e

        # Finally, process modifications.
        # Directories must be created before files to ensure the path exists.
        for node in sorted(modified, key=lambda d: len(relpath_for(d).parts)):
            rel = relpath_for(node)

            if node.record.type == TreeRecordType.TREE:
                (cwd / rel).mkdir(parents=True, exist_ok=True)
                continue

            if node.record.type != TreeRecordType.BLOB:
                continue

            target_path = cwd / rel
            target_path.parent.mkdir(parents=True, exist_ok=True)
            new_record = record_at_path(target_root, rel, tree_cache)
            if new_record.type != TreeRecordType.BLOB:
                msg = f'Target record is not a file: {rel}'
                raise RepositoryError(msg)
            try:
                target_path.write_bytes(read_object_bytes(new_record.hash))
            except Exception as e:
                msg = f'Failed to modify file {rel}'
                raise RepositoryError(msg) from e

                    
    @requires_repo
    def checkout(self, target: str) -> None:
        """Checkout a target (commit or branch) into the working directory.

        :param target: The target to checkout. Can be a commit hash or a branch name
        :raises RepositoryError: If the target cannot be resolved or if the checkout fails.
        :raises RepositoryNotFoundError: If the repository does not exist."""
        is_clean = self.status() == []

        if not is_clean:
            msg = 'Cannot checkout: working directory has uncommitted changes.'
            raise RepositoryError(msg)
        
        resolved_ref = self._resolve_checkout_target(target)
        if resolved_ref is None:
            msg = f'Cannot resolve reference {target}'
            raise RepositoryError(msg)

        # Build target tree cache for applying ModifiedDiff blobs.
        tree_cache: dict[str, Tree] = {}
        try:
            target_tree, _ = self._resolve_target(resolved_ref, tree_cache)
        except Exception as e:
            msg = f'Cannot resolve checkout target tree for {target}'
            raise RepositoryError(msg) from e

        diffs = self.diff(self.head_commit(), resolved_ref)
        self._apply_diffs(diffs, target_tree, tree_cache)

        if isinstance(resolved_ref, SymRef) and str(resolved_ref).startswith(f'{HEADS_DIR}/'):
            write_ref(self.head_file(), resolved_ref)
            return

        commit_hash = self.resolve_ref(resolved_ref)
        if commit_hash is None:
            msg = f'Cannot resolve commit for checkout target {target}'
            raise RepositoryError(msg)
        write_ref(self.head_file(), commit_hash)

def branch_ref(branch: str) -> SymRef:
    """Create a symbolic reference for a branch name.

    :param branch: The name of the branch.
    :return: A SymRef object representing the branch reference."""
    return SymRef(f'{HEADS_DIR}/{branch}')


def tag_ref(tag: str) -> SymRef:
    """Create a symbolic reference for a tag name.

    :param tag: The name of the tag.
    :return: A SymRef object representing the tag reference."""
    return SymRef(f'{TAGS_DIR}/{tag}')