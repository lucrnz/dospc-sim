# DosPC Sim

Terminal UI application built with Python and Textual.
This project exposes an SSH server to connect to a simulated DOS environment.

## Installation

This project uses `uv` for dependency management:

```bash
uv sync
```

## Usage

Run the application:

```bash
uv run dospc-sim
```

Run the standalone DOS shell from your current directory:

```bash
uv run dos-shell
```

Run a batch file with optional `%1..%9` arguments:

```bash
uv run dos-shell file.bat arg1 arg2
```

Interpret stdin as batch input (explicit token or piped stdin):

```bash
uv run dos-shell - < script.bat
uv run dos-shell STDIN < script.bat
cat script.bat | uv run dos-shell
```

## Development

Running unit tests:

```bash
uv run pytest
```

## License

[MIT License](./LICENSE)