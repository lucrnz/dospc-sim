# DosPC Sim

A retro-styled terminal UI application built with Python and Textual.

## Features

- **DOS/9x Style Menubar**: Classic menu bar at the top with File, Edit, View, and Help menus - usable with mouse clicks
- **Light/Dark Theme Toggle**: Press `t` to switch between light and dark themes
- **Retro UI**: Box-drawing characters and classic styling reminiscent of early computing interfaces
- **Coming Soon Screen**: Placeholder UI showing the application is under development

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

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `q` | Quit the application |
| `t` | Toggle between light and dark themes |
| `f1` | Show help information |

## Development

### Running Tests

```bash
uv run pytest
```

### Project Structure

```
dospc-sim/
├── src/
│   └── dospc_sim/
│       ├── __init__.py
│       └── main.py          # Main application code
├── tests/
│   ├── __init__.py
│   ├── test_main.py         # Unit tests for main module
│   ├── test_integration.py  # Integration tests
│   └── test_widgets.py      # Widget-specific tests
├── pyproject.toml
└── README.md
```

## License

MIT License
