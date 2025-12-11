from collections.abc import Sequence
import shutil
from libcaf.repository import (AddedDiff, Diff, ModifiedDiff, MovedFromDiff, MovedToDiff, RemovedDiff, Repository)

def split_diffs_by_type(diffs: Sequence[Diff]) -> \
        tuple[list[AddedDiff],
        list[ModifiedDiff],
        list[MovedToDiff],
        list[MovedFromDiff],
        list[RemovedDiff]]:
    added = [d for d in diffs if isinstance(d, AddedDiff)]
    moved_to = [d for d in diffs if isinstance(d, MovedToDiff)]
    moved_from = [d for d in diffs if isinstance(d, MovedFromDiff)]
    removed = [d for d in diffs if isinstance(d, RemovedDiff)]
    modified = [d for d in diffs if isinstance(d, ModifiedDiff)]

    return added, modified, moved_to, moved_from, removed


def test_diff_head(temp_repo: Repository) -> None:
    file_path = temp_repo.working_dir / 'file.txt'
    file_path.write_text('Same content')

    temp_repo.commit_working_dir('Tester', 'Initial commit')
    diff_result = temp_repo.diff(temp_repo.head_commit(), temp_repo.working_dir)

    assert len(diff_result) == 0


def test_diff_identical_commits(temp_repo: Repository) -> None:
    file_path = temp_repo.working_dir / 'file.txt'
    file_path.write_text('Same content')

    commit_hash = temp_repo.commit_working_dir('Tester', 'Initial commit')
    diff_result = temp_repo.diff(commit_hash, 'HEAD')

    assert len(diff_result) == 0


def test_diff_added_file(temp_repo: Repository) -> None:
    file1 = temp_repo.working_dir / 'file1.txt'
    file1.write_text('Content 1')
    commit1_hash = temp_repo.commit_working_dir('Tester', 'Initial commit')

    file2 = temp_repo.working_dir / 'file2.txt'
    file2.write_text('Content 2')
    temp_repo.commit_working_dir('Tester', 'Added file2')

    diff_result = temp_repo.diff(commit1_hash, temp_repo.head_commit())
    added, modified, moved_to, moved_from, removed = \
        split_diffs_by_type(diff_result)

    assert len(added) == 1
    assert added[0].record.name == 'file2.txt'

    assert len(moved_to) == 0
    assert len(moved_from) == 0
    assert len(removed) == 0
    assert len(modified) == 0


def test_diff_removed_file(temp_repo: Repository) -> None:
    file1 = temp_repo.working_dir / 'file.txt'
    file1.write_text('Content')
    commit1_hash = temp_repo.commit_working_dir('Tester', 'File created')

    file1.unlink()  # Delete the file.
    temp_repo.commit_working_dir('Tester', 'File deleted')

    diff_result = temp_repo.diff(commit1_hash, temp_repo.head_commit())
    added, modified, moved_to, moved_from, removed = \
        split_diffs_by_type(diff_result)

    assert len(added) == 0
    assert len(moved_to) == 0
    assert len(moved_from) == 0
    assert len(modified) == 0

    assert len(removed) == 1
    assert removed[0].record.name == 'file.txt'


def test_diff_modified_file(temp_repo: Repository) -> None:
    file1 = temp_repo.working_dir / 'file.txt'
    file1.write_text('Old content')
    commit1 = temp_repo.commit_working_dir('Tester', 'Original commit')

    file1.write_text('New content')
    commit2 = temp_repo.commit_working_dir('Tester', 'Modified file')

    diff_result = temp_repo.diff(commit1, commit2)
    added, modified, moved_to, moved_from, removed = \
        split_diffs_by_type(diff_result)

    assert len(added) == 0
    assert len(moved_to) == 0
    assert len(moved_from) == 0
    assert len(removed) == 0

    assert len(modified) == 1
    assert modified[0].record.name == 'file.txt'


def test_diff_nested_directory(temp_repo: Repository) -> None:
    subdir = temp_repo.working_dir / 'subdir'
    subdir.mkdir()
    nested_file = subdir / 'file.txt'
    nested_file.write_text('Initial')
    commit1 = temp_repo.commit_working_dir('Tester', 'Commit with subdir')

    nested_file.write_text('Modified')
    commit2 = temp_repo.commit_working_dir('Tester', 'Modified nested file')

    diff_result = temp_repo.diff(commit1, commit2)
    added, modified, moved_to, moved_from, removed = \
        split_diffs_by_type(diff_result)

    assert len(added) == 0
    assert len(moved_to) == 0
    assert len(moved_from) == 0
    assert len(removed) == 0

    assert len(modified) == 1
    assert modified[0].record.name == 'subdir'
    assert len(modified[0].children) == 1
    assert modified[0].children[0].record.name == 'file.txt'


