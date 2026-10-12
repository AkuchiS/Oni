"""Offline and filesystem boundaries exercised without real network calls."""
import io
import json
import os
import tarfile
from pathlib import Path

import pytest
from oni import acquire, cli, fingerprint, llm, pipeline, util

FIXTURE = str(Path(__file__).resolve().parents[1] / "fixtures" / "tinyrepo")


def forbidden(*args, **kwargs):
    raise AssertionError("offline mode attempted network/model work")


def test_offline_rejects_remote_before_acquisition(monkeypatch):
    monkeypatch.setattr(acquire, "_clone", forbidden)
    monkeypatch.setattr(acquire, "_download_tarball", forbidden)
    with pytest.raises(ValueError, match="existing local directory"):
        pipeline.teardown("psf/requests", offline=True)


def test_offline_ignores_configured_model(monkeypatch):
    monkeypatch.setenv("ONI_API_KEY", "test-placeholder")
    monkeypatch.delenv("ONI_NO_LLM", raising=False)
    monkeypatch.setattr(llm, "available", forbidden)
    monkeypatch.setattr(llm, "complete", forbidden)
    result = pipeline.teardown(FIXTURE, offline=True)
    assert result["teardown"]["_model"] is None
    assert result["jewels"]


def test_no_llm_does_not_change_environment(monkeypatch, capsys):
    monkeypatch.delenv("ONI_NO_LLM", raising=False)
    monkeypatch.setattr(llm, "available", forbidden)
    assert cli.main([FIXTURE, "--no-llm", "--json"]) == 0
    assert "ONI_NO_LLM" not in os.environ
    assert json.loads(capsys.readouterr().out)["target"] == "tinyrepo"


def test_cli_offline_remote_error(capsys):
    assert cli.main(["psf/requests", "--offline"]) == 1
    captured = capsys.readouterr()
    assert not captured.out
    assert "existing local directory" in captured.err


@pytest.mark.parametrize("kind", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE])
def test_archive_rejects_links_and_special_files(tmp_path, kind):
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w") as archive:
        member = tarfile.TarInfo("repo/escape")
        member.type = kind
        member.linkname = "../../outside"
        archive.addfile(member)
    data.seek(0)
    with tarfile.open(fileobj=data) as archive:
        with pytest.raises(RuntimeError, match="unsafe member"):
            acquire._safe_extract(archive, str(tmp_path))
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("name", ["../outside", "/outside", "C:/outside", "repo\\..\\outside"])
def test_archive_rejects_traversal(tmp_path, name):
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w") as archive:
        archive.addfile(tarfile.TarInfo(name))
    data.seek(0)
    with tarfile.open(fileobj=data) as archive:
        with pytest.raises(RuntimeError):
            acquire._safe_extract(archive, str(tmp_path))


def test_archive_regular_file(tmp_path):
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w") as archive:
        member = tarfile.TarInfo("repo/file.txt")
        member.size = 2
        archive.addfile(member, io.BytesIO(b"ok"))
    data.seek(0)
    with tarfile.open(fileobj=data) as archive:
        acquire._safe_extract(archive, str(tmp_path))
    assert (tmp_path / "repo/file.txt").read_text() == "ok"


def test_source_symlinks_are_not_read(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.py").write_text("SECRET_MARKER = 1")
    (outside / "pyproject.toml").write_text('[project]\nname = "private"')
    root = tmp_path / "repo"
    root.mkdir()
    try:
        (root / "linked.py").symlink_to(outside / "secret.py")
        (root / "linked_dir").symlink_to(outside, target_is_directory=True)
        (root / "README.md").symlink_to(outside / "secret.py")
    except OSError:
        pytest.skip("symlink creation unavailable")
    assert not list(util.walk_source(str(root)))
    assert util.read_text(root / "linked.py") == ""
    result = fingerprint.fingerprint(str(root))
    assert not result["manifests"]
    assert not result["readme"]
