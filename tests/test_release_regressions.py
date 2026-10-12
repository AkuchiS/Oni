import io
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest
from oni import acquire, fingerprint, graphmap, llm, pipeline, report
from oni.mcp import Server, local_lexical

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/tinyrepo"


def forbidden(*args, **kwargs):
    raise AssertionError("unexpected filesystem/network operation")


@pytest.mark.parametrize("target", ["gh:x/..", "gh:x/.", "https://github.com/x/..",
                                    "https://github.com/x/y\\..\\..\\outside",
                                    "https://github.com/x\\outside/repo"])
def test_invalid_repo_cannot_create_or_delete_directories(monkeypatch, tmp_path, target):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(acquire.tempfile, "mkdtemp", forbidden)
    monkeypatch.setattr(acquire.shutil, "rmtree", forbidden)
    with pytest.raises(ValueError):
        acquire.resolve(target)


def test_cache_acquisition_preserves_existing_work(monkeypatch, tmp_path):
    old = tmp_path / "x__repo"
    old.mkdir(); (old / "keep").write_text("user data")
    def clone(owner, repo, ref, dest):
        Path(dest).mkdir()
        (Path(dest) / "README.md").write_text("new clone")
    monkeypatch.setattr(acquire, "_have_git", lambda: True)
    monkeypatch.setattr(acquire, "_clone", clone)
    first = acquire.resolve("gh:x/repo", cache_dir=str(tmp_path))
    second = acquire.resolve("gh:x/repo", cache_dir=str(tmp_path))
    assert first.root != second.root
    assert (old / "keep").read_text() == "user data"
    assert Path(first.root).is_dir()


def test_failed_acquisition_cleans_only_its_own_directory(monkeypatch, tmp_path):
    keep = tmp_path / "keep"
    keep.write_text("user data")
    monkeypatch.setattr(acquire, "_have_git", lambda: False)
    def fail(*args):
        raise RuntimeError("failed fetch")
    monkeypatch.setattr(acquire, "_download_tarball", fail)
    with pytest.raises(RuntimeError):
        acquire.resolve("gh:x/repo", cache_dir=str(tmp_path))
    assert list(tmp_path.iterdir()) == [keep]


def test_archive_size_limit_before_writes(monkeypatch, tmp_path):
    monkeypatch.setattr(acquire, "MAX_EXTRACT_BYTES", 1)
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w") as archive:
        member = tarfile.TarInfo("repo/file")
        member.size = 2
        archive.addfile(member, io.BytesIO(b"ok"))
    data.seek(0)
    with tarfile.open(fileobj=data) as archive:
        with pytest.raises(RuntimeError, match="limits"):
            acquire._safe_extract(archive, str(tmp_path))
    assert not list(tmp_path.iterdir())


@pytest.fixture
def clean_model_env(monkeypatch):
    for name in ("ONI_ENDPOINT", "ONI_API_KEY", "ONI_NO_LLM", "OPENAI_API_KEY",
                 "OPENAI_BASE_URL", "OPENAI_API_BASE", "ONI_MODEL", "OPENAI_MODEL"):
        monkeypatch.delenv(name, raising=False)


def test_default_analysis_does_not_use_ambient_model(monkeypatch, clean_model_env):
    monkeypatch.setenv("OPENAI_API_KEY", "placeholder")
    monkeypatch.setattr(llm, "available", forbidden)
    assert pipeline.teardown(str(FIXTURE))["teardown"]["_model"] is None


def test_opt_in_reaches_model_and_offline_overrides(monkeypatch, clean_model_env):
    seen = []
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "complete", lambda *a, **kw: seen.append(True) or None)
    pipeline.teardown(str(FIXTURE), use_llm=True)
    assert len(seen) == 2
    pipeline.teardown(str(FIXTURE), use_llm=True, offline=True)
    assert len(seen) == 2


