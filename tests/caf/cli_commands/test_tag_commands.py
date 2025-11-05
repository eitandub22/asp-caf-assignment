import pytest
from pathlib import Path
from collections.abc import Callable
from libcaf.repository import Repository
from pytest import CaptureFixture
from caf import cli_commands
from libcaf.constants import HASH_LENGTH

# We need a fixture to get a commit hash.
# Your test_log_command.py and others use `parse_commit_hash`.
# We'll assume that fixture is available from conftest.py
# If not, we'll create a simple commit helper.
@pytest.fixture
def commit_hash(temp_repo: Repository) -> str:
    """Fixture to create a single commit and return its hash."""
    (temp_repo.working_dir / 'file.txt').write_text('content')
    commit_ref = temp_repo.commit_working_dir('Test Author', 'Test Message')
    return str(commit_ref)

# --- Tests for 'tags' (list tags) command ---

def test_tags_command(temp_repo: Repository, commit_hash: str, capsys: CaptureFixture[str]):
    """Tests the happy path for the 'tags' command."""
    cli_commands.create_tag(working_dir_path=temp_repo.working_dir, tag_name='v1.0', commit_hash=commit_hash)
    cli_commands.create_tag(working_dir_path=temp_repo.working_dir, tag_name='v2.0', commit_hash=commit_hash)
    
    assert cli_commands.tags(working_dir_path=temp_repo.working_dir) == 0
    
    output = capsys.readouterr().out
    assert 'Tags:' in output
    assert 'v1.0' in output
    assert 'v2.0' in output

def test_tags_no_tags(temp_repo: Repository, capsys: CaptureFixture[str]):
    """Tests the 'tags' command when no tags exist."""
    assert cli_commands.tags(working_dir_path=temp_repo.working_dir) == 0
    assert 'No tags found' in capsys.readouterr().out

def test_tags_no_repo(temp_repo_dir: Path, capsys: CaptureFixture[str]):
    """Tests the 'tags' command on a non-existent repository."""
    assert cli_commands.tags(working_dir_path=temp_repo_dir) == -1
    assert 'No repository found' in capsys.readouterr().err

# --- Tests for 'create_tag' command ---

def test_create_tag_command(temp_repo: Repository, commit_hash: str, capsys: CaptureFixture[str]):
    """Tests the happy path for the 'create_tag' command."""
    assert cli_commands.create_tag(working_dir_path=temp_repo.working_dir,
                                   tag_name='v1.0', commit_hash=commit_hash) == 0
    assert 'Tag "v1.0" created' in capsys.readouterr().out

def test_create_tag_no_repo(temp_repo_dir: Path, commit_hash: str, capsys: CaptureFixture[str]):
    """Tests 'create_tag' on a non-existent repository."""
    assert cli_commands.create_tag(working_dir_path=temp_repo_dir,
                                   tag_name='v1.0', commit_hash=commit_hash) == -1
    assert 'No repository found' in capsys.readouterr().err

def test_create_tag_missing_args(temp_repo: Repository, commit_hash: str, capsys: CaptureFixture[str]):
    """Tests 'create_tag' with missing arguments."""
    assert cli_commands.create_tag(working_dir_path=temp_repo.working_dir,
                                   tag_name=None, commit_hash=commit_hash) == -1
    assert 'Tag name is required' in capsys.readouterr().err
    
    assert cli_commands.create_tag(working_dir_path=temp_repo.working_dir,
                                   tag_name='v1.0', commit_hash=None) == -1
    assert 'Commit hash is required' in capsys.readouterr().err

def test_create_tag_already_exists(temp_repo: Repository, commit_hash: str, capsys: CaptureFixture[str]):
    """Tests 'create_tag' when the tag already exists."""
    cli_commands.create_tag(working_dir_path=temp_repo.working_dir,
                            tag_name='v1.0', commit_hash=commit_hash)
    capsys.readouterr()  # Clear stdout
    
    assert cli_commands.create_tag(working_dir_path=temp_repo.working_dir,
                                   tag_name='v1.0', commit_hash=commit_hash) == -1

def test_create_tag_nonexistent_hash(temp_repo: Repository, capsys: CaptureFixture[str]):
    """Tests 'create_tag' with a hash that doesn't exist."""
    non_existent_hash = 'a' * HASH_LENGTH
    assert cli_commands.create_tag(working_dir_path=temp_repo.working_dir,
                                   tag_name='v1.0', commit_hash=non_existent_hash) == -1
    assert 'does not exist' in capsys.readouterr().err

# --- Tests for 'delete_tag' command ---

def test_delete_tag_command(temp_repo: Repository, commit_hash: str, capsys: CaptureFixture[str]):
    """Tests the happy path for the 'delete_tag' command."""
    cli_commands.create_tag(working_dir_path=temp_repo.working_dir,
                            tag_name='v1.0', commit_hash=commit_hash)
    capsys.readouterr()  # Clear stdout
    
    assert cli_commands.delete_tag(working_dir_path=temp_repo.working_dir, tag_name='v1.0') == 0
    assert 'Tag v1.0 deleted' in capsys.readouterr().out

def test_delete_tag_nonexistent(temp_repo: Repository, capsys: CaptureFixture[str]):
    """Tests 'delete_tag' for a tag that doesn't exist."""
    assert cli_commands.delete_tag(working_dir_path=temp_repo.working_dir, tag_name='v1.0') == -1
    assert "Tag 'v1.0' Not In 'tags' Directory" in capsys.readouterr().err

def test_delete_tag_no_repo(temp_repo_dir: Path, capsys: CaptureFixture[str]):
    """Tests 'delete_tag' on a non-existent repository."""
    assert cli_commands.delete_tag(working_dir_path=temp_repo_dir, tag_name='v1.0') == -1
    assert 'No repository found' in capsys.readouterr().err

def test_delete_tag_missing_name(temp_repo: Repository, capsys: CaptureFixture[str]):
    """Tests 'delete_tag' with a missing tag name."""
    assert cli_commands.delete_tag(working_dir_path=temp_repo.working_dir, tag_name=None) == -1
    assert 'Tag name is required' in capsys.readouterr().err