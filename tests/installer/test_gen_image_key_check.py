"""Tests for the gen-image prerequisite probe in installer/lib/deps.sh.

The regression this replaces: the probe looked for the `gemini` CLI and the
nanobanana extension, and warned on every run of every sync that gen-image
"needs it". The skill had since moved to calling /v1beta/interactions directly
with stdlib urllib and says so in as many words -- "The old `gemini` CLI +
`nanobanana` extension path is no longer used". So the warning was not merely
noise: it pushed the reader toward installing a tool the skill tells them to
ignore, and it fired on a machine where gen-image was fully working.

What must not regress is the OTHER half. The key reaches the environment via
~/.zshrc sourcing secrets/secrets.env, so a probe reading only the env var
false-warns under the non-login shell an installer actually runs in. Both
sources have to count.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPS_SH = REPO_ROOT / "installer" / "lib" / "deps.sh"


def run_check(repo_dir: Path, key_in_env: str | None) -> str:
    """Source deps.sh in a sandbox and run check_runtime_deps against it.

    The sandbox supplies the two globals install.sh sets that this function
    reads -- PLATFORM and REPO_DIR. GEMINI_API_KEY is removed from the
    environment unless the caller asks for it, since inheriting the developer's
    own key would make every negative case pass vacuously.
    """
    script = f"""
    set -euo pipefail
    PLATFORM=macos
    REPO_DIR={repo_dir!s}
    source {DEPS_SH!s}
    check_runtime_deps
    """
    cmd = ["bash", "-c", script]
    if key_in_env is None:
        cmd = ["env", "-u", "GEMINI_API_KEY", *cmd]
    else:
        cmd = ["env", f"GEMINI_API_KEY={key_in_env}", *cmd]
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout


def write_secrets(repo_dir: Path, line: str) -> None:
    d = repo_dir / "secrets"
    d.mkdir(parents=True, exist_ok=True)
    (d / "secrets.env").write_text(line)


def test_warns_when_the_key_is_in_neither_the_env_nor_secrets(tmp_path):
    assert "GEMINI_API_KEY" in run_check(tmp_path, key_in_env=None)


def test_silent_when_the_key_is_only_in_the_environment(tmp_path):
    assert "GEMINI_API_KEY" not in run_check(tmp_path, key_in_env="AIzaFAKE")


def test_silent_when_the_key_is_only_in_secrets_env(tmp_path):
    """The installer runs in a non-login shell, which never sources ~/.zshrc.
    Reading the env var alone would warn on a correctly-configured machine."""
    write_secrets(tmp_path, "GEMINI_API_KEY=AIzaFAKE\n")
    assert "GEMINI_API_KEY" not in run_check(tmp_path, key_in_env=None)


def test_silent_when_secrets_env_exports_the_key(tmp_path):
    """secrets.env is written both ways in the wild; `export` is not a miss."""
    write_secrets(tmp_path, "export GEMINI_API_KEY=AIzaFAKE\n")
    assert "GEMINI_API_KEY" not in run_check(tmp_path, key_in_env=None)


def test_warns_when_secrets_env_holds_a_different_key(tmp_path):
    """A substring match on the file would pass this; the probe anchors the
    name to the start of the line so NANOBANANA_API_KEY is not mistaken for it."""
    write_secrets(tmp_path, "NANOBANANA_API_KEY=AIzaFAKE\n")
    assert "GEMINI_API_KEY" in run_check(tmp_path, key_in_env=None)


def test_no_longer_probes_the_deprecated_gemini_cli(tmp_path):
    """The skill deprecates that path outright, so the installer must not
    mention it -- a stale hint is what sent the reader to install it."""
    out = run_check(tmp_path, key_in_env=None)
    assert "gemini CLI" not in out
    assert "nanobanana" not in out.lower()
