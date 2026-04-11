"""CLI interface for DosPC Sim."""

import argparse
import getpass
import logging
import signal
import sys

from dospc_sim.ssh_server import SSHServer
from dospc_sim.users import UserManager


def cmd_user_add(args):
    user_manager = UserManager()
    username = args.username

    if user_manager.user_exists(username):
        print(f"Error: User '{username}' already exists.")
        sys.exit(1)

    password = getpass.getpass(f"Password for '{username}': ")
    if not password:
        print("Error: Password cannot be empty.")
        sys.exit(1)

    password_confirm = getpass.getpass("Confirm password: ")
    if password != password_confirm:
        print("Error: Passwords do not match.")
        sys.exit(1)

    try:
        user = user_manager.create_user(username, password)
        print(f"User '{user.username}' created successfully.")
        print(f"  Home directory: {user.home_dir}")
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_user_list(args):
    user_manager = UserManager()
    users = user_manager.list_users()

    if not users:
        print("No users found.")
        return

    print(f"{'Username':<20} {'Created':<12} {'Last Login':<12} {'Home Directory'}")
    print("-" * 80)
    for user in users:
        last_login = (user.last_login or "Never")[:10]
        created = user.created_at[:10]
        print(f"{user.username:<20} {created:<12} {last_login:<12} {user.home_dir}")


def cmd_user_remove(args):
    user_manager = UserManager()
    username = args.username

    if not user_manager.user_exists(username):
        print(f"Error: User '{username}' not found.")
        sys.exit(1)

    confirm = input(f"Remove user '{username}'? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return

    remove_data = (
        input(f"Also remove all data for '{username}'? [y/N]: ").strip().lower()
    )

    user = user_manager.get_user(username)
    home_dir = user.home_dir
    user_manager.delete_user(username, remove_data=(remove_data == "y"))

    if remove_data == "y":
        print(f"User '{username}' and all data removed.")
    else:
        print(f"User '{username}' removed (home directory kept: {home_dir}).")


def cmd_server_listen(args):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )

    host = args.host
    port = args.port

    server = SSHServer(host=host, port=port)

    if not server.start():
        print("Failed to start SSH server.", file=sys.stderr)
        sys.exit(1)

    status = server.get_status()
    print(f"SSH server listening on {status['host']}:{status['port']}")
    print("Press Ctrl+C to stop.")

    def _shutdown(signum, frame):
        print("\nStopping SSH server...")
        server.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        signal.pause()
    except KeyboardInterrupt:
        _shutdown(None, None)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="dospc-sim",
        description="DosPC Sim - SSH DOS Environment Server",
    )
    subparsers = parser.add_subparsers(dest="command")

    user_parser = subparsers.add_parser("user", help="Manage users")
    user_subparsers = user_parser.add_subparsers(dest="user_command")

    user_add_parser = user_subparsers.add_parser("add", help="Add a new user")
    user_add_parser.add_argument("username", help="Username to create")

    user_subparsers.add_parser("list", help="List all users")

    user_remove_parser = user_subparsers.add_parser("remove", help="Remove a user")
    user_remove_parser.add_argument("username", help="Username to remove")

    server_parser = subparsers.add_parser("server", help="Server management")
    server_subparsers = server_parser.add_subparsers(dest="server_command")

    server_listen_parser = server_subparsers.add_parser(
        "listen", help="Start SSH server directly"
    )
    server_listen_parser.add_argument(
        "--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)"
    )
    server_listen_parser.add_argument(
        "--port", type=int, default=2222, help="Port (default: 2222)"
    )

    return parser


def run_cli(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "user":
        if args.user_command == "add":
            cmd_user_add(args)
        elif args.user_command == "list":
            cmd_user_list(args)
        elif args.user_command == "remove":
            cmd_user_remove(args)
        else:
            parser.parse_args(["user", "--help"])
    elif args.command == "server":
        if args.server_command == "listen":
            cmd_server_listen(args)
        else:
            parser.parse_args(["server", "--help"])
    elif args.command is None:
        return False
    else:
        return False

    return True
