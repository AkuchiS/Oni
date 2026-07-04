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
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=180)


def _download_tarball(owner, repo, ref, dest):
    """git-less fallback: GitHub codeload tarball → extract into dest."""
    refs = [ref] if ref else ["HEAD", "main", "master"]
    ctx = ssl.create_default_context()
    last = None
    for r in refs:
        url = "https://codeload.github.com/%s/%s/tar.gz/%s" % (owner, repo, r)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "oni"})
            with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
                data = resp.read()
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
                members = tf.getmembers()
                top = members[0].name.split("/")[0] if members else ""
                _safe_extract(tf, dest)
            inner = os.path.join(dest, top)
            if os.path.isdir(inner):          # codeload wraps everything in a <repo>-<ref>/ dir
                return inner
            return dest
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            last = e
            continue
    raise RuntimeError("could not fetch %s/%s (no git, tarball failed: %s)" % (owner, repo, last))


def _safe_extract(tf, dest):
    """Extract, refusing any member that would escape dest (tar path-traversal guard)."""
    base = os.path.abspath(dest)
    for m in tf.getmembers():
        target = os.path.abspath(os.path.join(dest, m.name))
        if not (target == base or target.startswith(base + os.sep)):
            raise RuntimeError("unsafe path in tarball: %s" % m.name)
    tf.extractall(dest)


def resolve(source, cache_dir=None):
    """Resolve `source` to a local Target. Local paths win; otherwise fetch from GitHub."""
    if source and os.path.isdir(source):
        root = os.path.abspath(source)
        return Target(root=root, source=source, remote=False)

    owner = repo = ref = None
    m = _URL_RE.match(source.strip()) or _SHORT_RE.match(source.strip())
    if not m:
        raise ValueError(
            "don't understand target %r — give a local path, a GitHub URL, or owner/repo[@ref]" % source
        )
    owner, repo = m.group("owner"), m.group("repo")
    try:
        ref = m.group("ref")
    except IndexError:
        ref = None

    tmp = tempfile.mkdtemp(prefix="oni-") if not cache_dir else None
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
        dest = os.path.join(cache_dir, "%s__%s" % (owner, repo))
        if os.path.isdir(dest):
            shutil.rmtree(dest, ignore_errors=True)
    else:
        dest = os.path.join(tmp, repo)

    if _have_git():
        try:
            _clone(owner, repo, ref, dest)
            root = dest
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            # branch may not exist, or clone blocked — fall back to tarball
            shutil.rmtree(dest, ignore_errors=True)
            os.makedirs(dest, exist_ok=True)
            root = _download_tarball(owner, repo, ref, dest)
    else:
        os.makedirs(dest, exist_ok=True)
        root = _download_tarball(owner, repo, ref, dest)

    return Target(root=root, source=source, owner=owner, repo=repo, ref=ref, remote=True, tmp=tmp)