def test_diff_nested_trees(temp_repo: Repository) -> None:
    dir1 = temp_repo.working_dir / 'dir1'
    dir1.mkdir()
    file_a = dir1 / 'file_a.txt'
    file_a.write_text('A1')

    dir2 = temp_repo.working_dir / 'dir2'
    dir2.mkdir()
    file_b = dir2 / 'file_b.txt'
    file_b.write_text('B1')

    commit1 = temp_repo.commit_working_dir('Tester', 'Initial nested commit')

    file_a.write_text('A2')
    file_b.unlink()
    file_c = dir2 / 'file_c.txt'
    file_c.write_text('C1')

    commit2 = temp_repo.commit_working_dir('Tester', 'Updated nested commit')

    diff_result = temp_repo.diff(commit1, commit2)
    added, modified, moved_to, moved_from, removed = \
        split_diffs_by_type(diff_result)

    assert len(added) == 0
    assert len(moved_to) == 0
    assert len(moved_from) == 0
    assert len(removed) == 0

    assert len(modified) == 2

    # We don't know the order of modified directories, so first check if the names exist
    # and then use their indices
    dir_names = [mod.record.name for mod in modified]

    assert 'dir1' in dir_names
    dir1_index = dir_names.index('dir1')

    assert modified[dir1_index].record.name == 'dir1'
    assert len(modified[dir1_index].children) == 1
    assert modified[dir1_index].children[0].record.name == 'file_a.txt'
    assert isinstance(modified[dir1_index].children[0], ModifiedDiff)

    assert 'dir2' in dir_names
    dir2_index = dir_names.index('dir2')

    assert modified[dir2_index].record.name == 'dir2'
    assert len(modified[dir2_index].children) == 2
    assert modified[dir2_index].children[0].record.name == 'file_b.txt'
    assert isinstance(modified[dir2_index].children[0], RemovedDiff)
    assert modified[dir2_index].children[1].record.name == 'file_c.txt'
    assert isinstance(modified[dir2_index].children[1], AddedDiff)


def test_diff_moved_file_added_first(temp_repo: Repository) -> None:
    dir1 = temp_repo.working_dir / 'dir1'
    dir1.mkdir()
    file_a = dir1 / 'file_a.txt'
    file_a.write_text('A1')

    dir2 = temp_repo.working_dir / 'dir2'
    dir2.mkdir()
    file_b = dir2 / 'file_b.txt'
    file_b.write_text('B1')

    commit1 = temp_repo.commit_working_dir('Tester', 'Initial nested commit')

    file_a.rename(dir2 / 'file_c.txt')

    commit2 = temp_repo.commit_working_dir('Tester', 'Updated nested commit')

    diff_result = temp_repo.diff(commit1, commit2)
    added, modified, moved_to, moved_from, removed = \
        split_diffs_by_type(diff_result)

    assert len(added) == 0
    assert len(moved_to) == 0
    assert len(moved_from) == 0
    assert len(removed) == 0

    assert len(modified) == 2

    # We don't know the order of modified directories, so first check if the names exist
    # and then use their indices
    dir_names = [mod.record.name for mod in modified]

    assert 'dir1' in dir_names
    dir1_index = dir_names.index('dir1')

    assert modified[dir1_index].record.name == 'dir1'
    assert len(modified[dir1_index].children) == 1

    modified_child = modified[dir1_index].children[0]
    assert isinstance(modified_child, MovedToDiff)
    assert modified_child.record.name == 'file_a.txt'

    assert isinstance(modified_child.moved_to, MovedFromDiff)
    assert modified_child.moved_to.parent is not None
    assert modified_child.moved_to.parent.record.name == 'dir2'
    assert len(modified_child.moved_to.parent.children) == 1
    assert modified_child.moved_to.record.name == 'file_c.txt'

    assert 'dir2' in dir_names
    dir2_index = dir_names.index('dir2')

    assert modified[dir2_index].record.name == 'dir2'
    assert len(modified[dir2_index].children) == 1

    modified_child = modified[dir2_index].children[0]
    assert isinstance(modified_child, MovedFromDiff)
    assert modified_child.record.name == 'file_c.txt'

    assert isinstance(modified_child.moved_from, MovedToDiff)
    assert modified_child.moved_from.parent is not None
    assert modified_child.moved_from.parent.record.name == 'dir1'
    assert len(modified_child.moved_from.parent.children) == 1
    assert modified_child.moved_from.record.name == 'file_a.txt'


