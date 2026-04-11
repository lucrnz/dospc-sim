# AGENTS.md

Terminal UI application built with Python and Textual, exposing an SSH server that presents a simulated DOS environment to connected users.

This project uses `uv` for dependency management (`uv sync`, `uv run`).

## Git Commits

Follow conventional commits

## Architecture

All DOS/BATCH interpreter features should go through the LARK grammar + AST.

## Commands

Run tests: `uv run pytest`
Run the app: `uv run dospc-sim`
Lint: `uv run ruff check .`
Format: `uv run ruff format .`
