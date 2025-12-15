from pathlib import Path
from typing import Tuple
from .plumbing import hash_file, hash_object
from . import Tree, TreeRecord, TreeRecordType

class MissingHashError(Exception):
    """Custom exception raised when a required hash is missing."""

def build_fsTree(path: Path, tree_hashes: dict[str, Tree], repo_dir_name: str) -> Tuple[Tree, str]:
        """
        Builds a Tree structure from the filesystem in memory.
        Populates 'tree_hashes' with hash -> Tree mappings.
        Returns the hash of the root tree.

        :param path: The directory path to build the tree from.
        :param tree_hashes: A dictionary to populate with tree hashes and their corresponding Tree objects.
        :param repo_dir_name: The name of the repository directory to ignore.
        :return: The root Tree object.
        """
        if not path.is_dir():
            raise NotADirectoryError(f"{path} is not a directory")

        traversal_stack = [path]
        
        # Stores directories in the order we found them 
        # We will iterate this in reverse order to build trees from the bottom up
        build_order = []

        while traversal_stack:
            current_path = traversal_stack.pop()
            build_order.append(current_path)

            for entry in sorted(current_path.iterdir(), reverse=True):
                if entry.name == repo_dir_name:
                    continue
                if entry.is_dir():
                    traversal_stack.append(entry)

        dir_hashes: dict[Path, str] = {}

        while build_order:
            current_path = build_order.pop()
            tree_records: dict[str, TreeRecord] = {}

            for entry in sorted(current_path.iterdir()):
                if entry.name == repo_dir_name:
                    continue

                if entry.is_dir():
                    if entry not in dir_hashes:
                         raise MissingHashError(f"Missing hash for subdirectory {entry}")
                    
                    subtree_hash = dir_hashes[entry]
                    record = TreeRecord(TreeRecordType.TREE, subtree_hash, entry.name)
                else:
                    file_hash = hash_file(str(entry))
                    record = TreeRecord(TreeRecordType.BLOB, file_hash, entry.name)
                
                tree_records[entry.name] = record

            tree = Tree(tree_records)
            t_hash = hash_object(tree)
            tree_hashes[t_hash] = tree
            
            dir_hashes[current_path] = t_hash

        return tree_hashes[dir_hashes[path]], dir_hashes[path]