def test_diff_moved_file_removed_first(temp_repo: Repository) -> None:
    dir1 = temp_repo.working_dir / 'dir1'
    dir1.mkdir()
    file_a = dir1 / 'file_a.txt'
    file_a.write_text('A1')

    dir2 = temp_repo.working_dir / 'dir2'
    dir2.mkdir()
    file_b = dir2 / 'file_b.txt'
    file_b.write_text('B1')

    commit1 = temp_repo.commit_working_dir('Tester', 'Initial nested commit')

    file_b.rename(dir1 / 'file_c.txt')

    commit2 = temp_repo.commit_working_dir('Tester', 'Updated nested commit')

    diff_result = temp_repo.diff(commit1, commit2)
    added, modified, moved_to, moved_from, removed = \
        split_diffs_by_type(diff_result)

    assert len(added) == 0
    assert len(moved_to) == 0
    assert len(moved_from) == 0
    assert len(removed) == 0

    assert len(modified) == 2

    # We don't know the order of modified directories, so first check if the names exist
    # and then use their indices
    dir_names = [mod.record.name for mod in modified]

    assert 'dir1' in dir_names
    dir1_index = dir_names.index('dir1')

    assert modified[dir1_index].record.name == 'dir1'
    assert len(modified[dir1_index].children) == 1

    modified_child = modified[dir1_index].children[0]
    assert isinstance(modified_child, MovedFromDiff)
    assert modified_child.record.name == 'file_c.txt'

    assert isinstance(modified_child.moved_from, MovedToDiff)
    assert modified_child.moved_from.parent is not None
    assert modified_child.moved_from.parent.record.name == 'dir2'
    assert len(modified_child.moved_from.parent.children) == 1
    assert modified_child.moved_from.record.name == 'file_b.txt'

    assert 'dir2' in dir_names
    dir2_index = dir_names.index('dir2')

    assert modified[dir2_index].record.name == 'dir2'
    assert len(modified[dir2_index].children) == 1

    modified_child = modified[dir2_index].children[0]
    assert isinstance(modified_child, MovedToDiff)
    assert modified_child.record.name == 'file_b.txt'

    assert isinstance(modified_child.moved_to, MovedFromDiff)
    assert modified_child.moved_to.parent is not None
    assert len(modified_child.moved_to.parent.children) == 1
    assert modified_child.moved_to.parent.record.name == 'dir1'
    assert modified_child.moved_to.record.name == 'file_c.txt'

def test_diff_workdir_clean(temp_repo: Repository) -> None:
    file_path = temp_repo.working_dir / 'file.txt'
    file_path.write_text('Same content')

    temp_repo.commit_working_dir('Tester', 'Initial commit')
    
    diff_result = temp_repo.diff(temp_repo.head_commit(), temp_repo.working_dir)

    assert len(diff_result) == 0

def test_diff_workdir_added_file(temp_repo: Repository) -> None:
    file1 = temp_repo.working_dir / 'file1.txt'
    file1.write_text('Content 1')
    temp_repo.commit_working_dir('Tester', 'Initial commit')

    file2 = temp_repo.working_dir / 'file2.txt'
    file2.write_text('Content 2')

    diff_result = temp_repo.diff(temp_repo.head_commit(), temp_repo.working_dir)
    added, modified, moved_to, moved_from, removed = \
        split_diffs_by_type(diff_result)

    assert len(added) == 1
    assert added[0].record.name == 'file2.txt'

    assert len(moved_to) == 0
    assert len(moved_from) == 0
    assert len(removed) == 0
    assert len(modified) == 0

def test_diff_workdir_removed_file(temp_repo: Repository) -> None:
    file1 = temp_repo.working_dir / 'file.txt'
    file1.write_text('Content')
    temp_repo.commit_working_dir('Tester', 'File created')

    # Delete the file from working directory
    file1.unlink()

    diff_result = temp_repo.diff(temp_repo.head_commit(), temp_repo.working_dir)
    added, modified, moved_to, moved_from, removed = \
        split_diffs_by_type(diff_result)

    assert len(added) == 0
    assert len(moved_to) == 0
    assert len(moved_from) == 0
    assert len(modified) == 0

    assert len(removed) == 1
    assert removed[0].record.name == 'file.txt'

