"""User management system for DosPC Sim SSH server."""

import json
import hashlib
import secrets
import os
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict


DATA_DIR = Path("data")
USERS_FILE = DATA_DIR / "users.json"
USERS_DIR = DATA_DIR / "users"


@dataclass
class User:
    """Represents a user in the system."""

    username: str
    password_hash: str
    salt: str
    home_dir: str
    created_at: str
    last_login: Optional[str] = None
    is_active: bool = True


class UserManager:
    """Manages user accounts and authentication."""

    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = data_dir
        self.users_file = data_dir / "users.json"
        self.users_dir = data_dir / "users"
        self._users: Dict[str, User] = {}
        self._ensure_directories()
        self._load_users()

    def _ensure_directories(self) -> None:
        """Ensure required directories exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.users_dir.mkdir(parents=True, exist_ok=True)

    def _load_users(self) -> None:
        """Load users from JSON file."""
        if self.users_file.exists():
            try:
                with open(self.users_file, "r") as f:
                    data = json.load(f)
                    for username, user_data in data.items():
                        self._users[username] = User(**user_data)
            except (json.JSONDecodeError, TypeError):
                self._users = {}

    def _save_users(self) -> None:
        """Save users to JSON file."""
        data = {username: asdict(user) for username, user in self._users.items()}
        with open(self.users_file, "w") as f:
            json.dump(data, f, indent=2)

    def _hash_password(self, password: str, salt: Optional[str] = None) -> tuple:
        """Hash a password with salt."""
        if salt is None:
            salt = secrets.token_hex(16)
        # Use PBKDF2 for secure password hashing
        hash_value = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000
        ).hex()
        return hash_value, salt

    def create_user(self, username: str, password: str) -> User:
        """Create a new user with home directory."""
        if not username or not password:
            raise ValueError("Username and password are required")

        if username in self._users:
            raise ValueError(f"User '{username}' already exists")

        # Validate username (alphanumeric and underscore only)
        if not username.replace("_", "").isalnum():
            raise ValueError("Username must be alphanumeric (underscores allowed)")

        # Create home directory
        from datetime import datetime

        home_dir = str(self.users_dir / username)
        os.makedirs(home_dir, exist_ok=True)

        # Create default DOS structure
        self._create_default_structure(home_dir)

        # Hash password
        password_hash, salt = self._hash_password(password)

        user = User(
            username=username,
            password_hash=password_hash,
            salt=salt,
            home_dir=home_dir,
            created_at=datetime.now().isoformat(),
        )

        self._users[username] = user
        self._save_users()

        return user

    def _create_default_structure(self, home_dir: str) -> None:
        """Create default DOS directory structure."""
        # Create common DOS directories
        dirs = ["DOCS", "GAMES", "TEMP", "CONFIG"]
        for d in dirs:
            os.makedirs(os.path.join(home_dir, d), exist_ok=True)

        # Create a welcome file
        welcome_path = os.path.join(home_dir, "WELCOME.TXT")
        with open(welcome_path, "w") as f:
            f.write("""Welcome to DosPC Sim DOS Environment
==================================

This is your personal DOS environment.
Type HELP for available commands.

Your directories:
- DOCS:   Documents and text files
- GAMES:  Game files and saves
- TEMP:   Temporary files
- CONFIG: Configuration files

Enjoy your retro computing experience!
""")

    def authenticate(self, username: str, password: str) -> Optional[User]:
        """Authenticate a user."""
        if username not in self._users:
            return None

        user = self._users[username]
        if not user.is_active:
            return None

        password_hash, _ = self._hash_password(password, user.salt)
        if password_hash == user.password_hash:
            from datetime import datetime

            user.last_login = datetime.now().isoformat()
            self._save_users()
            return user

        return None

    def get_user(self, username: str) -> Optional[User]:
        """Get a user by username."""
        return self._users.get(username)

    def list_users(self) -> List[User]:
        """List all users."""
        return list(self._users.values())

    def delete_user(self, username: str, remove_data: bool = True) -> bool:
        """Delete a user and optionally their home directory."""
        if username not in self._users:
            return False

        user = self._users[username]

        if remove_data:
            import shutil

            if os.path.exists(user.home_dir):
                shutil.rmtree(user.home_dir)

        del self._users[username]
        self._save_users()
        return True

    def change_password(self, username: str, new_password: str) -> bool:
        """Change a user's password."""
        if username not in self._users:
            return False

        user = self._users[username]
        password_hash, salt = self._hash_password(new_password)
        user.password_hash = password_hash
        user.salt = salt
        self._save_users()
        return True

    def user_exists(self, username: str) -> bool:
        """Check if a user exists."""
        return username in self._users
