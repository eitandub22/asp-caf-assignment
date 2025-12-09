from pathlib import Path
from _libcaf import Tree, TreeRecord, TreeRecordType, hash_file
    
class WorkingTree:
    """Wraps a physical directory on disk."""

    def __init__(self, path: Path):
        self.path = path

    def get_records(self) -> dict[str, TreeRecord]:
        records = {}

        if not self.path.exists() or not self.path.is_dir():
            raise FileNotFoundError(f"Directory {self.path} does not exist or is not a directory.")
        
        for entry in sorted(self.path.iterdir()):
            if entry.name == '.caf':
                continue

            if entry.is_dir():
                record = TreeRecord(TreeRecordType.TREE, '', entry.name)
            else:
                file_hash = hash_file(str(entry))
                record = TreeRecord(TreeRecordType.BLOB, file_hash, entry.name)
            records[entry.name] = record
        return records
    
    @property
    def records(self) -> dict[str, TreeRecord]:
        return self.get_records()