def test_diff_workdir_modified_file(temp_repo: Repository) -> None:
    file1 = temp_repo.working_dir / 'file.txt'
    file1.write_text('Old content')
    temp_repo.commit_working_dir('Tester', 'Original commit')

    # Modify the file in working directory
    file1.write_text('New content')

    diff_result = temp_repo.diff(temp_repo.head_commit(), temp_repo.working_dir)
    added, modified, moved_to, moved_from, removed = \
        split_diffs_by_type(diff_result)

    assert len(added) == 0
    assert len(moved_to) == 0
    assert len(moved_from) == 0
    assert len(removed) == 0

    assert len(modified) == 1
    assert modified[0].record.name == 'file.txt'

def test_diff_workdir_nested_directory(temp_repo: Repository) -> None:
    subdir = temp_repo.working_dir / 'subdir'
    subdir.mkdir()
    nested_file = subdir / 'file.txt'
    nested_file.write_text('Initial')
    temp_repo.commit_working_dir('Tester', 'Commit with subdir')

    # Modify file inside subdir
    nested_file.write_text('Modified')

    diff_result = temp_repo.diff(temp_repo.head_commit(), temp_repo.working_dir)
    added, modified, moved_to, moved_from, removed = \
        split_diffs_by_type(diff_result)

    assert len(added) == 0
    assert len(moved_to) == 0
    assert len(moved_from) == 0
    assert len(removed) == 0

    assert len(modified) == 1
    assert modified[0].record.name == 'subdir'

    # Check children of the directory diff
    assert len(modified[0].children) == 1
    assert modified[0].children[0].record.name == 'file.txt'
    assert isinstance(modified[0].children[0], ModifiedDiff)

def test_diff_workdir_nested_trees_complex(temp_repo: Repository) -> None:
    dir1 = temp_repo.working_dir / 'dir1'
    dir1.mkdir()
    file_a = dir1 / 'file_a.txt'
    file_a.write_text('A1')

    dir2 = temp_repo.working_dir / 'dir2'
    dir2.mkdir()
    file_b = dir2 / 'file_b.txt'
    file_b.write_text('B1')

    temp_repo.commit_working_dir('Tester', 'Initial nested commit')

    # Perform changes in working directory
    file_a.write_text('A2')
    file_b.unlink()
    file_c = dir2 / 'file_c.txt'
    file_c.write_text('C1')

    diff_result = temp_repo.diff(temp_repo.head_commit(), temp_repo.working_dir)
    added, modified, moved_to, moved_from, removed = \
        split_diffs_by_type(diff_result)

    assert len(added) == 0
    assert len(moved_to) == 0
    assert len(moved_from) == 0
    assert len(removed) == 0

    # We expect 2 modified directories at top level
    assert len(modified) == 2

    dir_names = [mod.record.name for mod in modified]

    assert 'dir1' in dir_names
    dir1_index = dir_names.index('dir1')
    assert modified[dir1_index].record.name == 'dir1'
    assert len(modified[dir1_index].children) == 1
    assert modified[dir1_index].children[0].record.name == 'file_a.txt'
    assert isinstance(modified[dir1_index].children[0], ModifiedDiff)

    assert 'dir2' in dir_names
    dir2_index = dir_names.index('dir2')
    assert modified[dir2_index].record.name == 'dir2'
    assert len(modified[dir2_index].children) == 2

    # Children order might vary, so checking existence
    child_names = [child.record.name for child in modified[dir2_index].children]

    assert 'file_b.txt' in child_names
    b_index = child_names.index('file_b.txt')
    assert isinstance(modified[dir2_index].children[b_index], RemovedDiff)

    assert 'file_c.txt' in child_names
    c_index = child_names.index('file_c.txt')
    assert isinstance(modified[dir2_index].children[c_index], AddedDiff)

