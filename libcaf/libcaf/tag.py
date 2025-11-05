from pathlib import Path
from ref import HashRef, RefError, read_ref, write_ref

from .constants import HASH_CHARSET, HASH_LENGTH

class TagError(Exception):
    """Base class for all tag-related errors."""

class TagNotInTagsDirError(TagError):
    """Exception raised when a tag file is not located in a 'tags' directory."""

    def __init__(self, tag_file: str) -> None:
        super().__init__(f"Tag Not In 'tags' Directory Error: {tag_file}")

class TagAlreadyExistsError(TagError):
    """Exception raised when attempting to create a tag that already exists."""

    def __init__(self, tag_file: str) -> None:
        super().__init__(f"Tag Already Exists Error: {tag_file}")

# A tag is basically just a hash reference
Tag = HashRef

def read_tag(tag_file: Path) -> Tag | None:
    """Read a tag from a file.

    :param tag_file: Path to the tag file
    :return: A Tag object or None if the file is empty
    :raises TagError: If the tag is invalid"""

    # Ensure the tag file is in a 'tags' directory
    if tag_file.parent.name != "tags":
        raise TagNotInTagsDirError(tag_file)

    try:
        # Read the tag as if it were a reference, which it is
        ref = read_ref(tag_file)
    except RefError as e:
        raise TagError(f"Failed to read tag from {tag_file}: {e}") from e
    
def write_tag(tag_file: Path, tag: Tag) -> None:
    """Write a tag to a file.

    :param tag_file: Path to the tag file
    :param tag: Tag to write
    :raises TagError: If the tag is invalid"""
    
    # Ensure the tag file is in a 'tags' directory
    if tag_file.parent.name != "tags":
        raise TagNotInTagsDirError(tag_file)
    
    # Check if the tag already exists, to avoid overwriting
    if tag_file.exists():
        raise TagAlreadyExistsError(tag_file)
    
    try:
        # Write the tag as if it were a reference, which it is
        write_ref(tag_file, tag)
    except RefError as e:
        raise TagError(f"Failed to write tag to {tag_file}: {e}") from e