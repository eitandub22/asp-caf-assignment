from pathlib import Path
from libcaf.repository import Repository
from pytest import CaptureFixture
from caf import cli_commands


def test_status_command_when_no_changes(temp_repo: Repository, capsys: CaptureFixture[str]) -> None:
    cli_commands.commit(working_dir_path=temp_repo.working_dir, author='Test Author', message='Initial commit')
    result = cli_commands.status(working_dir_path=temp_repo.working_dir)

    assert result == 0
    output = capsys.readouterr().out
    assert 'Working directory is clean.' in output

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
    assert 'Diff:' in output
    assert f'Modified: {file1.name}' in output
