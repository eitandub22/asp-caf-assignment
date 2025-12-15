from pathlib import Path
from libcaf.repository import Repository
from pytest import CaptureFixture
from caf import cli_commands


def test_status_command_when_no_changes(temp_repo: Repository, capsys: CaptureFixture[str]) -> None:
    cli_commands.commit(working_dir_path=temp_repo.working_dir, author='Test Author', message='Initial commit')
    capsys.readouterr()

    result = cli_commands.status(working_dir_path=temp_repo.working_dir)

    assert result == 0
    output = capsys.readouterr().out
    assert 'nothing to commit, working tree clean.' in output

def test_status_command_when_added_file(temp_repo: Repository, capsys: CaptureFixture[str]) -> None:
    temp_repo.commit_working_dir('Tester', 'Initial commit')
    capsys.readouterr()

    file1 = temp_repo.working_dir / 'file.txt'
    file1.write_text('Sample content')

    result = cli_commands.status(working_dir_path=temp_repo.working_dir)

    assert result == 0
    output = capsys.readouterr().out
    assert 'Added:' in output
    assert f'file.txt' in output

def test_status_command_when_modified_file(temp_repo: Repository, capsys: CaptureFixture[str]) -> None:
    file1 = temp_repo.working_dir / 'file.txt'
    file1.write_text('Old content')

    temp_repo.commit_working_dir('Tester', 'Original commit')
    capsys.readouterr()

    file1.write_text('New content')

    result = cli_commands.status(working_dir_path=temp_repo.working_dir)

    assert result == 0
    output = capsys.readouterr().out
    assert f'Modified: {file1.name}' in output

def test_status_command_when_removed_file(temp_repo: Repository, capsys: CaptureFixture[str]) -> None:
    file1 = temp_repo.working_dir / 'file.txt'
    file1.write_text('Content to be deleted')

    temp_repo.commit_working_dir('Tester', 'Initial commit')
    capsys.readouterr()

    file1.unlink()

    result = cli_commands.status(working_dir_path=temp_repo.working_dir)

    assert result == 0
    output = capsys.readouterr().out
    assert 'Removed:' in output
    assert f'file.txt' in output

def test_status_command_with_multiple_changes(temp_repo: Repository, capsys: CaptureFixture[str]) -> None:
    file1 = temp_repo.working_dir / 'file1.txt'
    file2 = temp_repo.working_dir / 'file2.txt'
    file1.write_text('Initial content for file 1')
    file2.write_text('Initial content for file 2')

    temp_repo.commit_working_dir('Tester', 'Initial commit')
    capsys.readouterr()

    # Modify file1, remove file2, and add file3
    file1.write_text('Modified content for file 1')
    file2.unlink()
    file3 = temp_repo.working_dir / 'file3.txt'
    file3.write_text('Content for new file 3')

    result = cli_commands.status(working_dir_path=temp_repo.working_dir)

    assert result == 0
    output = capsys.readouterr().out
    assert f'Modified: {file1.name}' in output
    assert 'Removed:' in output and f'file2.txt' in output
    assert 'Added:' in output and f'file3.txt' in output