def test_oni_endpoint_cannot_receive_generic_key(monkeypatch, clean_model_env):
    monkeypatch.setenv("ONI_ENDPOINT", "https://other.example/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "generic-placeholder")
    assert llm._key() == ""
    assert not llm.available()


@pytest.mark.parametrize("url, key, available", [
    ("http://127.0.0.1:11434/v1", "", True),
    ("http://127.0.0.1:11434/v1", "placeholder", False),
    ("http://remote.example/v1", "placeholder", False),
    ("https://ollama.example:8000/v1", "", False),
    ("https://api.example/v1", "placeholder", True),
])
def test_model_transport_boundary(monkeypatch, clean_model_env, url, key, available):
    monkeypatch.setenv("ONI_ENDPOINT", url)
    monkeypatch.setenv("ONI_API_KEY", key)
    assert llm.available() is available


def test_model_redirects_are_not_followed():
    assert llm._NoRedirect().redirect_request(None, None, 302, None, {}, "https://other.example") is None


@pytest.mark.parametrize("path", ["\\\\host\\share\\repo", "\\\\?\\C:\\repo", "//host/share/repo"])
def test_network_paths_rejected_before_filesystem(monkeypatch, path):
    monkeypatch.setattr(os.path, "abspath", forbidden)
    with pytest.raises(ValueError):
        local_lexical(path)


def test_outside_mcp_path_rejected_before_realpath(monkeypatch, tmp_path):
    allowed = tmp_path / "allowed"; allowed.mkdir()
    server = Server([str(allowed)])
    monkeypatch.setattr(os.path, "realpath", forbidden)
    with pytest.raises(ValueError):
        server.analyze({"path": str(tmp_path / "outside")})


def test_analysis_error_preserves_request_id(monkeypatch):
    server = Server([str(FIXTURE)]); server.ready = True
    def fail(*args, **kwargs):
        raise KeyError("private detail")
    monkeypatch.setattr(pipeline, "teardown", fail)
    response = server.handle({"jsonrpc": "2.0", "id": 37, "method": "tools/call",
                              "params": {"name": "analyze_repository", "arguments": {"path": str(FIXTURE)}}})
    assert response["id"] == 37 and response["result"]["isError"]
    assert "private detail" not in json.dumps(response)


def test_graph_includes_core_cluster():
    result = graphmap.build(fingerprint.fingerprint(str(FIXTURE)))
    assert any(c["dir"] == "core" for c in result["clusters"])
    assert all("\\" not in f["path"] for f in result["files"])


def test_ast_resource_error_degrades(monkeypatch):
    def fail(*args):
        raise MemoryError()
    monkeypatch.setattr(graphmap.ast, "parse", fail)
    assert graphmap._py_defs("def sample(): pass") == {}


def test_ranking_ties_stable_across_processes(tmp_path):
    (tmp_path / "a.py").write_text("def shared_symbol(): return 1")
    (tmp_path / "b.py").write_text("def shared_symbol(): return 2")
    (tmp_path / "entry.py").write_text("def entry(): return shared_symbol()")
    code = 'import json,sys; from oni import graphmap,fingerprint; print(json.dumps(graphmap.build(fingerprint.fingerprint(sys.argv[1]))["symbols"],sort_keys=True))'
    outputs = [subprocess.check_output([sys.executable, "-c", code, str(tmp_path)],
                env=dict(os.environ, PYTHONHASHSEED=str(seed)), text=True) for seed in (1, 17, 93)]
    assert outputs[0] == outputs[1] == outputs[2]


def test_excerpt_backticks_remain_fenced():
    result = pipeline.teardown(str(FIXTURE), offline=True)
    result["jewels"][0]["excerpt"] = "```\n![remote](https://example.invalid/image)"
    text = report.to_markdown(result)
    assert "````python\n```\n![remote]" in text
    assert "https://example.invalid/image)\n````" in text


@pytest.mark.parametrize("target", ["gh:x/repo@../../other/evil/tar.gz/main",
    "gh:x/repo@-bad", "https://github.com/x/repo/tree/main?other=1",
    "https://github.com/x/repo/tree/%2e%2e", "gh:x/repo@a//b", "gh:x/repo@a.lock"])
def test_invalid_ref_rejected_before_acquisition(monkeypatch, target):
    monkeypatch.setattr(acquire.tempfile, "mkdtemp", forbidden)
    with pytest.raises(ValueError):
        acquire.resolve(target)


@pytest.mark.parametrize("name", ["repo/CON", "repo/aux.txt", "repo/COM1", "repo/file."])
def test_archive_rejects_windows_reserved_names(tmp_path, name):
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w") as archive:
        archive.addfile(tarfile.TarInfo(name))
    data.seek(0)
    with tarfile.open(fileobj=data) as archive:
        with pytest.raises(RuntimeError):
            acquire._safe_extract(archive, str(tmp_path))


@pytest.mark.parametrize("payload", [[], {}, {"choices": []},
    {"choices": [{"message": {"content": []}}]},
    {"choices": [{"message": {"content": "valid response"}}]}])
def test_model_response_shapes_and_loopback_proxy_bypass(monkeypatch, clean_model_env, payload):
    monkeypatch.setenv("ONI_ENDPOINT", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.example:8080")
    seen = []
    class Opener:
        def open(self, *args, **kwargs):
            return io.BytesIO(json.dumps(payload).encode())
    def build(*handlers):
        seen.extend(handlers)
        return Opener()
    monkeypatch.setattr(llm.urllib.request, "build_opener", build)
    result = llm.complete("public test fixture")
    expected = "valid response" if payload == {"choices": [{"message": {"content": "valid response"}}]} else None
    assert result == expected
    assert any(isinstance(h, llm.urllib.request.ProxyHandler) and h.proxies == {} for h in seen)


def test_model_truncated_response_degrades(monkeypatch, clean_model_env):
    monkeypatch.setenv("ONI_ENDPOINT", "http://127.0.0.1:11434/v1")
    class Opener:
        def open(self, *args, **kwargs):
            raise llm.http.client.IncompleteRead(b"partial")
    monkeypatch.setattr(llm.urllib.request, "build_opener", lambda *args: Opener())
    assert llm.complete("public fixture") is None


def test_explicit_symlinked_root_alias_is_usable(tmp_path):
    alias = tmp_path / "approved-alias"
    try:
        alias.symlink_to(FIXTURE, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation unavailable")
    result = Server([str(alias)]).analyze({"path": str(alias)})
    assert not result["isError"]
    assert json.loads(result["content"][0]["text"])["target"] == "tinyrepo"


def test_fingerprint_sees_github_workflows(tmp_path):
    workflow = tmp_path / ".github/workflows/ci.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: test")
    assert fingerprint.fingerprint(str(tmp_path))["signals"]["ci"]


def test_metadata_links_are_skipped_before_following_stat(monkeypatch, tmp_path):
    root = tmp_path / "repo"; root.mkdir()
    outside = tmp_path / "outside"; outside.mkdir()
    (outside / "content").write_text("private")
    try:
        (root / "README.md").symlink_to(outside / "content")
        (root / "pyproject.toml").symlink_to(outside / "content")
        (root / "nested").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation unavailable")
    original_dir, original_file = os.path.isdir, os.path.isfile
    def guarded(check):
        def call(path):
            if os.path.islink(path):
                raise AssertionError("followed metadata symlink before checking it")
            return check(path)
        return call
    monkeypatch.setattr(os.path, "isdir", guarded(original_dir))
    monkeypatch.setattr(os.path, "isfile", guarded(original_file))
    result = fingerprint.fingerprint(str(root))
    assert not result["readme"] and not result["manifests"]


@pytest.mark.parametrize("target", ["gh:x/..", "gh:x/repo", "https://github.com/x/repo",
                                    "github.com:x/..", "www.github.com:x/.."])
def test_explicit_remote_offline_never_probes_local_path(monkeypatch, target):
    monkeypatch.setattr(acquire.os.path, "isdir", forbidden)
    with pytest.raises(ValueError, match="offline mode"):
        acquire.resolve(target, offline=True)


@pytest.mark.parametrize("target", ["gh:x/..", "github.com:x/..", "www.github.com:x/.."])
def test_malformed_remote_rejected_even_if_platform_reports_directory(monkeypatch, target):
    monkeypatch.setattr(acquire.os.path, "isdir", lambda path: True)
    monkeypatch.setattr(acquire.tempfile, "mkdtemp", forbidden)
    monkeypatch.setattr(acquire.shutil, "rmtree", forbidden)
    with pytest.raises(ValueError, match="invalid GitHub"):
        acquire.resolve(target)
