from pathlib import Path

from libcaf.repository import Repository
from pytest import CaptureFixture

from caf import cli_commands


def test_checkout_branch(temp_repo: Repository, capsys: CaptureFixture[str]) -> None:
    file_path = temp_repo.working_dir / 'test_file.txt'
    file_path.write_text('Version 1')

    cli_commands.commit(working_dir_path=temp_repo.working_dir,
                        author='Author', message='Commit 1')

    temp_repo.add_branch('feature')

    file_path.write_text('Version 2')
    cli_commands.commit(working_dir_path=temp_repo.working_dir,
                        author='Author', message='Commit 2')

    assert file_path.read_text() == 'Version 2'

    capsys.readouterr()

    exit_code = cli_commands.checkout(working_dir_path=temp_repo.working_dir, ref='feature')

    assert exit_code == 0

    out = capsys.readouterr().out
    assert "Switched to branch 'feature'" in out


def test_checkout_commit_detached(temp_repo: Repository, capsys: CaptureFixture[str]) -> None:
    file_path = temp_repo.working_dir / 'file.txt'
    file_path.write_text('Content V1')

    temp_repo.commit_working_dir('Author', 'Commit 1')
    commit_1_hash = temp_repo.head_commit()

    file_path.write_text('Content V2')
    temp_repo.commit_working_dir('Author', 'Commit 2')

    capsys.readouterr()

    exit_code = cli_commands.checkout(working_dir_path=temp_repo.working_dir, ref=commit_1_hash)

    assert exit_code == 0

    out = capsys.readouterr().out
    assert 'Note: switching to' in out
    assert "You are in 'detached HEAD' state" in out
    assert f'HEAD is now at {commit_1_hash}' in out


def test_checkout_ref_not_found(temp_repo: Repository, capsys: CaptureFixture[str]) -> None:
    (temp_repo.working_dir / 'init').touch()
    cli_commands.commit(working_dir_path=temp_repo.working_dir,
                               author='Author', message='Init')

    capsys.readouterr()

    exit_code = cli_commands.checkout(working_dir_path=temp_repo.working_dir, ref='non-existent-branch')

    assert exit_code == -1

    err = capsys.readouterr().err
    assert 'Cannot resolve reference non-existent-branch' in err


def test_checkout_no_repo(temp_repo_dir: Path, capsys: CaptureFixture[str]) -> None:
    exit_code = cli_commands.checkout(working_dir_path=temp_repo_dir, ref='master')

    assert exit_code == -1

    err = capsys.readouterr().err
    assert 'No repository found' in err


def test_checkout_repo_error(temp_repo: Repository, capsys: CaptureFixture[str]) -> None:
    (temp_repo.working_dir / '.caf' / 'HEAD').unlink()

    exit_code = cli_commands.checkout(working_dir_path=temp_repo.working_dir, ref='master')

    assert exit_code == -1

    err = capsys.readouterr().err
    assert 'Repository error' in err


def test_checkout_fails_on_dirty_state(temp_repo: Repository, capsys: CaptureFixture[str]) -> None:
    file_path = temp_repo.working_dir / 'test.txt'
    file_path.write_text('Version 1')
    cli_commands.commit(working_dir_path=temp_repo.working_dir, author='Me', message='Commit 1')

    temp_repo.add_branch('feature')

    file_path.write_text('Unsaved Changes')

    capsys.readouterr()

    exit_code = cli_commands.checkout(working_dir_path=temp_repo.working_dir, ref='feature')

    assert exit_code == -1

    err = capsys.readouterr().err
    assert "working directory has uncommitted changes." in err


def test_checkout_tag(temp_repo: Repository, capsys: CaptureFixture[str]) -> None:
    file_path = temp_repo.working_dir / 'version.txt'
    file_path.write_text('v1.0 code')
    cli_commands.commit(working_dir_path=temp_repo.working_dir, author='Me', message='Release v1.0')

    commit_hash = temp_repo.head_commit()

    temp_repo.create_tag(tag_name='v1.0', commit_hash=commit_hash, author='Me', message='Version 1.0')

    capsys.readouterr()

    exit_code = cli_commands.checkout(working_dir_path=temp_repo.working_dir, ref='v1.0')

    assert exit_code == 0

    out = capsys.readouterr().out
    assert "Note: switching to 'v1.0'" in out
    assert "You are in 'detached HEAD' state" in out
    assert f'HEAD is now at {commit_hash}' in out


def test_checkout_branch_same_commit(temp_repo: Repository, capsys: CaptureFixture[str]) -> None:
    (temp_repo.working_dir / 'file.txt').write_text('A')
    cli_commands.commit(working_dir_path=temp_repo.working_dir, author='Me', message='Commit A')

    temp_repo.add_branch('dev')

    capsys.readouterr()

    exit_code = cli_commands.checkout(working_dir_path=temp_repo.working_dir, ref='dev')

    assert exit_code == 0

    out = capsys.readouterr().out
    assert "Switched to branch 'dev'" in out