def test_diff_workdir_moved_file(temp_repo: Repository) -> None:
    dir1 = temp_repo.working_dir / 'dir1'
    dir1.mkdir()
    file_a = dir1 / 'file_a.txt'
    file_a.write_text('Unique Content For Move')

    dir2 = temp_repo.working_dir / 'dir2'
    dir2.mkdir()

    temp_repo.commit_working_dir('Tester', 'Initial commit')

    file_a.rename(dir2 / 'file_a.txt')

    diff_result = temp_repo.diff(temp_repo.head_commit(), temp_repo.working_dir)
    added, modified, moved_to, moved_from, removed = \
        split_diffs_by_type(diff_result)

    # Since we modified directories (dir1 and dir2), the moves are nested inside ModifiedDiffs for the directories
    assert len(modified) == 2

    dir_names = [mod.record.name for mod in modified]

    assert 'dir1' in dir_names
    dir1_index = dir_names.index('dir1')
    dir1_diff = modified[dir1_index]

    assert len(dir1_diff.children) == 1
    child1 = dir1_diff.children[0]
    assert isinstance(child1, MovedToDiff)
    assert child1.record.name == 'file_a.txt'

    assert 'dir2' in dir_names
    dir2_index = dir_names.index('dir2')
    dir2_diff = modified[dir2_index]

    assert len(dir2_diff.children) == 1
    child2 = dir2_diff.children[0]
    assert isinstance(child2, MovedFromDiff)
    assert child2.record.name == 'file_a.txt'

    assert child1.moved_to == child2
    assert child2.moved_from == child1

def test_diff_workdir_type_change(temp_repo: Repository) -> None:
    """Test detecting a type change (File becomes Directory and vice-versa)."""

    file_path = temp_repo.working_dir / 'a_file'
    file_path.write_text('content')

    dir_path = temp_repo.working_dir / 'a_dir'
    dir_path.mkdir()
    (dir_path / 'nested').write_text('nested content')

    temp_repo.commit_working_dir('Tester', 'Initial commit')

    file_path.unlink()
    file_path.mkdir()

    shutil.rmtree(dir_path)

    dir_path = temp_repo.working_dir / 'a_dir'
    dir_path.write_text('I am a file now')

    diff_result = temp_repo.diff(temp_repo.head_commit(), temp_repo.working_dir)
    added, modified, moved_to, moved_from, removed = \
        split_diffs_by_type(diff_result)

    assert len(modified) == 2

    names = [m.record.name for m in modified]
    assert 'a_file' in names
    assert 'a_dir' in names

    file_diff = next(d for d in modified if d.record.name == 'a_file')
    assert isinstance(file_diff, ModifiedDiff)
    assert len(file_diff.children) == 0

    dir_diff = next(d for d in modified if d.record.name == 'a_dir')
    assert isinstance(dir_diff, ModifiedDiff)

    assert len(dir_diff.children) == 0

def test_diff_workdir_added_directory(temp_repo: Repository) -> None:
    temp_repo.commit_working_dir('Tester', 'Initial commit')

    new_dir = temp_repo.working_dir / 'new_dir'
    new_dir.mkdir()
    (new_dir / 'nested_file.txt').write_text('content')

    diffs = temp_repo.diff(temp_repo.head_commit(), temp_repo.working_dir)

    assert len(diffs) == 1
    assert isinstance(diffs[0], AddedDiff)
    assert diffs[0].record.name == 'new_dir'

    assert len(diffs[0].children) == 1
    assert isinstance(diffs[0].children[0], AddedDiff)
    assert diffs[0].children[0].record.name == 'nested_file.txt'

def test_diff_workdir_moved_file_detection(temp_repo: Repository) -> None:
    """Test detecting a file move (rename) in the working directory."""
    file_path = temp_repo.working_dir / 'old_name.txt'
    file_path.write_text('unique content for move')
    temp_repo.commit_working_dir('Tester', 'Initial commit')

    file_path.rename(temp_repo.working_dir / 'new_name.txt')

    diffs = temp_repo.diff(temp_repo.head_commit(), temp_repo.working_dir)

    assert len(diffs) == 2

    new_file_diff = next(d for d in diffs if d.record.name == 'new_name.txt')

    assert isinstance(new_file_diff, MovedFromDiff)
    assert new_file_diff.moved_from is not None
    assert new_file_diff.moved_from.record.name == 'old_name.txt'

def test_diff_removed_directory(temp_repo: Repository) -> None:
    dir_path = temp_repo.working_dir / 'to_be_deleted'
    dir_path.mkdir()
    (dir_path / 'file.txt').write_text('content')

    commit1 = temp_repo.commit_working_dir('Tester', 'Initial commit')

    shutil.rmtree(dir_path)

    commit2 = temp_repo.commit_working_dir('Tester', 'Deleted directory')

    diff_result = temp_repo.diff(commit1, commit2)

    assert len(diff_result) == 1
    folder_diff = diff_result[0]

    assert isinstance(folder_diff, RemovedDiff)
    assert folder_diff.record.name == 'to_be_deleted'

    assert len(folder_diff.children) == 1
    file_diff = folder_diff.children[0]

    assert isinstance(file_diff, RemovedDiff)
    assert file_diff.record.name == 'file.txt'

