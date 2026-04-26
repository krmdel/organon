"""Tests for shell script quality — SH-01, SH-02, SH-03.

Validates all scripts in scripts/ and scripts/admin/ for:
  - SH-01: ShellCheck passes with --severity=error (no errors)
  - SH-02: Correct shebang (#!/usr/bin/env bash)
  - SH-03: No GNU-only flags (macOS BSD-compatible)
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constants (uses conftest.py SCRIPTS_DIR for consistency)
# ---------------------------------------------------------------------------

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"

ALL_SCRIPTS = sorted(
    list(SCRIPTS_DIR.glob("*.sh")) + list((SCRIPTS_DIR / "admin").glob("*.sh"))
)

SHELLCHECK_AVAILABLE = shutil.which("shellcheck") is not None


# ---------------------------------------------------------------------------
# SH-01, SH-02, SH-03 Tests
# ---------------------------------------------------------------------------


class TestShellScripts:
    """SH-01 through SH-03: ShellCheck, shebang, and BSD compatibility."""

    @pytest.mark.skipif(
        not SHELLCHECK_AVAILABLE,
        reason="shellcheck not installed -- run 'brew install shellcheck'",
    )
    @pytest.mark.parametrize("script", ALL_SCRIPTS, ids=lambda s: s.name)
    def test_sh_01_shellcheck_passes(self, script):
        """SH-01: ShellCheck passes with --severity=error for every script."""
        result = subprocess.run(
            ["shellcheck", "--severity=error", str(script)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"ShellCheck errors in {script.name}:\n{result.stdout}"
        )

    @pytest.mark.parametrize("script", ALL_SCRIPTS, ids=lambda s: s.name)
    def test_sh_02_correct_shebang(self, script):
        """SH-02: Every script must use #!/usr/bin/env bash shebang."""
        first_line = script.read_text().splitlines()[0] if script.stat().st_size > 0 else ""
        assert first_line.strip() == "#!/usr/bin/env bash", (
            f"{script.name} has wrong shebang: {first_line.strip()!r}"
        )

    @pytest.mark.parametrize("script", ALL_SCRIPTS, ids=lambda s: s.name)
    def test_sh_03_no_gnu_only_flags(self, script):
        """SH-03: No GNU-only flags that break on macOS BSD tools."""
        text = script.read_text()

        issues = []

        # grep -P (Perl regex -- GNU grep only, not on macOS by default)
        if re.search(r"\bgrep\s+-[a-zA-Z]*P", text):
            issues.append(
                "grep -P (Perl regex) is GNU-only. Use grep -E or Python for complex patterns."
            )

        # readlink -f (GNU coreutils only, not on macOS without greadlink)
        if re.search(r"\breadlink\s+-f\b", text):
            issues.append(
                "readlink -f is GNU-only. Use 'python3 -c \"import os; print(os.path.realpath(...))\"' "
                "or 'cd ... && pwd' idiom on macOS."
            )

        # sed -i without '' (GNU sed accepts -i directly; BSD sed requires -i '')
        if re.search(r"sed\s+-i\s+(?!''|\"\")", text):
            issues.append(
                "sed -i without '' is GNU-only. Use sed -i '' on macOS BSD sed."
            )

        # date -d (GNU date's --date/-d flag not available on macOS).
        # Exception: cross-platform guard patterns that also use 'date -j' (macOS BSD)
        # are intentional and acceptable.
        if re.search(r"\bdate\s+-d\b", text) and not re.search(r"\bdate\s+-j\b", text):
            issues.append(
                "date -d is GNU-only. Use python3 or gdate for date arithmetic on macOS. "
                "If cross-platform, guard with 'date -j' (macOS) first, date -d as fallback."
            )

        # find -printf (GNU find only, not on macOS)
        if re.search(r"\bfind\b.*-printf\b", text):
            issues.append(
                "find -printf is GNU-only. Use find + awk/python on macOS."
            )

        assert not issues, (
            f"{script.name} contains GNU-only flags:\n"
            + "\n".join(f"  - {i}" for i in issues)
        )
