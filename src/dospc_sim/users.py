"""User management system for DosPC Sim SSH server."""

import hashlib
import json
import secrets
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

DATA_DIR = Path('data')
USERS_FILE = DATA_DIR / 'users.json'
USERS_DIR = DATA_DIR / 'users'


@dataclass
class User:
    """Represents a user in the system."""

    username: str
    password_hash: str
    salt: str
    home_dir: str
    created_at: str
    last_login: str | None = None
    is_active: bool = True


class UserManagerStorage:
    """Persistence and filesystem scaffolding for user accounts."""

    def __init__(
        self,
        data_dir: Path,
        users_file: Path | None = None,
        users_dir: Path | None = None,
    ):
        self.data_dir = data_dir
        self.users_file = (
            users_file if users_file is not None else data_dir / 'users.json'
        )
        self.users_dir = users_dir if users_dir is not None else data_dir / 'users'

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.users_dir.mkdir(parents=True, exist_ok=True)

    def load_users(self) -> dict[str, User]:
        if not self.users_file.exists():
            return {}
        try:
            with open(self.users_file, encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, TypeError):
            return {}
        return {username: User(**user_data) for username, user_data in data.items()}

    def save_users(self, users: dict[str, User]) -> None:
        data = {username: asdict(user) for username, user in users.items()}
        with open(self.users_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def user_home_dir(self, username: str) -> Path:
        return self.users_dir / username

    def remove_home_dir(self, home_dir: str) -> None:
        target = Path(home_dir)
        if target.exists():
            shutil.rmtree(target)

    def seed_default_user_home(self, home_dir: Path) -> None:
        dirs = ['DOCS', 'GAMES', 'TEMP', 'CONFIG']
        for d in dirs:
            (home_dir / d).mkdir(parents=True, exist_ok=True)

        welcome_path = home_dir / 'WELCOME.TXT'
        with open(welcome_path, 'w', encoding='utf-8') as f:
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


class UserManager:
    """Manages user accounts and authentication."""

    def __init__(self, data_dir: Path = DATA_DIR):
        users_file = USERS_FILE if data_dir == DATA_DIR else data_dir / 'users.json'
        users_dir = USERS_DIR if data_dir == DATA_DIR else data_dir / 'users'
        self.storage = UserManagerStorage(data_dir, users_file, users_dir)
        self._users: dict[str, User] = {}
        self.storage.ensure_directories()
        self._users = self.storage.load_users()

    def _hash_password(self, password: str, salt: str | None = None) -> tuple:
        """Hash a password with salt."""
        if salt is None:
            salt = secrets.token_hex(16)
        # Use PBKDF2 for secure password hashing
        hash_value = hashlib.pbkdf2_hmac(
            'sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000
        ).hex()
        return hash_value, salt

    def create_user(self, username: str, password: str) -> User:
        """Create a new user with home directory."""
        if not username or not password:
            raise ValueError('Username and password are required')

        if username in self._users:
            raise ValueError(f"User '{username}' already exists")

        # Validate username (alphanumeric and underscore only)
        if not username.replace('_', '').isalnum():
            raise ValueError('Username must be alphanumeric (underscores allowed)')

        home_dir_path = self.storage.user_home_dir(username)
        home_dir_path.mkdir(parents=True, exist_ok=True)

        self.storage.seed_default_user_home(home_dir_path)

        # Hash password
        password_hash, salt = self._hash_password(password)

        user = User(
            username=username,
            password_hash=password_hash,
            salt=salt,
            home_dir=str(home_dir_path),
            created_at=datetime.now().isoformat(),
        )

        self._users[username] = user
        self.storage.save_users(self._users)

        return user

    def authenticate(self, username: str, password: str) -> User | None:
        """Authenticate a user."""
        if username not in self._users:
            return None

        user = self._users[username]
        if not user.is_active:
            return None

        password_hash, _ = self._hash_password(password, user.salt)
        if password_hash == user.password_hash:
            user.last_login = datetime.now().isoformat()
            self.storage.save_users(self._users)
            return user

        return None

    def get_user(self, username: str) -> User | None:
        """Get a user by username."""
        return self._users.get(username)

    def list_users(self) -> list[User]:
        """List all users."""
        return list(self._users.values())

    def delete_user(self, username: str, remove_data: bool = True) -> bool:
        """Delete a user and optionally their home directory."""
        if username not in self._users:
            return False

        user = self._users[username]

        if remove_data:
            self.storage.remove_home_dir(user.home_dir)

        del self._users[username]
        self.storage.save_users(self._users)
        return True

    def change_password(self, username: str, new_password: str) -> bool:
        """Change a user's password."""
        if username not in self._users:
            return False

        user = self._users[username]
        password_hash, salt = self._hash_password(new_password)
        user.password_hash = password_hash
        user.salt = salt
        self.storage.save_users(self._users)
        return True

    def user_exists(self, username: str) -> bool:
        """Check if a user exists."""
        return username in self._users
