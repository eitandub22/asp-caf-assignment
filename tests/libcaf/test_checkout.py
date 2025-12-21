import shutil

import pytest
from libcaf.checkout import MissingMovedFromError
from libcaf.exceptions import RepositoryError
from libcaf.repository import HashRef, Repository, branch_ref


def test_checkout_fails_if_dirty(temp_repo: Repository) -> None:
    """Ensure checkout aborts if working directory has uncommitted changes."""
    test_file = temp_repo.working_dir / 'file.txt'
    test_file.write_text('v1')
    temp_repo.commit_working_dir('User', 'Commit 1')

    test_file.write_text('dirty content')

    temp_repo.add_branch('feature')
    temp_repo.update_ref(branch_ref('feature'), temp_repo.head_commit())

    with pytest.raises(RepositoryError):
        temp_repo.checkout('feature')

def test_checkout_switch_branches(temp_repo: Repository) -> None:
    """Test switching between branches updates files correctly."""
    file_a = temp_repo.working_dir / 'a.txt'
    file_a.write_text('Content A')
    commit_a = temp_repo.commit_working_dir('User', 'Commit A')

    temp_repo.add_branch('feature')
    temp_repo.update_ref(branch_ref('feature'), commit_a)

    temp_repo.checkout('feature')

    file_b = temp_repo.working_dir / 'b.txt'
    file_b.write_text('Content B')
    temp_repo.commit_working_dir('User', 'Commit B')

    assert file_b.exists()
    assert file_a.exists()

    temp_repo.checkout('main')

    assert file_a.exists()
    assert not file_b.exists()
    assert temp_repo.head_ref() == branch_ref('main')
    temp_repo.checkout('feature')
    assert file_a.exists()
    assert file_b.exists()
    assert file_b.read_text() == 'Content B'

def test_checkout_detached_head_commit(temp_repo: Repository) -> None:
    """Test checking out a specific commit hash (Detached HEAD)."""
    (temp_repo.working_dir / 'f.txt').write_text('v1')
    commit_1 = temp_repo.commit_working_dir('User', 'v1')

    (temp_repo.working_dir / 'g.txt').write_text('v2')
    temp_repo.commit_working_dir('User', 'v2')
    temp_repo.checkout(str(commit_1))

    assert (temp_repo.working_dir / 'f.txt').read_text() == 'v1'
    assert not (temp_repo.working_dir / 'g.txt').exists()

    assert temp_repo.head_ref() == commit_1
    assert isinstance(temp_repo.head_ref(), HashRef)

def test_checkout_tag(temp_repo: Repository) -> None:
    """Test checking out a tag (Detached HEAD)."""
    (temp_repo.working_dir / 'f.txt').write_text('stable')
    commit_hash = temp_repo.commit_working_dir('User', 'stable commit')

    tag_name = 'v1.0'
    temp_repo.create_tag(tag_name, str(commit_hash), 'User', 'Release')
    (temp_repo.working_dir / 'g.txt').write_text('newer')
    temp_repo.commit_working_dir('User', 'newer')

    temp_repo.checkout(tag_name)

    assert (temp_repo.working_dir / 'f.txt').read_text() == 'stable'
    assert temp_repo.head_ref() == commit_hash

def test_checkout_modification_and_directory(temp_repo: Repository) -> None:
    """Test that file modifications and directory creation/deletion work."""
    root_file = temp_repo.working_dir / 'root.txt'
    root_file.write_text('root v1')

    sub_dir = temp_repo.working_dir / 'subdir'
    sub_dir.mkdir()
    sub_file = sub_dir / 'sub.txt'
    sub_file.write_text('sub v1')

    commit_1 = temp_repo.commit_working_dir('User', 'State 1')

    root_file.write_text('root v2')

    shutil.rmtree(sub_dir)

    new_dir = temp_repo.working_dir / 'newdir'
    new_dir.mkdir()
    (new_dir / 'deep.txt').write_text('deep')

    temp_repo.commit_working_dir('User', 'State 2')

    assert root_file.read_text() == 'root v2'
    assert not sub_dir.exists()
    assert (new_dir / 'deep.txt').exists()

    temp_repo.checkout(str(commit_1))

    assert root_file.read_text() == 'root v1'
    assert sub_dir.exists()
    assert sub_file.exists()
    assert not new_dir.exists()

