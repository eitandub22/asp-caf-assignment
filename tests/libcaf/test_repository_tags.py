import pytest
from libcaf.repository import Repository, HashRef
from libcaf.constants import HASH_LENGTH
from libcaf.exceptions import TagNotFound, TagExistsError, UnknownHashError, RepositoryError
from datetime import datetime

def test_init_creates_tags_dir(temp_repo: Repository):
    """Tests that the 'tags' directory is created by repo.init()."""
    assert temp_repo.tags() == []

def test_create_tag_success(temp_repo: Repository, commit_hash: HashRef):
    """Tests the happy path for creating a tag."""
    temp_repo.create_tag('v1.0', commit_hash, 'Some author', 'Some message', 'Some date')

    tags_dict = {tag.name: tag for tag in temp_repo.tags()}
    assert len(tags_dict) == 1
    assert tags_dict['v1.0'].name == 'v1.0'
    assert tags_dict['v1.0'].commit_hash == commit_hash
    assert tags_dict['v1.0'].author == 'Some author'
    assert tags_dict['v1.0'].message == 'Some message'
    assert tags_dict['v1.0'].date == 'Some date'


def test_create_tag_already_exists(temp_repo: Repository, commit_hash: HashRef):
    """Tests that creating a duplicate tag raises an error."""
    temp_repo.create_tag('v1.0', commit_hash, 'Some author', 'Some message', 'Some date')
    
    with pytest.raises(TagExistsError):
        temp_repo.create_tag('v1.0', commit_hash, 'Some author', 'Some message', 'Some date')

def test_create_tag_empty_name(temp_repo: Repository, commit_hash: HashRef):
    """Tests that creating a tag with an empty name fails."""
    with pytest.raises(ValueError, match="Tag name is required"):
        temp_repo.create_tag('', commit_hash, 'Some author', 'Some message', 'Some date')

def test_create_tag_invalid_hash(temp_repo: Repository):
    """Tests creating a tag with an invalid hash format."""
    with pytest.raises(ValueError, match="Invalid commit hash"):
        temp_repo.create_tag('v1.0', 'not-a-hash', 'Some author', 'Some message', 'Some date')

def test_create_tag_no_author(temp_repo: Repository, commit_hash: HashRef):
    """Tests creating a tag with no author."""
    with pytest.raises(ValueError, match="Tag author is required"):
        temp_repo.create_tag('v1.0', commit_hash, None, 'Some message', 'Some date')

def test_create_tag_no_message(temp_repo: Repository, commit_hash: HashRef):
    """Tests creating a tag with no message."""
    with pytest.raises(ValueError, match="Tag message is required"):
        temp_repo.create_tag('v1.0', commit_hash, 'Some author', None, 'Some date')

def test_create_tag_no_date(temp_repo: Repository, commit_hash: HashRef):
    """Tests creating a tag with no date."""
    with pytest.raises(ValueError, match="Tag date is required"):
        temp_repo.create_tag('v1.0', commit_hash, 'Some author', 'Some message', None)

def test_create_tag_nonexistent_object(temp_repo: Repository):
    """Tests creating a tag pointing to an object that doesn't exist."""
    non_existent_hash = 'a' * HASH_LENGTH
    with pytest.raises(UnknownHashError, match="Unknown commit hash"):
        temp_repo.create_tag('v1.0', non_existent_hash, 'Some author', 'Some message', 'Some date')

def test_create_tag_points_to_tree(temp_repo: Repository):
    """Tests that create_tag fails if the hash points to a Tree, not a Commit."""
    tree_hash = temp_repo.save_dir(temp_repo.working_dir)
    
    with pytest.raises(RepositoryError):
        temp_repo.create_tag('v1.0', tree_hash, 'Some author', 'Some message', 'Some date')

def test_list_tags(temp_repo: Repository, commit_hash: HashRef):
    """Tests listing multiple tags."""
    temp_repo.create_tag('v1.0', commit_hash, 'Some author', 'Some message', 'Some date')
    temp_repo.create_tag('v1.1-beta', commit_hash, 'Some author', 'Some message', 'Some date')
    
    tags = temp_repo.tags()
    tags_dict = {tag.name: tag for tag in tags}

    assert len(tags_dict) == 2
    assert set(tags_dict.keys()) == {'v1.0', 'v1.1-beta'}
    
    assert tags_dict['v1.0'].name == 'v1.0'
    assert tags_dict['v1.0'].commit_hash == commit_hash
    assert tags_dict['v1.0'].author == 'Some author'
    assert tags_dict['v1.0'].message == 'Some message'
    assert tags_dict['v1.0'].date == 'Some date'

    assert tags_dict['v1.1-beta'].name == 'v1.1-beta'
    assert tags_dict['v1.1-beta'].commit_hash == commit_hash
    assert tags_dict['v1.1-beta'].author == 'Some author'
    assert tags_dict['v1.1-beta'].message == 'Some message'
    assert tags_dict['v1.1-beta'].date == 'Some date'

def test_list_tags_empty(temp_repo: Repository):
    """Tests listing tags when none exist."""
    assert temp_repo.tags() == []

def test_delete_tag_success(temp_repo: Repository, commit_hash: HashRef):
    """Tests the happy path for deleting a tag."""
    temp_repo.create_tag('v1.0', commit_hash, 'Some author', 'Some message', 'Some date')
    tag_path = temp_repo.tags_dir() / 'v1.0'
    assert tag_path.exists()
    
    temp_repo.delete_tag('v1.0')

    tags_dict = {tag.name: tag for tag in temp_repo.tags()}
    assert 'v1.0' not in tags_dict

def test_delete_tag_nonexistent(temp_repo: Repository):
    """Tests that deleting a non-existent tag raises the correct error."""
    with pytest.raises(TagNotFound):
        temp_repo.delete_tag('v1.0')

def test_delete_tag_empty_name(temp_repo: Repository):
    """Tests that deleting a tag with an empty name fails."""
    with pytest.raises(ValueError, match="Tag name is required"):
        temp_repo.delete_tag('')