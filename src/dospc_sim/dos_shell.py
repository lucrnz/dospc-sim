"""DOS shell simulation for SSH clients."""

import re
import shlex
from typing import List, Optional, Callable, Dict
from pathlib import Path
from datetime import datetime

from dospc_sim.filesystem import UserFilesystem, FileInfo
from dospc_sim.editor import run_editor


class DOSShell:
    """Simulates a DOS environment for SSH clients."""

    def __init__(
        self,
        filesystem: UserFilesystem,
        username: str,
        output_callback: Optional[Callable[[str], None]] = None,
    ):
        self.fs = filesystem
        self.username = username
        self.output_callback = output_callback or print
        self.running = False
        self.last_errorlevel = 0
        self.aliases: Dict[str, str] = {}
        self.environment = {
            "PROMPT": f"{self.fs._drive_letter}:\\>",
            "PATH": "C:\\;C:\\DOS;C:\\WINDOWS",
            "COMSPEC": "C:\\COMMAND.COM",
            "TEMP": "C:\\TEMP",
            "TMP": "C:\\TEMP",
        }

    def _output(self, text: str = "") -> None:
        """Output text to the client."""
        self.output_callback(text)

    def _output_line(self, text: str = "") -> None:
        """Output a line of text to the client."""
        self._output(text)

    def get_prompt(self) -> str:
        """Get the current DOS prompt."""
        path = self.fs.get_current_path()
        return f"{path}>"

    def run(self) -> None:
        """Run the DOS shell interactively."""
        self.running = True
        self._output_line(f"Welcome, {self.username}!")
        self._output_line(f"Type HELP for available commands.")
        self._output_line()

    def execute_command(self, command_line: str) -> int:
        """Execute a single command and return errorlevel."""
        command_line = command_line.strip()

        if not command_line:
            return 0

        # Handle comments in batch files
        if command_line.startswith("::") or command_line.startswith("REM "):
            return 0

        # Parse command and arguments
        try:
            parts = shlex.split(command_line, posix=False)
        except ValueError:
            # Fallback for simple parsing
            parts = command_line.split()

        if not parts:
            return 0

        command = parts[0].upper()
        args = parts[1:]

        # Check for aliases
        if command in self.aliases:
            alias_cmd = self.aliases[command]
            # Replace $1, $2, etc. with arguments
            for i, arg in enumerate(args, 1):
                alias_cmd = alias_cmd.replace(f"${i}", arg)
            alias_cmd = alias_cmd.replace("$*", " ".join(args))
            return self.execute_command(alias_cmd)

        # Execute the command
        try:
            handler = getattr(self, f"cmd_{command.lower()}", None)
            if handler:
                self.last_errorlevel = handler(args)
            else:
                # Check if it's a batch file
                batch_file = self._find_batch_file(command)
                if batch_file:
                    self.last_errorlevel = self._execute_batch(batch_file, args)
                else:
                    self._output_line(f"Bad command or file name: {command}")
                    self.last_errorlevel = 1
        except Exception as e:
            self._output_line(f"Error: {str(e)}")
            self.last_errorlevel = 1

        return self.last_errorlevel

    def _find_batch_file(self, name: str) -> Optional[str]:
        """Find a batch file (.bat or .cmd)."""
        for ext in [".BAT", ".CMD"]:
            # Check current directory
            test_path = f"{name}{ext}"
            if self.fs.file_exists(test_path):
                return test_path

            # Check PATH directories
            for path_dir in self.environment["PATH"].split(";"):
                try:
                    path_dir = path_dir.strip()
                    if path_dir:
                        test_path = f"{path_dir}\\{name}{ext}"
                        if self.fs.file_exists(test_path):
                            return test_path
                except:
                    continue
        return None

    def _execute_batch(self, batch_file: str, args: List[str]) -> int:
        """Execute a batch file."""
        try:
            content = self.fs.read_file(batch_file)
            lines = content.splitlines()

            # Set batch parameters %0-%9
            params = {0: batch_file}
            for i, arg in enumerate(args[:9], 1):
                params[i] = arg

            for line in lines:
                line = line.strip()
                if not line or line.startswith("::") or line.upper().startswith("REM "):
                    continue

                # Expand batch parameters
                for i in range(10):
                    placeholder = f"%{i}"
                    if placeholder in line and i in params:
                        line = line.replace(placeholder, params[i])

                self.execute_command(line)

            return 0
        except Exception as e:
            self._output_line(f"Batch error: {str(e)}")
            return 1

    # ==================== DOS Commands ====================

    def cmd_dir(self, args: List[str]) -> int:
        """DIR - List directory contents."""
        path = "."
        show_all = False
        wide_format = False

        # Parse arguments
        for arg in args:
            upper = arg.upper()
            if upper == "/W":
                wide_format = True
            elif upper == "/A":
                show_all = True
            elif not arg.startswith("/"):
                path = arg

        try:
            entries = self.fs.list_directory(path)

            if not wide_format:
                # Standard format
                self._output_line(
                    f" Volume in drive {self.fs._drive_letter} is DOSPC-SIM"
                )
                self._output_line(f" Directory of {self.fs.get_current_path()}")
                self._output_line()

                total_files = 0
                total_dirs = 0
                total_size = 0

                for entry in entries:
                    if not show_all and entry.name.startswith("."):
                        continue

                    date_str = entry.modified.strftime("%m/%d/%Y")
                    time_str = entry.modified.strftime("%I:%M %p")

                    if entry.is_dir:
                        self._output_line(
                            f"{date_str}  {time_str}    <DIR>          {entry.name}"
                        )
                        total_dirs += 1
                    else:
                        size_str = f"{entry.size:>14,}"
                        self._output_line(
                            f"{date_str}  {time_str}{size_str} {entry.name}"
                        )
                        total_files += 1
                        total_size += entry.size

                self._output_line()
                self._output_line(
                    f"{'':>14}{total_files} File(s){total_size:>15,} bytes"
                )
                free_space = self.fs.get_free_space()
                self._output_line(
                    f"{'':>14}{total_dirs} Dir(s){free_space:>16,} bytes free"
                )
            else:
                # Wide format
                names = [
                    e.name for e in entries if show_all or not e.name.startswith(".")
                ]
                for i in range(0, len(names), 5):
                    row = names[i : i + 5]
                    self._output_line("  ".join(f"{n:<15}" for n in row))

            return 0
        except Exception as e:
            self._output_line(f"File not found: {path}")
            return 1

    def cmd_cd(self, args: List[str]) -> int:
        """CD/CHDIR - Change directory."""
        if not args:
            # Show current directory
            self._output_line(self.fs.get_current_path())
            return 0

        path = args[0]
        try:
            new_path = self.fs.change_directory(path)
            return 0
        except Exception as e:
            self._output_line(f"The system cannot find the path specified.")
            return 1

    cmd_chdir = cmd_cd  # Alias

    def cmd_md(self, args: List[str]) -> int:
        """MD/MKDIR - Make directory."""
        if not args:
            self._output_line("The syntax of the command is incorrect.")
            return 1

        for dirname in args:
            try:
                self.fs.make_directory(dirname)
            except FileExistsError:
                self._output_line(f"A subdirectory or file {dirname} already exists.")
                return 1
            except Exception as e:
                self._output_line(f"Error creating directory: {str(e)}")
                return 1
        return 0

    cmd_mkdir = cmd_md  # Alias

    def cmd_rd(self, args: List[str]) -> int:
        """RD/RMDIR - Remove directory."""
        if not args:
            self._output_line("The syntax of the command is incorrect.")
            return 1

        recursive = False
        dirs = []

        for arg in args:
            if arg.upper() == "/S":
                recursive = True
            elif arg.upper() == "/Q":
                pass  # Quiet mode - ignore for now
            elif not arg.startswith("/"):
                dirs.append(arg)

        for dirname in dirs:
            try:
                if recursive:
                    self._output(f"Are you sure (Y/N)? ")
                    # In real implementation, would wait for input
                    self.fs.remove_directory_recursive(dirname)
                else:
                    self.fs.remove_directory(dirname)
            except Exception as e:
                self._output_line(f"Error removing directory: {str(e)}")
                return 1
        return 0

    cmd_rmdir = cmd_rd  # Alias

    def cmd_copy(self, args: List[str]) -> int:
        """COPY - Copy files."""
        if len(args) < 2:
            self._output_line("The syntax of the command is incorrect.")
            return 1

        # Simple copy: source dest
        source = args[0]
        dest = args[-1]

        try:
            self.fs.copy_file(source, dest)
            self._output_line(f"        1 file(s) copied.")
            return 0
        except Exception as e:
            self._output_line(f"The system cannot find the file specified.")
            return 1

    def cmd_del(self, args: List[str]) -> int:
        """DEL/ERASE - Delete files."""
        if not args:
            self._output_line("The syntax of the command is incorrect.")
            return 1

        quiet = False
        files = []

        for arg in args:
            if arg.upper() == "/Q":
                quiet = True
            elif not arg.startswith("/"):
                files.append(arg)

        for pattern in files:
            try:
                # Simple wildcard support
                if "*" in pattern or "?" in pattern:
                    entries = self.fs.list_directory()
                    import fnmatch

                    for entry in entries:
                        if fnmatch.fnmatch(entry.name.upper(), pattern.upper()):
                            if not entry.is_dir:
                                if not quiet:
                                    self._output_line(f"Deleting {entry.name}")
                                self.fs.delete_file(entry.name)
                else:
                    self.fs.delete_file(pattern)
            except Exception as e:
                self._output_line(f"Could not find {pattern}")
                return 1
        return 0

    cmd_erase = cmd_del  # Alias

    def cmd_ren(self, args: List[str]) -> int:
        """REN/RENAME - Rename files."""
        if len(args) < 2:
            self._output_line("The syntax of the command is incorrect.")
            return 1

        old_name = args[0]
        new_name = args[1]

        try:
            self.fs.rename(old_name, new_name)
            return 0
        except Exception as e:
            self._output_line(f"Duplicate file name or file not found")
            return 1

    cmd_rename = cmd_ren  # Alias

    def cmd_move(self, args: List[str]) -> int:
        """MOVE - Move files."""
        if len(args) < 2:
            self._output_line("The syntax of the command is incorrect.")
            return 1

        source = args[0]
        dest = args[-1]

        try:
            self.fs.move_file(source, dest)
            self._output_line(f"        1 file(s) moved.")
            return 0
        except Exception as e:
            self._output_line(f"The system cannot find the file specified.")
            return 1

    def cmd_type(self, args: List[str]) -> int:
        """TYPE - Display file contents."""
        if not args:
            self._output_line("The syntax of the command is incorrect.")
            return 1

        filename = args[0]
        try:
            content = self.fs.read_file(filename)
            self._output_line(content)
            return 0
        except Exception as e:
            self._output_line(f"The system cannot find the file specified.")
            return 1

    def cmd_cls(self, args: List[str]) -> int:
        """CLS - Clear screen."""
        self._output("\x1b[2J\x1b[H")  # ANSI clear screen
        return 0

    def cmd_echo(self, args: List[str]) -> int:
        """ECHO - Display messages or toggle command echoing."""
        if not args:
            self._output_line(f"ECHO is {'on' if True else 'off'}")
            return 0

        # Handle ECHO ON/OFF
        if len(args) == 1 and args[0].upper() == "ON":
            return 0
        if len(args) == 1 and args[0].upper() == "OFF":
            return 0

        # Display text
        text = " ".join(args)
        # Remove surrounding quotes if present
        if (text.startswith('"') and text.endswith('"')) or (
            text.startswith("'") and text.endswith("'")
        ):
            text = text[1:-1]
        self._output_line(text)
        return 0

    def cmd_help(self, args: List[str]) -> int:
        """HELP - Display help information."""
        if args:
            # Help for specific command
            cmd = args[0].upper()
            help_text = self._get_command_help(cmd)
            self._output_line(help_text)
        else:
            # List all commands
            self._output_line(
                "For more information on a specific command, type HELP command-name"
            )
            self._output_line()
            commands = [
                "CD",
                "CHDIR",
                "CLS",
                "COPY",
                "DATE",
                "DEL",
                "DIR",
                "ECHO",
                "EDIT",
                "ERASE",
                "EXIT",
                "HELP",
                "MD",
                "MKDIR",
                "MOVE",
                "PATH",
                "PROMPT",
                "RD",
                "REN",
                "RENAME",
                "RMDIR",
                "SET",
                "TIME",
                "TYPE",
                "VER",
            ]
            for i in range(0, len(commands), 6):
                row = commands[i : i + 6]
                self._output_line("  ".join(f"{c:<10}" for c in row))
        return 0

    def _get_command_help(self, cmd: str) -> str:
        """Get help text for a specific command."""
        help_texts = {
            "CD": "Displays the name of or changes the current directory.",
            "CHDIR": "Displays the name of or changes the current directory.",
            "CLS": "Clears the screen.",
            "COPY": "Copies one or more files to another location.",
            "DATE": "Displays or sets the date.",
            "DEL": "Deletes one or more files.",
            "DIR": "Displays a list of files and subdirectories in a directory.",
            "ECHO": "Displays messages, or turns command-echoing on or off.",
            "EDIT": "Starts the DosPC Sim text editor.\n\nEDIT [filename]",
            "ERASE": "Deletes one or more files.",
            "EXIT": "Quits the command interpreter.",
            "HELP": "Provides help information for commands.",
            "MD": "Creates a directory.",
            "MKDIR": "Creates a directory.",
            "MOVE": "Moves one or more files from one directory to another.",
            "PATH": "Displays or sets a search path for executable files.",
            "PROMPT": "Changes the command prompt.",
            "RD": "Removes a directory.",
            "REN": "Renames a file or files.",
            "RENAME": "Renames a file or files.",
            "RMDIR": "Removes a directory.",
            "SET": "Displays, sets, or removes environment variables.",
            "TIME": "Displays or sets the system time.",
            "TYPE": "Displays the contents of a text file.",
            "VER": "Displays the operating system version.",
        }
        return help_texts.get(cmd, f"Help not available for {cmd}")

    def cmd_exit(self, args: List[str]) -> int:
        """EXIT - Exit the shell."""
        self.running = False
        return 0

    def cmd_ver(self, args: List[str]) -> int:
        """VER - Display version."""
        self._output_line()
        self._output_line(f"DosPC Sim DOS [Version 1.0]")
        self._output_line()
        return 0

    def cmd_set(self, args: List[str]) -> int:
        """SET - Display or set environment variables."""
        if not args:
            # Display all environment variables
            for key, value in sorted(self.environment.items()):
                self._output_line(f"{key}={value}")
            return 0

        # Parse SET VAR=VALUE
        arg = " ".join(args)
        if "=" in arg:
            parts = arg.split("=", 1)
            var_name = parts[0].strip()
            var_value = parts[1].strip() if len(parts) > 1 else ""
            self.environment[var_name.upper()] = var_value
        else:
            # Display specific variable
            var_name = arg.strip().upper()
            if var_name in self.environment:
                self._output_line(f"{var_name}={self.environment[var_name]}")
        return 0

    def cmd_prompt(self, args: List[str]) -> int:
        """PROMPT - Change the command prompt."""
        if args:
            new_prompt = " ".join(args)
            self.environment["PROMPT"] = new_prompt
        else:
            self._output_line(f"Current prompt: {self.environment['PROMPT']}")
        return 0

    def cmd_path(self, args: List[str]) -> int:
        """PATH - Display or set the search path."""
        if args:
            new_path = " ".join(args)
            self.environment["PATH"] = new_path
        else:
            self._output_line(f"PATH={self.environment['PATH']}")
        return 0

    def cmd_date(self, args: List[str]) -> int:
        """DATE - Display or set the date."""
        now = datetime.now()
        self._output_line(f"Current date: {now.strftime('%a %m/%d/%Y')}")
        return 0

    def cmd_time(self, args: List[str]) -> int:
        """TIME - Display or set the time."""
        now = datetime.now()
        self._output_line(f"Current time: {now.strftime('%I:%M:%S.%f %p')[:12]}")
        return 0

    def cmd_edit(self, args: List[str]) -> int:
        """EDIT - Text file editor."""
        filename = args[0] if args else ""

        # Check if we have an interactive input handler registered
        if hasattr(self, "_editor_input_handler") and self._editor_input_handler:
            return self._editor_input_handler(filename)

        # Fallback: just report that edit requires interactive mode
        self._output_line("EDIT requires an interactive terminal session.")
        self._output_line("Usage: EDIT [filename]")
        return 1

    def set_editor_handler(self, handler) -> None:
        """Set the handler function for interactive editor mode.

        The handler should accept a filename and return an exit code.
        """
        self._editor_input_handler = handler
