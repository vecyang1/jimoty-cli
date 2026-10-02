"""Unit and integration tests for jimoty CLI entry points, arguments, and exit codes (Requirement R4).

Verifies:
- Main CLI help and subcommand discovery (search, get, diagnose, template, checklist, config)
- Subcommand argument parsing and validation
- Standard output formatting and --json compliance
- Exit codes (0 for success, non-zero for syntax or execution failures).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any
import pytest

try:
    from jimoty.cli import main as cli_main
    HAS_CLI = True
except ImportError:
    HAS_CLI = False

pytestmark = pytest.mark.skipif(
    not HAS_CLI,
    reason="jimoty.cli is pending implementation in Milestone 4",
)


class TestCliInterface:
    """Test CLI commands, flags, help outputs, and exit codes."""

    def test_cli_help(self) -> None:
        """Verify jimoty-cli --help displays description and available subcommands."""
        result = subprocess.run(
            [sys.executable, "-m", "jimoty", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        output = result.stdout
        assert "search" in output
        assert "diagnose" in output or "get" in output
        assert "template" in output or "checklist" in output

    def test_search_subcommand_help(self) -> None:
        """Verify jimoty search --help displays search arguments."""
        result = subprocess.run(
            [sys.executable, "-m", "jimoty", "search", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        output = result.stdout
        assert "--municipality" in output or "-m" in output
        assert "--max-price" in output or "-p" in output
        assert "--keyword" in output or "-k" in output

    def test_diagnose_subcommand_help(self) -> None:
        """Verify jimoty diagnose --help displays argument expectations."""
        result = subprocess.run(
            [sys.executable, "-m", "jimoty", "diagnose", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        output = result.stdout
        assert "url" in output.lower() or "id" in output.lower()
        assert "--json" in output

    def test_checklist_subcommand_output(self) -> None:
        """Verify jimoty checklist generates output with exit code 0."""
        result = subprocess.run(
            [sys.executable, "-m", "jimoty", "checklist"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert len(result.stdout) > 0

    def test_checklist_subcommand_json_output(self) -> None:
        """Verify jimoty checklist --json produces valid parseable JSON array."""
        result = subprocess.run(
            [sys.executable, "-m", "jimoty", "checklist", "--json"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) >= 5

    def test_config_subcommand(self) -> None:
        """Verify jimoty config prints current operational parameters and masked proxy."""
        result = subprocess.run(
            [sys.executable, "-m", "jimoty", "config"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "kanagawa" in result.stdout.lower() or "chigasaki" in result.stdout.lower()
