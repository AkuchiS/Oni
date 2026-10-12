"""
Stage 1 — acquire: turn whatever the user pointed at into a local directory on disk.

Accepts, in order of preference:
  · a local path (used in place, never modified)
  · a full URL            https://github.com/owner/repo[.git][/tree/ref]
  · a shorthand           owner/repo[@ref]   or   gh:owner/repo

Remote targets are shallow-cloned (``git clone --depth 1``) into a cache dir. If git isn't
available we fall back to downloading GitHub's codeload tarball over stdlib urllib — so oni
works on a box with no git at all. Everything is read-only w.r.t. the target.
"""
import os
import re
import io
import ssl
import shutil
import tarfile
import tempfile
import subprocess
import urllib.request
import urllib.error
import urllib.parse

_URL_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?github\.com[:/]+(?P<owner>[^/]+)/(?P<repo>[^/#]+?)"
    r"(?:\.git)?(?:/tree/(?P<ref>[^/#]+))?/?$",
    re.I,
)
_SHORT_RE = re.compile(r"^(?:gh:)?(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:@(?P<ref>[\w./-]+))?$")


class Target:
    """A resolved acquisition: where the code is, and where it came from."""

    def __init__(self, root, source, owner=None, repo=None, ref=None, remote=False, tmp=None):
        self.root = root            # local dir containing the source
        self.source = source        # the string the user gave us
        self.owner = owner
        self.repo = repo
        self.ref = ref
        self.remote = remote        # True if we fetched it (so the caller may clean up)
        self.tmp = tmp              # tempdir to remove on cleanup, or None

    @property
    def slug(self):
        if self.owner and self.repo:
            return "%s/%s" % (self.owner, self.repo)
        return os.path.basename(os.path.normpath(self.root))

    def cleanup(self):
        if self.tmp and os.path.isdir(self.tmp):
            shutil.rmtree(self.tmp, ignore_errors=True)


def _have_git():
    return shutil.which("git") is not None


def _clone(owner, repo, ref, dest):
    url = "https://github.com/%s/%s.git" % (owner, repo)
    cmd = ["git", "clone", "--depth", "1", "--quiet"]
    if ref:
        cmd += ["--branch", ref]
    cmd += [url, dest]
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                   stderr=subprocess.PIPE, timeout=180, env=env)


MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024
MAX_EXTRACT_BYTES = 200 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 20000


def _download_tarball(owner, repo, ref, dest):
    """Download a bounded archive; retry missing default refs, never partial extraction."""
    refs = [ref] if ref else ["HEAD", "main", "master"]
    ctx = ssl.create_default_context()
    last = None
    for r in refs:
        url = "https://codeload.github.com/%s/%s/tar.gz/%s" % (owner, repo, urllib.parse.quote(r, safe=""))
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "oni"})
            with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
                data = resp.read(MAX_DOWNLOAD_BYTES + 1)
        except urllib.error.URLError as exc:
            last = exc
            continue
        if len(data) > MAX_DOWNLOAD_BYTES:
            raise RuntimeError("archive exceeds the 50 MiB download limit")
        try:
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
                top = _safe_extract(tf, dest)
        except (tarfile.TarError, EOFError, OSError) as exc:
            raise RuntimeError("invalid or unreadable repository archive") from exc
        inner = os.path.join(dest, top)
        return inner if os.path.isdir(inner) else dest
    raise RuntimeError("could not fetch %s/%s: %s" % (owner, repo, last))


def _safe_extract(tf, dest):
    """Validate a bounded set of regular files/directories before writing anything."""
    base = os.path.realpath(dest)
    members, total = [], 0
    for m in tf:
        total += m.size
        if len(members) >= MAX_ARCHIVE_MEMBERS or total > MAX_EXTRACT_BYTES or m.size < 0:
            raise RuntimeError("archive exceeds extraction limits")
        parts = m.name.rstrip("/").split("/")
        reserved = any(re.fullmatch(r"CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³]",
                                   part.split(".")[0], re.I) or part.endswith((" ", "."))
                       for part in parts)
        target = os.path.realpath(os.path.join(base, m.name))
        if (not (target == base or target.startswith(base + os.sep))
                or "\\" in m.name or ":" in m.name
                or reserved or not (m.isfile() or m.isdir())):
            raise RuntimeError("unsafe member in tarball: %s" % m.name)
        members.append(m)
    for m in members:
        target = os.path.join(base, m.name)
        if m.isdir():
            os.makedirs(target, exist_ok=True)
        else:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with tf.extractfile(m) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
    return members[0].name.split("/")[0] if members else ""


def resolve(source, cache_dir=None, offline=False):
    """Use local paths in place, or acquire into a fresh invocation-owned directory."""
    if source and os.path.isdir(source):
        return Target(root=os.path.abspath(source), source=source, remote=False)
    if offline:
        raise ValueError("offline mode requires an existing local directory; remote acquisition is disabled")
    m = (_URL_RE.match(source.strip()) or _SHORT_RE.match(source.strip())) if isinstance(source, str) else None
    if not m:
        raise ValueError("give a local path, a GitHub URL, or owner/repo[@ref]")
    owner, repo, ref = m.group("owner"), m.group("repo"), m.group("ref")
    if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", owner)
            or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", repo) or repo in (".", "..")):
        raise ValueError("invalid GitHub owner or repository name")
    if ref and (not re.fullmatch(r"[\w][\w./-]{0,254}", ref) or ".." in ref or "//" in ref
                or any(part.startswith(".") or part.endswith((".", ".lock")) for part in ref.split("/"))
                or ref.endswith("/")):
        raise ValueError("invalid or unsupported GitHub branch/tag reference")
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
    # Neither the target name nor a previous cached checkout is ever a deletion target.
    owned = tempfile.mkdtemp(prefix="oni-", dir=cache_dir)
    dest = os.path.join(owned, "source")
    if os.path.dirname(os.path.realpath(dest)) != os.path.realpath(owned):
        raise RuntimeError("acquisition directory escaped its owned parent")
    try:
        if _have_git():
            try:
                _clone(owner, repo, ref, dest)
                root = dest
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                shutil.rmtree(dest, ignore_errors=True)  # created only by this invocation
                os.makedirs(dest)
                root = _download_tarball(owner, repo, ref, dest)
        else:
            os.makedirs(dest)
            root = _download_tarball(owner, repo, ref, dest)
    except Exception:
        shutil.rmtree(owned, ignore_errors=True)
        raise
    return Target(root=root, source=source, owner=owner, repo=repo, ref=ref,
                  remote=True, tmp=None if cache_dir else owned)
