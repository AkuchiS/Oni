import json
import subprocess
import sys
from pathlib import Path

import pytest
from oni.mcp import Server, PROTOCOL

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "tinyrepo"


def request(method, params=None, id=1):
    return {"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}}


def ready(root):
    server = Server([str(root)])
    response = server.handle(request("initialize", {"protocolVersion": PROTOCOL}))
    assert response["result"]["protocolVersion"] == PROTOCOL
    assert server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    return server


def test_requires_initialization():
    assert "error" in Server([str(FIXTURE)]).handle(request("tools/list"))


def test_tool_discovery_and_analysis():
    server = ready(FIXTURE)
    assert server.handle(request("tools/list"))["result"]["tools"][0]["annotations"]["readOnlyHint"]
    result = server.handle(request("tools/call", {
        "name": "analyze_repository", "arguments": {"path": str(FIXTURE)}}))["result"]
    assert not result["isError"]
    data = json.loads(result["content"][0]["text"])
    assert data["target"] == "tinyrepo" and data["teardown"]["_model"] is None


@pytest.mark.parametrize("args", [
    {"path": "psf/requests"}, {"path": str(FIXTURE.parent)},
    {"path": str(FIXTURE), "jewels": True},
    {"path": str(FIXTURE), "jewels": 0},
    {"path": str(FIXTURE), "out": "/tmp/report"},
    {"path": str(FIXTURE), "query": []},
])
def test_rejects_invalid_tool_inputs(args):
    with pytest.raises(ValueError):
        ready(FIXTURE).analyze(args)


def test_symlink_cannot_escape_root(tmp_path):
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir(); outside.mkdir()
    try:
        (allowed / "escape").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation unavailable")
    with pytest.raises(ValueError):
        ready(allowed).analyze({"path": str(allowed / "escape")})


def test_stdio_session():
    messages = [request("initialize", {"protocolVersion": PROTOCOL}),
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                request("tools/list", id=2),
                request("tools/call", {"name": "analyze_repository",
                                       "arguments": {"path": str(FIXTURE)}}, id=3)]
    result = subprocess.run([sys.executable, "-m", "oni.mcp", "--root", str(FIXTURE)],
                            input="\n".join(json.dumps(m) for m in messages) + "\n",
                            text=True, capture_output=True, timeout=20, check=True)
    responses = [json.loads(line) for line in result.stdout.splitlines()]
    assert [r["id"] for r in responses] == [1, 2, 3]
    assert not responses[-1]["result"]["isError"]
    assert result.stderr == ""


def test_malformed_requests_do_not_crash():
    server = ready(FIXTURE)
    for malformed in ([], None, {"jsonrpc": "2.0", "id": 1, "method": []},
                      request("tools/call", params=[1])):
        assert "error" in server.handle(malformed)
