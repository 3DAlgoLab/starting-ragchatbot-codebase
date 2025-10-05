# UV Guide for pip Users

UV is a fast Python package manager written in Rust. It's a drop-in replacement for pip with better performance and dependency resolution.

## Quick Reference: pip → uv

| Task | pip | uv |
|------|-----|-----|
| Install package | `pip install package` | `uv pip install package` |
| Install from requirements | `pip install -r requirements.txt` | `uv pip install -r requirements.txt` |
| Install dev dependencies | `pip install -e .` | `uv pip install -e .` |
| Sync all dependencies | `pip install -r requirements.txt` | `uv sync` |
| Create virtual environment | `python -m venv .venv` | `uv venv` |
| Uninstall package | `pip uninstall package` | `uv pip uninstall package` |
| List installed packages | `pip list` | `uv pip list` |
| Show package info | `pip show package` | `uv pip show package` |

## Key Commands

### `uv sync`
**Most common command** - Installs/updates all dependencies from `pyproject.toml` (like `pip install -r requirements.txt` but smarter):
```bash
uv sync                    # Install all dependencies
uv sync --no-dev          # Skip dev dependencies
```

### `uv run`
Run a command with the project's virtual environment automatically activated:
```bash
uv run python script.py    # Instead of: source .venv/bin/activate && python script.py
uv run uvicorn app:app     # Run server without manual venv activation
uv run pytest              # Run tests
```

### `uv pip`
Traditional pip commands with uv speed:
```bash
uv pip install requests
uv pip install -e .        # Editable install
uv pip freeze              # Show installed packages
```

### `uv venv`
Create virtual environment (faster than venv):
```bash
uv venv                    # Creates .venv/
uv venv .venv --python 3.11  # Specify Python version
```

## Advantages over pip

- **10-100x faster** installation and dependency resolution
- **Better dependency resolution** - catches conflicts pip misses
- **Lock files** - `uv.lock` ensures reproducible builds
- **Unified tool** - manages Python versions, venvs, and packages
- **No venv activation needed** with `uv run`

## Common Workflows

### Starting a new project
```bash
uv venv                    # Create virtual environment
uv sync                    # Install dependencies from pyproject.toml
```

### Running the application (this project)
```bash
uv sync                    # Install/update dependencies
uv run uvicorn app:app --reload --port 8000
```

### Adding a new package
```bash
uv pip install new-package
# Or add to pyproject.toml, then:
uv sync
```

## Troubleshooting

**"command not found: uv"** - Install with `curl -LsSf https://astral.sh/uv/install.sh | sh`

**Package not found** - uv uses PyPI by default, same as pip

**Need specific Python version** - `uv venv --python 3.11`

## Learn More

- Docs: https://docs.astral.sh/uv/
- Comparison: https://docs.astral.sh/uv/pip/compatibility/
