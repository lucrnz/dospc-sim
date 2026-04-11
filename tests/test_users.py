"""Tests for user management system."""

import os
import shutil
import tempfile
from pathlib import Path

import pytest

from dospc_sim.users import UserManager


class TestUserManager:
    """Test cases for UserManager."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests."""
        temp_path = tempfile.mkdtemp()
        yield Path(temp_path)
        shutil.rmtree(temp_path, ignore_errors=True)

    @pytest.fixture
    def user_manager(self, temp_dir):
        """Create a UserManager with temp directory."""
        return UserManager(data_dir=temp_dir)

    def test_create_user(self, user_manager):
        """Test creating a new user."""
        user = user_manager.create_user("testuser", "password123")

        assert user.username == "testuser"
        assert user.is_active is True
        assert user.home_dir is not None
        assert os.path.exists(user.home_dir)

    def test_create_user_duplicate(self, user_manager):
        """Test creating a user with duplicate username."""
        user_manager.create_user("testuser", "password123")

        with pytest.raises(ValueError, match="already exists"):
            user_manager.create_user("testuser", "password456")

    def test_create_user_invalid_chars(self, user_manager):
        """Test creating a user with invalid characters."""
        with pytest.raises(ValueError, match="alphanumeric"):
            user_manager.create_user("test-user!", "password123")

    def test_create_user_empty_values(self, user_manager):
        """Test creating a user with empty values."""
        with pytest.raises(ValueError, match="required"):
            user_manager.create_user("", "password123")

        with pytest.raises(ValueError, match="required"):
            user_manager.create_user("testuser", "")

    def test_authenticate_success(self, user_manager):
        """Test successful authentication."""
        user_manager.create_user("testuser", "password123")

        result = user_manager.authenticate("testuser", "password123")
        assert result is not None
        assert result.username == "testuser"
        assert result.last_login is not None

    def test_authenticate_wrong_password(self, user_manager):
        """Test authentication with wrong password."""
        user_manager.create_user("testuser", "password123")

        result = user_manager.authenticate("testuser", "wrongpassword")
        assert result is None

    def test_authenticate_nonexistent_user(self, user_manager):
        """Test authentication for non-existent user."""
        result = user_manager.authenticate("nonexistent", "password123")
        assert result is None

    def test_get_user(self, user_manager):
        """Test getting a user by username."""
        user_manager.create_user("testuser", "password123")

        user = user_manager.get_user("testuser")
        assert user is not None
        assert user.username == "testuser"

    def test_get_user_nonexistent(self, user_manager):
        """Test getting a non-existent user."""
        user = user_manager.get_user("nonexistent")
        assert user is None

    def test_list_users(self, user_manager):
        """Test listing all users."""
        user_manager.create_user("user1", "password1")
        user_manager.create_user("user2", "password2")
        user_manager.create_user("user3", "password3")

        users = user_manager.list_users()
        assert len(users) == 3
        usernames = [u.username for u in users]
        assert "user1" in usernames
        assert "user2" in usernames
        assert "user3" in usernames

    def test_delete_user(self, user_manager):
        """Test deleting a user."""
        user = user_manager.create_user("testuser", "password123")
        home_dir = user.home_dir

        result = user_manager.delete_user("testuser")
        assert result is True
        assert not os.path.exists(home_dir)
        assert user_manager.get_user("testuser") is None

    def test_delete_user_nonexistent(self, user_manager):
        """Test deleting a non-existent user."""
        result = user_manager.delete_user("nonexistent")
        assert result is False

    def test_change_password(self, user_manager):
        """Test changing a user's password."""
        user_manager.create_user("testuser", "oldpassword")

        result = user_manager.change_password("testuser", "newpassword")
        assert result is True

        # Old password should fail
        assert user_manager.authenticate("testuser", "oldpassword") is None

        # New password should succeed
        assert user_manager.authenticate("testuser", "newpassword") is not None

    def test_change_password_nonexistent(self, user_manager):
        """Test changing password for non-existent user."""
        result = user_manager.change_password("nonexistent", "newpassword")
        assert result is False

    def test_user_exists(self, user_manager):
        """Test checking if user exists."""
        user_manager.create_user("testuser", "password123")

        assert user_manager.user_exists("testuser") is True
        assert user_manager.user_exists("nonexistent") is False

    def test_default_directory_structure(self, user_manager):
        """Test that default directories are created."""
        user = user_manager.create_user("testuser", "password123")

        # Check default directories
        assert os.path.exists(os.path.join(user.home_dir, "DOCS"))
        assert os.path.exists(os.path.join(user.home_dir, "GAMES"))
        assert os.path.exists(os.path.join(user.home_dir, "TEMP"))
        assert os.path.exists(os.path.join(user.home_dir, "CONFIG"))

        # Check welcome file
        assert os.path.exists(os.path.join(user.home_dir, "WELCOME.TXT"))

    def test_persistence(self, temp_dir):
        """Test that users are persisted to disk."""
        # Create user with first manager
        um1 = UserManager(data_dir=temp_dir)
        um1.create_user("testuser", "password123")

        # Create new manager instance pointing to same directory
        um2 = UserManager(data_dir=temp_dir)

        # User should exist in new instance
        assert um2.user_exists("testuser") is True
        user = um2.get_user("testuser")
        assert user.username == "testuser"
