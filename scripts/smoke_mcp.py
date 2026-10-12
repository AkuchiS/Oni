"""Exercise an installed oni-mcp entry point, without importing its source package."""
import json
import subprocess
import sys
from pathlib import Path

command, target = sys.argv[1:]
target = str(Path(target).resolve())
messages = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "capabilities": {},
        "clientInfo": {"name": "oni-smoke", "version": "1"}}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
        "name": "analyze_repository", "arguments": {"path": target}}},
]
result = subprocess.run([command, "--root", target],
                        input="\n".join(json.dumps(m) for m in messages) + "\n",
                        capture_output=True, text=True, timeout=30, check=True)
responses = [json.loads(line) for line in result.stdout.splitlines()]
if [r["id"] for r in responses] != [1, 2, 3]:
    raise SystemExit("Unexpected MCP responses")
if responses[1]["result"]["tools"][0]["name"] != "analyze_repository":
    raise SystemExit("Oni tool not discovered")
if responses[2]["result"].get("isError"):
    raise SystemExit("MCP analysis failed")
data = json.loads(responses[2]["result"]["content"][0]["text"])
if data["teardown"]["_model"] is not None:
    raise SystemExit("MCP unexpectedly used a model")
print("Installed MCP initialization, discovery and offline analysis passed")
