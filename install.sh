#!/usr/bin/env bash
# oni installer — no dependencies, just puts `oni` on your PATH.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "oni — clean-room reverse-engineering engine"
echo

if command -v pipx >/dev/null 2>&1; then
    echo "→ installing with pipx (isolated)…"
    pipx install --force "$HERE"
elif command -v pip3 >/dev/null 2>&1; then
    echo "→ installing with pip3 --user…"
    pip3 install --user --upgrade "$HERE"
else
    # zero-install fallback: a shim that runs the package in place
    BIN="${HOME}/.local/bin"
    mkdir -p "$BIN"
    cat > "$BIN/oni" <<EOF
#!/usr/bin/env bash
exec python3 -m oni "\$@"
EOF
    chmod +x "$BIN/oni"
    # make the package importable from the shim
    if ! python3 -c "import oni" >/dev/null 2>&1; then
        echo "export PYTHONPATH=\"$HERE:\${PYTHONPATH:-}\"" >> "${HOME}/.bashrc"
        export PYTHONPATH="$HERE:${PYTHONPATH:-}"
    fi
    echo "→ installed shim at $BIN/oni (ensure $BIN is on PATH)"
fi

echo
echo "done. Try:  oni <owner/repo>     e.g.  oni Aider-AI/aider --no-llm"
echo "For an LLM-assisted teardown, set ONI_API_KEY (+ optional ONI_MODEL / ONI_ENDPOINT)."
