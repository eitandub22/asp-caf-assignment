from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from _libcaf import TreeRecord, TreeRecordType, hash_file, load_tree
from libcaf.exceptions import RepositoryError
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from libcaf.repository import Repository

class TreeInterface(ABC):
    """Abstract base class for tree-like structures in the repository."""

    @abstractmethod
    def get_records(self) -> dict[str, TreeRecord]:
        pass

    @abstractmethod
    def get_subtree(self) -> str:
        pass

class DBTree(TreeInterface):
    """Wraps a Tree stored in the CAF database."""
    def __init__(self, tree_hash: str, repo: Repository):
        self.tree_hash = tree_hash
        self._repo = repo
        try:
            self._tree = load_tree(str(repo.objects_dir()), tree_hash)
        except Exception as e:
            raise RepositoryError(f"Failed to load tree {tree_hash}") from e

    def get_records(self) -> dict[str, TreeRecord]:
        return self._tree.records

    def get_subtree(self, record: TreeRecord) -> TreeInterface:
        return DBTree(record.hash, self._repo)
    
class WorkingTree(TreeInterface):
    """Wraps a physical directory on disk."""

    def __init__(self, path: Path, repo: Repository):
        self.path = path
        self._repo = repo

    def get_records(self) -> dict[str, TreeRecord]:
        records = {}

        if not self.path.exists() or not self.path.is_dir():
            return records
        
        for entry in self.path.iterdir():
            if entry.name == '.caf':
                continue

            if entry.is_dir():
                record = TreeRecord(TreeRecordType.TREE, '', entry.name)
            else:
                file_hash = hash_file(str(entry))
                record = TreeRecord(TreeRecordType.BLOB, file_hash, entry.name)
            records[entry.name] = record
        return records
        

    def get_subtree(self, record: TreeRecord) -> TreeInterface:
        return WorkingTree(self.path / record.name, self._repo)
