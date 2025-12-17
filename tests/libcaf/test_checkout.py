import pytest
import shutil
from libcaf.repository import Repository, branch_ref, HashRef
from libcaf.exceptions import RepositoryError

def test_checkout_fails_if_dirty(temp_repo: Repository) -> None:
    """Ensure checkout aborts if working directory has uncommitted changes."""
    test_file = temp_repo.working_dir / "file.txt"
    test_file.write_text("v1")
    temp_repo.commit_working_dir("User", "Commit 1")

    test_file.write_text("dirty content")

    temp_repo.add_branch("feature")
    temp_repo.update_ref(branch_ref("feature"), temp_repo.head_commit())
    
    with pytest.raises(RepositoryError):
        temp_repo.checkout("feature")

def test_checkout_switch_branches(temp_repo: Repository) -> None:
    """Test switching between branches updates files correctly."""
    file_a = temp_repo.working_dir / "a.txt"
    file_a.write_text("Content A")
    commit_a = temp_repo.commit_working_dir("User", "Commit A")

    temp_repo.add_branch("feature")
    temp_repo.update_ref(branch_ref("feature"), commit_a)
    
    temp_repo.checkout("feature")

    file_b = temp_repo.working_dir / "b.txt"
    file_b.write_text("Content B")
    temp_repo.commit_working_dir("User", "Commit B")

    assert file_b.exists()
    assert file_a.exists()

    temp_repo.checkout("main")
    
    assert file_a.exists()
    assert not file_b.exists()
    assert temp_repo.head_ref() == branch_ref("main")

    temp_repo.checkout("feature")
    assert file_b.exists()
    assert file_b.read_text() == "Content B"

def test_checkout_detached_head_commit(temp_repo: Repository) -> None:
    """Test checking out a specific commit hash (Detached HEAD)."""
    (temp_repo.working_dir / "f.txt").write_text("v1")
    commit_1 = temp_repo.commit_working_dir("User", "v1")

    (temp_repo.working_dir / "f.txt").write_text("v2")
    commit_2 = temp_repo.commit_working_dir("User", "v2")

    temp_repo.checkout(str(commit_1))

    assert (temp_repo.working_dir / "f.txt").read_text() == "v1"
    
    assert temp_repo.head_ref() == commit_1
    assert isinstance(temp_repo.head_ref(), HashRef)

def test_checkout_tag(temp_repo: Repository) -> None:
    """Test checking out a tag (Detached HEAD)."""
    (temp_repo.working_dir / "f.txt").write_text("stable")
    commit_hash = temp_repo.commit_working_dir("User", "stable commit")

    tag_name = "v1.0"
    temp_repo.create_tag(tag_name, str(commit_hash), "User", "Release")

    (temp_repo.working_dir / "f.txt").write_text("newer")
    temp_repo.commit_working_dir("User", "newer")

    temp_repo.checkout(tag_name)

    assert (temp_repo.working_dir / "f.txt").read_text() == "stable"
    assert temp_repo.head_ref() == commit_hash

def test_checkout_modification_and_directory(temp_repo: Repository) -> None:
    """Test that file modifications and directory creation/deletion work."""
    root_file = temp_repo.working_dir / "root.txt"
    root_file.write_text("root v1")
    
    sub_dir = temp_repo.working_dir / "subdir"
    sub_dir.mkdir()
    sub_file = sub_dir / "sub.txt"
    sub_file.write_text("sub v1")
    
    commit_1 = temp_repo.commit_working_dir("User", "State 1")

    root_file.write_text("root v2")
    
    shutil.rmtree(sub_dir)
    
    new_dir = temp_repo.working_dir / "newdir"
    new_dir.mkdir()
    (new_dir / "deep.txt").write_text("deep")
    
    commit_2 = temp_repo.commit_working_dir("User", "State 2")

    assert root_file.read_text() == "root v2"
    assert not sub_dir.exists()
    assert (new_dir / "deep.txt").exists()

    temp_repo.checkout(str(commit_1))

    assert root_file.read_text() == "root v1"
    assert sub_dir.exists()
    assert sub_file.exists()
    assert not new_dir.exists()

def test_checkout_detects_move(temp_repo: Repository) -> None:
    """Test that moving a file is handled correctly."""
    file_a = temp_repo.working_dir / "a.txt"
    file_a.write_text("MOVE_ME")
    commit_1 = temp_repo.commit_working_dir("User", "Init")

    file_a.unlink()
    file_b = temp_repo.working_dir / "b.txt"
    file_b.write_text("MOVE_ME")
    
    commit_2 = temp_repo.commit_working_dir("User", "Moved")

    temp_repo.checkout(str(commit_1))
    assert file_a.exists()
    assert not file_b.exists()

    temp_repo.checkout(str(commit_2))
    assert not file_a.exists()
    assert file_b.exists()
    assert file_b.read_text() == "MOVE_ME"

def test_checkout_ambiguous_ref(temp_repo: Repository) -> None:
    """Test that branches take precedence over tags."""
    (temp_repo.working_dir / "f.txt").write_text("base")
    c1 = temp_repo.commit_working_dir("User", "base")

    temp_repo.add_branch("release")
    temp_repo.update_ref(branch_ref("release"), c1)
    
    (temp_repo.working_dir / "f.txt").write_text("advanced")
    c2 = temp_repo.commit_working_dir("User", "advanced")
    
    temp_repo.create_tag("release", str(c2), "User", "msg")

    temp_repo.checkout("release")

    assert temp_repo.head_commit() == c1
    
    current_head = temp_repo.head_ref()
    assert current_head == branch_ref("release")

def test_checkout_modifies_deeply_nested_file(temp_repo: Repository) -> None:
    deep_path = temp_repo.working_dir / "level1" / "level2" / "deep_file.txt"
    deep_path.parent.mkdir(parents=True)
    deep_path.write_text("v1")
    
    commit_1 = temp_repo.commit_working_dir("User", "Init Deep")

    deep_path.write_text("v2")
    commit_2 = temp_repo.commit_working_dir("User", "Update Deep")

    temp_repo.checkout(str(commit_1))

    assert deep_path.read_text() == "v1"

    temp_repo.checkout(str(commit_2))
    assert deep_path.read_text() == "v2"