def test_checkout_detects_move(temp_repo: Repository) -> None:
    """Test that moving a file is handled correctly."""
    file_a = temp_repo.working_dir / 'a.txt'
    file_a.write_text('MOVE_ME')
    commit_1 = temp_repo.commit_working_dir('User', 'Init')

    file_a.unlink()
    file_b = temp_repo.working_dir / 'b.txt'
    file_b.write_text('MOVE_ME')

    commit_2 = temp_repo.commit_working_dir('User', 'Moved')

    temp_repo.checkout(str(commit_1))
    assert file_a.exists()
    assert not file_b.exists()

    temp_repo.checkout(str(commit_2))
    assert not file_a.exists()
    assert file_b.exists()
    assert file_b.read_text() == 'MOVE_ME'

def test_checkout_ambiguous_ref(temp_repo: Repository) -> None:
    """Test that branches take precedence over tags."""
    (temp_repo.working_dir / 'f.txt').write_text('base')
    c1 = temp_repo.commit_working_dir('User', 'base')

    temp_repo.add_branch('release')
    temp_repo.update_ref(branch_ref('release'), c1)

    (temp_repo.working_dir / 'f.txt').write_text('advanced')
    c2 = temp_repo.commit_working_dir('User', 'advanced')

    temp_repo.create_tag('release', str(c2), 'User', 'msg')

    temp_repo.checkout('release')

    assert temp_repo.head_commit() == c1

    current_head = temp_repo.head_ref()
    assert current_head == branch_ref('release')

def test_checkout_modifies_deeply_nested_file(temp_repo: Repository) -> None:
    deep_path = temp_repo.working_dir / 'level1' / 'level2' / 'deep_file.txt'
    deep_path.parent.mkdir(parents=True)
    deep_path.write_text('v1')

    commit_1 = temp_repo.commit_working_dir('User', 'Init Deep')
    deep_path.write_text('v2')
    commit_2 = temp_repo.commit_working_dir('User', 'Update Deep')

    temp_repo.checkout(str(commit_1))

    assert deep_path.read_text() == 'v1'

    temp_repo.checkout(str(commit_2))
    assert deep_path.read_text() == 'v2'

def test_checkout_mixed_operations(temp_repo: Repository) -> None:
    """Test a commit that includes Adds, Removes, Mods, and Moves simultaneously."""
    wd = temp_repo.working_dir

    (wd / 'modify_me.txt').write_text('v1')
    (wd / 'delete_me.txt').write_text('gone soon')
    (wd / 'move_me.txt').write_text('move content')
    c1 = temp_repo.commit_working_dir('User', 'v1')

    (wd / 'modify_me.txt').write_text('v2')
    (wd / 'delete_me.txt').unlink()
    shutil.move(str(wd / 'move_me.txt'), str(wd / 'moved.txt'))
    (wd / 'add_me.txt').write_text('new')

    c2 = temp_repo.commit_working_dir('User', 'v2')

    # Go back to v1
    temp_repo.checkout(str(c1))

    assert (wd / 'modify_me.txt').read_text() == 'v1'
    assert (wd / 'delete_me.txt').exists()
    assert (wd / 'move_me.txt').exists()
    assert not (wd / 'add_me.txt').exists()

    # Go to v2
    temp_repo.checkout(str(c2))

    assert (wd / 'modify_me.txt').read_text() == 'v2'
    assert not (wd / 'delete_me.txt').exists()
    assert (wd / 'moved.txt').exists()
    assert (wd / 'add_me.txt').exists()

def test_checkout_fails_on_non_existent_ref(temp_repo: Repository) -> None:
    """Test that checkout raises RepositoryError when the target reference (branch/tag/hash) does not exist."""
    (temp_repo.working_dir / 'file.txt').write_text('v1')
    temp_repo.commit_working_dir('User', 'Commit 1')

    target = 'ghost-branch'

    with pytest.raises(RepositoryError):
        temp_repo.checkout(target)

