"""Filesystem abstraction for user isolation in DOS environment."""

import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class FileInfo:
    """Information about a file or directory."""

    name: str
    size: int
    is_dir: bool
    modified: datetime
    attributes: str


class UserFilesystem:
    """Provides isolated filesystem access for a user."""

    def __init__(self, home_dir: str, username: str):
        self.home_dir = Path(home_dir).resolve()
        self.username = username
        self.current_dir = self.home_dir
        self._drive_letter = 'C'
        self._ensure_home_exists()

    def _ensure_home_exists(self) -> None:
        """Ensure the home directory exists."""
        self.home_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, path: str) -> Path:
        """Resolve a path relative to current directory, with safety checks."""
        path = path.strip()

        # Handle drive letter (e.g., C: or C:\)
        if len(path) >= 2 and path[1] == ':':
            if path[0].upper() == self._drive_letter:
                # Map C: to home directory
                if len(path) == 2 or path[2:] in ['\\', '/']:
                    return self.home_dir
                path = path[2:].lstrip('\\/')
            else:
                raise PermissionError(f'Access denied to drive {path[0].upper()}:')

        # Handle absolute paths from home
        if path.startswith('\\') or path.startswith('/'):
            path = path[1:]

        # Resolve the path
        if not path or path == '.':
            target = self.current_dir
        elif path == '..':
            target = self.current_dir.parent
        else:
            target = self.current_dir / path

        target = target.resolve()

        # Security check: ensure path is within home directory
        try:
            target.relative_to(self.home_dir)
        except ValueError as exc:
            raise PermissionError('Access denied: path outside home directory') from exc

        # Case-insensitive resolution for DOS compatibility
        target = self._find_case_insensitive(target)

        # Re-verify security after case-insensitive resolution
        try:
            target.relative_to(self.home_dir)
        except ValueError as exc:
            raise PermissionError('Access denied: path outside home directory') from exc

        return target

    def get_current_path(self) -> str:
        """Get current path as DOS-style path."""
        try:
            rel_path = self.current_dir.relative_to(self.home_dir)
            if rel_path == Path('.'):
                return f'{self._drive_letter}:\\'
            return f'{self._drive_letter}:\\{str(rel_path).replace("/", "\\")}'
        except ValueError:
            return f'{self._drive_letter}:\\'

    def list_directory(self, path: str = '.') -> list[FileInfo]:
        """List files in a directory."""
        target = self._resolve_path(path)

        if not target.exists():
            raise FileNotFoundError(f'Directory not found: {path}')

        if not target.is_dir():
            raise NotADirectoryError(f'Not a directory: {path}')

        entries = []
        for item in target.iterdir():
            stat = item.stat()
            modified = datetime.fromtimestamp(stat.st_mtime)

            # DOS-style attributes
            attrs = 'D' if item.is_dir() else ' '
            attrs += 'R' if not os.access(item, os.W_OK) else ' '
            attrs += 'H' if item.name.startswith('.') else ' '

            entries.append(
                FileInfo(
                    name=item.name,
                    size=stat.st_size if item.is_file() else 0,
                    is_dir=item.is_dir(),
                    modified=modified,
                    attributes=attrs,
                )
            )

        return sorted(entries, key=lambda x: (not x.is_dir, x.name.upper()))

    def change_directory(self, path: str) -> str:
        """Change current directory."""
        if not path or path.strip() == '':
            self.current_dir = self.home_dir
            return self.get_current_path()

        target = self._resolve_path(path)

        if not target.exists():
            raise FileNotFoundError(f'Directory not found: {path}')

        if not target.is_dir():
            raise NotADirectoryError(f'Not a directory: {path}')

        self.current_dir = target
        return self.get_current_path()

    def make_directory(self, name: str) -> None:
        """Create a new directory."""
        target = self._resolve_path(name)
        target.mkdir(parents=True, exist_ok=False)

    def remove_directory(self, name: str) -> None:
        """Remove an empty directory."""
        target = self._resolve_path(name)

        if not target.exists():
            raise FileNotFoundError(f'Directory not found: {name}')

        if not target.is_dir():
            raise NotADirectoryError(f'Not a directory: {name}')

        # Check if empty
        if any(target.iterdir()):
            raise OSError(f'Directory not empty: {name}')

        target.rmdir()

    def remove_directory_recursive(self, name: str) -> None:
        """Remove a directory and all its contents."""
        target = self._resolve_path(name)

        if not target.exists():
            raise FileNotFoundError(f'Directory not found: {name}')

        if not target.is_dir():
            raise NotADirectoryError(f'Not a directory: {name}')

        shutil.rmtree(target)

    def _find_case_insensitive(self, path: Path) -> Path:
        """Find a file/directory with case-insensitive matching.

        Walks each segment of the path relative to home_dir, resolving
        case mismatches at every level so that multi-segment DOS paths
        like ``MYDIR\\SUBDIR\\FILE.TXT`` work on case-sensitive hosts.
        """
        if path.exists():
            return path

        try:
            rel = path.relative_to(self.home_dir)
        except ValueError:
            return path

        current = self.home_dir
        for part in rel.parts:
            candidate = current / part
            if candidate.exists():
                current = candidate
                continue
            # Case-insensitive search in current directory
            part_lower = part.lower()
            found = False
            if current.exists() and current.is_dir():
                for item in current.iterdir():
                    if item.name.lower() == part_lower:
                        current = item
                        found = True
                        break
            if not found:
                return path
        return current

    def read_file(self, filename: str) -> str:
        """Read contents of a text file."""
        target = self._resolve_path(filename)

        if not target.exists():
            raise FileNotFoundError(f'File not found: {filename}')

        if target.is_dir():
            raise IsADirectoryError(f'Is a directory: {filename}')

        with open(target, encoding='utf-8', errors='replace') as f:
            return f.read()

    def write_file(self, filename: str, content: str) -> None:
        """Write content to a file."""
        target = self._resolve_path(filename)
        target.parent.mkdir(parents=True, exist_ok=True)

        with open(target, 'w', encoding='utf-8') as f:
            f.write(content)

    def delete_file(self, filename: str) -> None:
        """Delete a file."""
        target = self._resolve_path(filename)

        if not target.exists():
            raise FileNotFoundError(f'File not found: {filename}')

        if target.is_dir():
            raise IsADirectoryError(f'Is a directory: {filename}')

        target.unlink()

    def copy_file(self, source: str, dest: str) -> None:
        """Copy a file."""
        source_path = self._resolve_path(source)
        dest_path = self._resolve_path(dest)

        if not source_path.exists():
            raise FileNotFoundError(f'Source not found: {source}')

        if source_path.is_dir():
            raise IsADirectoryError(f'Source is a directory: {source}')

        # If dest is an existing directory, copy into it
        if dest_path.exists() and dest_path.is_dir():
            dest_path = dest_path / source_path.name

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, dest_path)

    def move_file(self, source: str, dest: str) -> None:
        """Move/rename a file or directory."""
        source_path = self._resolve_path(source)
        dest_path = self._resolve_path(dest)

        if not source_path.exists():
            raise FileNotFoundError(f'Source not found: {source}')

        # If dest is an existing directory, move into it
        if dest_path.exists() and dest_path.is_dir():
            dest_path = dest_path / source_path.name

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source_path), str(dest_path))

    def rename(self, old_name: str, new_name: str) -> None:
        """Rename a file or directory."""
        old_path = self._resolve_path(old_name)
        new_path = self._resolve_path(new_name)

        if not old_path.exists():
            raise FileNotFoundError(f'Source not found: {old_name}')

        if new_path.exists():
            raise FileExistsError(f'Destination already exists: {new_name}')

        old_path.rename(new_path)

    def file_exists(self, filename: str) -> bool:
        """Check if a file exists (case-insensitive for DOS compatibility)."""
        try:
            target = self._resolve_path(filename)
            return target.exists() and target.is_file()
        except (PermissionError, FileNotFoundError):
            return False

    def dir_exists(self, dirname: str) -> bool:
        """Check if a directory exists (case-insensitive for DOS compatibility)."""
        try:
            target = self._resolve_path(dirname)
            return target.exists() and target.is_dir()
        except (PermissionError, FileNotFoundError):
            return False

    def walk_directory(self, path: str = '.'):
        """Recursively walk a directory tree.

        Yields (dir_path, dirs, files) tuples.
        """
        target = self._resolve_path(path)

        if not target.exists():
            raise FileNotFoundError(f'Directory not found: {path}')

        if not target.is_dir():
            raise NotADirectoryError(f'Not a directory: {path}')

        for dirpath, dirnames, filenames in os.walk(target):
            rel = Path(dirpath).relative_to(self.home_dir)
            yield (
                str(rel),
                sorted(dirnames, key=str.upper),
                sorted(filenames, key=str.upper),
            )

    def get_file_info(self, filename: str):
        """Get FileInfo for a specific file."""
        target = self._resolve_path(filename)

        if not target.exists():
            raise FileNotFoundError(f'File not found: {filename}')

        stat = target.stat()
        modified = datetime.fromtimestamp(stat.st_mtime)
        attrs = 'D' if target.is_dir() else ' '
        attrs += 'R' if not os.access(target, os.W_OK) else ' '
        attrs += 'H' if target.name.startswith('.') else ' '

        return FileInfo(
            name=target.name,
            size=stat.st_size if target.is_file() else 0,
            is_dir=target.is_dir(),
            modified=modified,
            attributes=attrs,
        )

    def get_free_space(self) -> int:
        """Get free space in bytes."""
        stat = os.statvfs(self.home_dir)
        return stat.f_frsize * stat.f_bavail

    def get_total_size(self) -> int:
        """Get total size of user's home directory."""
        total = 0
        for dirpath, _dirnames, filenames in os.walk(self.home_dir):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                total += os.path.getsize(fp)
        return total
