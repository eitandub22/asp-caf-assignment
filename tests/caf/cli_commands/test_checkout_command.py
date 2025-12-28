from pathlib import Path

from libcaf.repository import Repository
from pytest import CaptureFixture

from caf import cli_commands


def test_checkout_branch(temp_repo: Repository) -> None:
    file_path = temp_repo.working_dir / 'test_file.txt'
    file_path.write_text('Version 1')

    cli_commands.commit(working_dir_path=temp_repo.working_dir,
                        author='Author', message='Commit 1')

    temp_repo.add_branch('feature')

    file_path.write_text('Version 2')
    cli_commands.commit(working_dir_path=temp_repo.working_dir,
                        author='Author', message='Commit 2')

    assert file_path.read_text() == 'Version 2'

    exit_code = cli_commands.checkout(working_dir_path=temp_repo.working_dir, ref='feature')

    assert exit_code == 0

    assert file_path.read_text() == 'Version 1'

    head_content = (temp_repo.head_file()).read_text().strip()
    assert head_content == 'ref: heads/feature'


def test_checkout_commit_detached(temp_repo: Repository) -> None:
    file_path = temp_repo.working_dir / 'file.txt'
    file_path.write_text('Content V1')

    temp_repo.commit_working_dir('Author', 'Commit 1')
    commit_1_hash = temp_repo.head_commit()

    file_path.write_text('Content V2')
    temp_repo.commit_working_dir('Author', 'Commit 2')

    exit_code = cli_commands.checkout(working_dir_path=temp_repo.working_dir, ref=commit_1_hash)

    assert exit_code == 0

    assert file_path.read_text() == 'Content V1'

    head_content = (temp_repo.working_dir / '.caf' / 'HEAD').read_text().strip()
    assert head_content == commit_1_hash


def test_checkout_ref_not_found(temp_repo: Repository) -> None:
    (temp_repo.working_dir / 'init').touch()
    cli_commands.commit(working_dir_path=temp_repo.working_dir,
                               author='Author', message='Init')

    exit_code = cli_commands.checkout(working_dir_path=temp_repo.working_dir, ref='non-existent-branch')

    assert exit_code == -1


def test_checkout_no_repo(temp_repo_dir: Path) -> None:
    exit_code = cli_commands.checkout(working_dir_path=temp_repo_dir, ref='master')

    assert exit_code == -1


def test_checkout_repo_error(temp_repo: Repository) -> None:
    (temp_repo.working_dir / '.caf' / 'HEAD').unlink()

    exit_code = cli_commands.checkout(working_dir_path=temp_repo.working_dir, ref='master')

    assert exit_code == -1

def test_checkout_fails_on_dirty_state(temp_repo: Repository) -> None:
    file_path = temp_repo.working_dir / 'test.txt'
    file_path.write_text('Version 1')
    cli_commands.commit(working_dir_path=temp_repo.working_dir, author='Me', message='Commit 1')

    temp_repo.add_branch('feature')

    file_path.write_text('Unsaved Changes')

    exit_code = cli_commands.checkout(working_dir_path=temp_repo.working_dir, ref='feature')

    assert exit_code == -1

def test_checkout_tag(temp_repo: Repository) -> None:
    file_path = temp_repo.working_dir / 'version.txt'
    file_path.write_text('v1.0 code')
    cli_commands.commit(working_dir_path=temp_repo.working_dir, author='Me', message='Release v1.0')

    commit_hash = temp_repo.head_commit()

    temp_repo.create_tag(tag_name='v1.0', commit_hash=commit_hash, author='Me', message='Version 1.0')

    exit_code = cli_commands.checkout(working_dir_path=temp_repo.working_dir, ref='v1.0')

    assert exit_code == 0

    head_content = (temp_repo.head_file()).read_text().strip()
    assert head_content == commit_hash

def test_checkout_branch_same_commit(temp_repo: Repository) -> None:
    (temp_repo.working_dir / 'file.txt').write_text('A')
    cli_commands.commit(working_dir_path=temp_repo.working_dir, author='Me', message='Commit A')

    temp_repo.add_branch('dev')

    exit_code = cli_commands.checkout(working_dir_path=temp_repo.working_dir, ref='dev')
    assert exit_code == 0

    head_content = (temp_repo.head_file()).read_text().strip()

    assert head_content == 'ref: heads/dev'
