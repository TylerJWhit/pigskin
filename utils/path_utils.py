"""Utility functions for path management across the application."""

import sys
from pathlib import Path
from typing import Union

def setup_project_path():
    """Add the project root to Python path if not already present."""
    project_root = str(get_project_root())
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent

def get_data_dir() -> Path:
    """Get the data directory path."""
    return get_project_root() / "data"

def get_config_dir() -> Path:
    """Get the config directory path."""
    return get_project_root() / "config"

def get_results_dir() -> Path:
    """Get the results directory path."""
    return get_project_root() / "results"

def ensure_dir_exists(path: Union[str, Path]) -> Path:
    """Ensure a directory exists, creating it if necessary."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_config_file() -> Path:
    """Get the main config file path."""
    return get_config_dir() / "config.json"

def get_data_file(filename: str) -> Path:
    """Get a data file path in the data directory.

    Raises ValueError if the resolved path escapes the data directory.
    """
    base = get_data_dir().resolve()
    resolved = (get_data_dir() / filename).resolve()
    if not str(resolved).startswith(str(base) + "/") and resolved != base:
        raise ValueError(f"Path traversal detected: {filename!r}")
    return resolved

def safe_file_path(path: Union[str, Path]) -> Path:
    """Convert to Path, validate it stays within the project root, and ensure parent dirs exist.

    Raises ValueError if the resolved path escapes the project root.
    """
    root = get_project_root().resolve()
    resolved = Path(path).resolve()
    if not str(resolved).startswith(str(root) + "/") and resolved != root:
        raise ValueError(f"Path traversal detected: {path!r}")
    ensure_dir_exists(resolved.parent)
    return resolved
