#!/usr/bin/env bash
# An isolated installation. Does not edit shell startup files or system Python.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ONI_VENV="${ONI_VENV:-${HOME}/.local/share/oni/venv}"
PYTHON="${PYTHON:-python3}"
"$PYTHON" -m venv "$ONI_VENV"
"$ONI_VENV/bin/python" -m pip install --upgrade "$HERE"
"$ONI_VENV/bin/oni" --version
printf 'Installed. Run: "%s/bin/oni" <local-repo> --offline\n' "$ONI_VENV"
printf 'Or add "%s/bin" to PATH.\n' "$ONI_VENV"
