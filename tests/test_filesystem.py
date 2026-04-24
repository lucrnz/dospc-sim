"""Tests for filesystem abstraction."""

import os
import shutil
import tempfile
from pathlib import Path

import pytest

from dospc_sim.filesystem import UserFilesystem


class TestUserFilesystem:
    """Test cases for UserFilesystem."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests."""
        temp_path = tempfile.mkdtemp()
        yield Path(temp_path)
        shutil.rmtree(temp_path, ignore_errors=True)

    @pytest.fixture
    def filesystem(self, temp_dir):
        """Create a UserFilesystem with temp directory."""
        user_dir = temp_dir / 'testuser'
        user_dir.mkdir()
        return UserFilesystem(str(user_dir), 'testuser')

    def test_initial_state(self, filesystem):
        """Test initial filesystem state."""
        assert filesystem.username == 'testuser'
        assert filesystem.drive_letter == 'C'
        assert filesystem.get_current_path() == 'C:\\'

    def test_make_directory(self, filesystem):
        """Test creating directories."""
        filesystem.make_directory('testdir')
        assert os.path.exists(os.path.join(filesystem.home_dir, 'testdir'))

    def test_make_directory_nested(self, filesystem):
        """Test creating nested directories."""
        filesystem.make_directory('parent/child')
        assert os.path.exists(os.path.join(filesystem.home_dir, 'parent', 'child'))

    def test_list_directory(self, filesystem):
        """Test listing directory contents."""
        # Create some files and directories
        os.makedirs(os.path.join(filesystem.home_dir, 'subdir'))
        with open(os.path.join(filesystem.home_dir, 'file1.txt'), 'w') as f:
            f.write('content')

        entries = filesystem.list_directory()

        assert len(entries) == 2
        names = [e.name for e in entries]
        assert 'subdir' in names
        assert 'file1.txt' in names

    def test_list_directory_sorted(self, filesystem):
        """Test that directory listing is sorted."""
        # Create entries in non-alphabetical order
        os.makedirs(os.path.join(filesystem.home_dir, 'zebra'))
        os.makedirs(os.path.join(filesystem.home_dir, 'alpha'))
        with open(os.path.join(filesystem.home_dir, 'file_b.txt'), 'w') as f:
            f.write('content')
        with open(os.path.join(filesystem.home_dir, 'file_a.txt'), 'w') as f:
            f.write('content')

        entries = filesystem.list_directory()
        names = [e.name for e in entries]

        # Directories first, then files, all sorted alphabetically
        assert names == ['alpha', 'zebra', 'file_a.txt', 'file_b.txt']

    def test_change_directory(self, filesystem):
        """Test changing directories."""
        os.makedirs(os.path.join(filesystem.home_dir, 'subdir'))

        result = filesystem.change_directory('subdir')
        assert result == 'C:\\subdir'
        assert filesystem.get_current_path() == 'C:\\subdir'

    def test_change_directory_parent(self, filesystem):
        """Test changing to parent directory."""
        os.makedirs(os.path.join(filesystem.home_dir, 'subdir'))
        filesystem.change_directory('subdir')

        result = filesystem.change_directory('..')
        assert result == 'C:\\'

    def test_change_directory_not_found(self, filesystem):
        """Test changing to non-existent directory."""
        with pytest.raises(FileNotFoundError):
            filesystem.change_directory('nonexistent')

    def test_write_and_read_file(self, filesystem):
        """Test writing and reading files."""
        content = 'Hello, World!'
        filesystem.write_file('test.txt', content)

        result = filesystem.read_file('test.txt')
        assert result == content

    def test_read_file_not_found(self, filesystem):
        """Test reading non-existent file."""
        with pytest.raises(FileNotFoundError):
            filesystem.read_file('nonexistent.txt')

    def test_delete_file(self, filesystem):
        """Test deleting files."""
        filesystem.write_file('delete_me.txt', 'content')
        assert filesystem.file_exists('delete_me.txt')

        filesystem.delete_file('delete_me.txt')
        assert not filesystem.file_exists('delete_me.txt')

    def test_delete_file_not_found(self, filesystem):
        """Test deleting non-existent file."""
        with pytest.raises(FileNotFoundError):
            filesystem.delete_file('nonexistent.txt')

    def test_remove_directory(self, filesystem):
        """Test removing empty directory."""
        filesystem.make_directory('emptydir')
        assert filesystem.dir_exists('emptydir')

        filesystem.remove_directory('emptydir')
        assert not filesystem.dir_exists('emptydir')

    def test_remove_directory_not_empty(self, filesystem):
        """Test removing non-empty directory."""
        filesystem.make_directory('parent')
        filesystem.write_file('parent/file.txt', 'content')

        with pytest.raises(OSError, match='not empty'):
            filesystem.remove_directory('parent')

    def test_remove_directory_recursive(self, filesystem):
        """Test recursive directory removal."""
        filesystem.make_directory('parent/child')
        filesystem.write_file('parent/file1.txt', 'content')
        filesystem.write_file('parent/child/file2.txt', 'content')

        filesystem.remove_directory_recursive('parent')
        assert not filesystem.dir_exists('parent')

    def test_copy_file(self, filesystem):
        """Test copying files."""
        filesystem.write_file('source.txt', 'content to copy')

        filesystem.copy_file('source.txt', 'dest.txt')

        assert filesystem.file_exists('dest.txt')
        assert filesystem.read_file('dest.txt') == 'content to copy'

    def test_move_file(self, filesystem):
        """Test moving files."""
        filesystem.make_directory('dest_dir')
        filesystem.write_file('source.txt', 'content')

        filesystem.move_file('source.txt', 'dest_dir')

        assert not filesystem.file_exists('source.txt')
        assert filesystem.file_exists('dest_dir/source.txt')

    def test_rename(self, filesystem):
        """Test renaming files."""
        filesystem.write_file('oldname.txt', 'content')

        filesystem.rename('oldname.txt', 'newname.txt')

        assert not filesystem.file_exists('oldname.txt')
        assert filesystem.file_exists('newname.txt')

    def test_file_exists(self, filesystem):
        """Test file existence check."""
        assert not filesystem.file_exists('test.txt')

        filesystem.write_file('test.txt', 'content')
        assert filesystem.file_exists('test.txt')

    def test_dir_exists(self, filesystem):
        """Test directory existence check."""
        assert not filesystem.dir_exists('testdir')

        filesystem.make_directory('testdir')
        assert filesystem.dir_exists('testdir')

    def test_security_escape_attempt(self, filesystem):
        """Test that escaping home directory is prevented."""
        # When at root of home, ".." should resolve to home itself
        # because we can't go above home directory

        # First, create a subdirectory and cd into it
        filesystem.make_directory('subdir')
        filesystem.change_directory('subdir')

        # Now ".." should work and go back to home
        result = filesystem._resolve_path('..')
        assert result == filesystem.home_dir

        # But trying to go above home should raise PermissionError
        # when we're already at home and try to go up
        filesystem.change_directory('..')  # Back at home

        with pytest.raises(PermissionError):
            filesystem._resolve_path('..')

        # Absolute paths should be relative to home
        result = filesystem._resolve_path('/test.txt')
        assert result == filesystem.home_dir / 'test.txt'

        # But trying to access files outside home should fail
        assert not filesystem.file_exists('/etc/passwd')

    def test_security_absolute_path(self, filesystem):
        """Test that absolute paths are contained."""
        # Absolute paths should be relative to home
        result = filesystem._resolve_path('/testfile.txt')
        assert result == filesystem.home_dir / 'testfile.txt'

    def test_drive_letter_mapping(self, filesystem):
        """Test C: drive letter mapping."""
        result = filesystem._resolve_path('C:')
        assert result == filesystem.home_dir

        result = filesystem._resolve_path('C:\\test.txt')
        assert result == filesystem.home_dir / 'test.txt'

    def test_get_free_space(self, filesystem):
        """Test getting free space."""
        free_space = filesystem.get_free_space()
        assert free_space > 0

    def test_get_total_size(self, filesystem):
        """Test getting total size."""
        filesystem.write_file('file1.txt', 'a' * 100)
        filesystem.write_file('file2.txt', 'b' * 200)

        total_size = filesystem.get_total_size()
        assert total_size >= 300

    def test_file_info(self, filesystem):
        """Test file information."""
        filesystem.write_file('test.txt', 'content')

        entries = filesystem.list_directory()
        file_entry = next(e for e in entries if e.name == 'test.txt')

        assert file_entry.name == 'test.txt'
        assert file_entry.size == len('content')
        assert file_entry.is_dir is False
        assert ' ' in file_entry.attributes  # Not a directory

    # ==================== Case-insensitive path tests ====================

    def test_read_file_case_insensitive(self, filesystem):
        """Test reading a file with mismatched case."""
        filesystem.write_file('hello.txt', 'world')
        assert filesystem.read_file('HELLO.TXT') == 'world'
        assert filesystem.read_file('Hello.Txt') == 'world'

    def test_delete_file_case_insensitive(self, filesystem):
        """Test deleting a file with mismatched case."""
        filesystem.write_file('remove_me.txt', 'data')
        filesystem.delete_file('REMOVE_ME.TXT')
        assert not filesystem.file_exists('remove_me.txt')

    def test_copy_file_case_insensitive(self, filesystem):
        """Test copying a file with mismatched case on source."""
        filesystem.write_file('original.txt', 'content')
        filesystem.copy_file('ORIGINAL.TXT', 'copy.txt')
        assert filesystem.read_file('copy.txt') == 'content'

    def test_move_file_case_insensitive(self, filesystem):
        """Test moving a file with mismatched case on source."""
        filesystem.write_file('moveme.txt', 'data')
        filesystem.move_file('MOVEME.TXT', 'moved.txt')
        assert filesystem.read_file('moved.txt') == 'data'
        assert not filesystem.file_exists('moveme.txt')

    def test_rename_case_insensitive(self, filesystem):
        """Test renaming a file with mismatched case on source."""
        filesystem.write_file('oldname.txt', 'data')
        filesystem.rename('OLDNAME.TXT', 'newname.txt')
        assert filesystem.read_file('newname.txt') == 'data'
        assert not filesystem.file_exists('oldname.txt')

    def test_change_directory_case_insensitive(self, filesystem):
        """Test changing directory with mismatched case."""
        filesystem.make_directory('MyFolder')
        filesystem.change_directory('myfolder')
        path = filesystem.get_current_path()
        assert 'myfolder' in path.lower()

    def test_remove_directory_case_insensitive(self, filesystem):
        """Test removing a directory with mismatched case."""
        filesystem.make_directory('RemoveDir')
        filesystem.remove_directory('removedir')
        assert not filesystem.dir_exists('RemoveDir')

    def test_remove_directory_recursive_case_insensitive(self, filesystem):
        """Test recursive directory removal with mismatched case."""
        filesystem.make_directory('DeepDir')
        filesystem.write_file('DeepDir/file.txt', 'data')
        filesystem.remove_directory_recursive('deepdir')
        assert not filesystem.dir_exists('DeepDir')

    def test_case_insensitive_multi_segment_path(self, filesystem):
        """Test case-insensitive matching across multiple path segments."""
        filesystem.make_directory('MyDir')
        filesystem.write_file('MyDir/test.txt', 'hello')
        assert filesystem.read_file('mydir/TEST.TXT') == 'hello'

    def test_write_file_uses_case_insensitive_parent_resolution(self, filesystem):
        """Test writing under an existing mixed-case parent directory."""
        filesystem.make_directory('MyDir')
        filesystem.write_file('mydir/new.txt', 'hello')
        assert filesystem.read_file('MyDir/new.txt') == 'hello'
        assert filesystem.read_file('mydir/new.txt') == 'hello'

    def test_case_insensitive_security_preserved(self, filesystem):
        """Case-insensitive resolution must not allow escaping home dir."""
        filesystem.make_directory('subdir')
        filesystem.change_directory('subdir')
        filesystem.change_directory('..')
        with pytest.raises(PermissionError):
            filesystem._resolve_path('..')