def test_checkout_deep_nested_move(temp_repo: Repository) -> None:
    """Test moving a file between two deep, unrelated directory structures."""
    src = temp_repo.working_dir / 'a' / 'b' / 'c' / 'source.txt'
    src.parent.mkdir(parents=True)
    src.write_text('deep content')
    commit_1 = temp_repo.commit_working_dir('User', 'v1')

    dst = temp_repo.working_dir / 'x' / 'y' / 'z' / 'dest.txt'
    dst.parent.mkdir(parents=True)

    shutil.move(str(src), str(dst))
    shutil.rmtree(temp_repo.working_dir / 'a')

    commit_2 = temp_repo.commit_working_dir('User', 'v2')

    temp_repo.checkout(str(commit_1))
    assert src.exists()
    assert not dst.exists()

    temp_repo.checkout(str(commit_2))

    assert dst.exists()
    assert dst.read_text() == 'deep content'
    assert not src.exists()

def test_checkout_move_out_of_deleted_directory(temp_repo: Repository) -> None:
    """Test moving a file out of a directory that is simultaneously being deleted.

    Verifies that 'src/' is not blindly deleted before 'src/file.txt' is moved.
    """
    src_dir = temp_repo.working_dir / 'src'
    src_dir.mkdir()
    file_src = src_dir / 'file.txt'
    file_src.write_text('precious data')

    commit_1 = temp_repo.commit_working_dir('User', 'Init src')

    file_dst = temp_repo.working_dir / 'file.txt'
    shutil.move(str(file_src), str(file_dst))
    shutil.rmtree(src_dir)

    commit_2 = temp_repo.commit_working_dir('User', 'Move out and delete src')

    temp_repo.checkout(str(commit_1))
    assert file_src.exists()

    temp_repo.checkout(str(commit_2))

    assert not src_dir.exists()
    assert file_dst.exists()
    assert file_dst.read_text() == 'precious data'

def test_checkout_type_swaps(temp_repo: Repository) -> None:
    """Test replacing a file with a directory and vice versa."""
    wd = temp_repo.working_dir

    # --- Commit 1: Setup initial types ---
    # f2d: Starts as File, will become Directory
    # d2f: Starts as Directory, will become File
    (wd / 'f2d').write_text('I am a file')
    (wd / 'd2f').mkdir()
    (wd / 'd2f' / 'inside.txt').write_text('content')

    commit_1 = temp_repo.commit_working_dir('User', 'State 1')

    # --- Commit 2: Swap types ---
    (wd / 'f2d').unlink()
    (wd / 'f2d').mkdir()
    (wd / 'f2d' / 'new_inside.txt').write_text('nested content')

    shutil.rmtree(wd / 'd2f')
    (wd / 'd2f').write_text('I am now a file')

    commit_2 = temp_repo.commit_working_dir('User', 'State 2')

    # --- Verification 1: Switch to State 1 (Reset) ---
    temp_repo.checkout(str(commit_1))
    assert (wd / 'f2d').is_file()
    assert (wd / 'd2f').is_dir()
    assert (wd / 'd2f' / 'inside.txt').exists()

    # --- Verification 2: Switch to State 2 (The Swap) ---
    # This proves Removals happen before Writes.
    # If Writes happened first, (wd/'d2f').write_text() would fail because 'd2f' is still a dir.
    temp_repo.checkout(str(commit_2))

    assert (wd / 'f2d').is_dir()
    assert (wd / 'f2d' / 'new_inside.txt').read_text() == 'nested content'

    assert (wd / 'd2f').is_file()
    assert (wd / 'd2f').read_text() == 'I am now a file'

    # --- Verification 3: Switch back to State 1 (Revert) ---
    temp_repo.checkout(str(commit_1))

    assert (wd / 'f2d').is_file()
    assert (wd / 'f2d').read_text() == 'I am a file'
    assert (wd / 'd2f').is_dir()