def test_directory_with_files_removed(temp_repo: Repository) -> None:
    dir_path = temp_repo.working_dir / 'my_folder'
    dir_path.mkdir()
    (dir_path / 'file1.txt').write_text('content1')
    (dir_path / 'file2.txt').write_text('content2')

    commit1 = temp_repo.commit_working_dir('Tester', 'Initial commit')

    (dir_path / 'file1.txt').unlink()
    (dir_path / 'file2.txt').unlink()

    shutil.rmtree(dir_path)

    diff_result = temp_repo.diff(commit1, temp_repo.working_dir)

    added, modified, moved_to, moved_from, removed = \
        split_diffs_by_type(diff_result)

    assert len(diff_result) == 1
    folder_diff = diff_result[0]

    assert isinstance(folder_diff, RemovedDiff)
    assert folder_diff.record.name == 'my_folder'

    assert len(folder_diff.children) == 2

    file_names = [child.record.name for child in folder_diff.children]
    assert 'file1.txt' in file_names
    assert 'file2.txt' in file_names

    for child in folder_diff.children:
        assert isinstance(child, RemovedDiff)

def test_diff_two_directories_added(temp_repo: Repository) -> None:
    temp_repo.commit_working_dir('Tester', 'Initial commit')

    dir1 = temp_repo.working_dir / 'dir1'
    dir1.mkdir()
    (dir1 / 'subdir1').mkdir()
    (dir1 / 'subdir2').mkdir()

    dir2 = temp_repo.working_dir / 'dir2'
    dir2.mkdir()
    (dir2 / 'file3.txt').write_text('content3')

    diff_result = temp_repo.diff(dir1, dir2)
    added, modified, moved_to, moved_from, removed = \
        split_diffs_by_type(diff_result)

    assert len(added) == 1
    assert added[0].record.name == 'file3.txt'

    assert len(modified) == 0
    assert len(moved_to) == 0
    assert len(moved_from) == 0

    assert len(removed) == 2
    removed_names = [d.record.name for d in removed]
    assert 'subdir1' in removed_names
    assert 'subdir2' in removed_names

def test_directory_move_detection(temp_repo: Repository) -> None:
    src_dir = temp_repo.working_dir / 'src'
    src_dir.mkdir()
    (src_dir / 'data.txt').write_text('important data')
    (src_dir / 'config.json').write_text('{"key": "value"}')

    temp_repo.commit_working_dir('Tester', 'Initial commit')

    shutil.move(src_dir, temp_repo.working_dir / 'dst')

    diffs = temp_repo.diff(temp_repo.head_commit(), temp_repo.working_dir)
    added, modified, moved_to, moved_from, removed = split_diffs_by_type(diffs)

    assert len(added) == 0
    assert len(removed) == 0

    names = [d.record.name for d in diffs]
    assert 'src' in names
    assert 'dst' in names

    src_diff = next(d for d in diffs if d.record.name == 'src')
    dst_diff = next(d for d in diffs if d.record.name == 'dst')

    assert isinstance(src_diff, MovedToDiff)
    assert isinstance(dst_diff, MovedFromDiff)
    
    assert src_diff.moved_to == dst_diff

def test_directory_content_modification_propagates_hash(temp_repo: Repository) -> None:
    docs_dir = temp_repo.working_dir / 'docs'
    docs_dir.mkdir()
    (docs_dir / 'readme.txt').write_text('v1')
    
    commit1 = temp_repo.commit_working_dir('Tester', 'v1')

    (docs_dir / 'readme.txt').write_text('v2')
    
    diffs = temp_repo.diff(commit1, temp_repo.working_dir)
    added, modified, moved_to, moved_from, removed = split_diffs_by_type(diffs)

    assert len(modified) == 1
    assert modified[0].record.name == 'docs'
    
    assert len(modified[0].children) == 1
    assert modified[0].children[0].record.name == 'readme.txt'
    assert isinstance(modified[0].children[0], ModifiedDiff)

def test_fs_vs_fs_different_content(temp_repo: Repository) -> None:
    dirA = temp_repo.working_dir / 'dirA'
    dirA.mkdir()
    (dirA / 'file.txt').write_text('AAA')

    dirB = temp_repo.working_dir / 'dirB'
    dirB.mkdir()
    (dirB / 'file.txt').write_text('BBB')

    diffs = temp_repo.diff(dirA, dirB)

    assert len(diffs) == 1
    assert isinstance(diffs[0], ModifiedDiff)
    assert diffs[0].record.name == 'file.txt'