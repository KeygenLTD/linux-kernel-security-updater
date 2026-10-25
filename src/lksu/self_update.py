"""Opt-in LKSU self-updater from integrity-checked GitHub Release wheel assets.

No git-main installs, unverified archives, or implicit kernel operations.
"""
import fcntl
import hashlib
import importlib.metadata
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import venv
from pathlib import Path
from urllib.parse import urlparse

from .core import LKSUError

RELEASE_API = "https://api.github.com/repos/KeygenLTD/linux-kernel-security-updater/releases/latest"
ROOT = Path("/opt/lksu")
BIN_DIR = Path("/usr/local/bin")
VERSION = re.compile(r"^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
DIGEST = re.compile(r"^sha256:([0-9a-fA-F]{64})$")
MAX_WHEEL_SIZE = 20 * 1024 * 1024


def version_tuple(version):
    match = VERSION.fullmatch(version)
    if not match:
        raise LKSUError("Invalid or unsupported LKSU release version")
    return tuple(int(x) for x in match.groups())


def installed_version():
    return "v" + importlib.metadata.version("lksu")


def _json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "LKSU-SelfUpdater/0.3", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=20) as response:
        if response.geturl() != url:
            raise LKSUError("Unexpected GitHub API redirect")
        data = response.read(2 * 1024 * 1024 + 1)
    if len(data) > 2 * 1024 * 1024:
        raise LKSUError("Release metadata exceeds safe size limit")
    return json.loads(data)


def release_info():
    release = _json(RELEASE_API)
    if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
        raise LKSUError("No eligible stable LKSU release")
    tag = release.get("tag_name", "")
    version_tuple(tag)
    filename = f"lksu-{tag[1:]}-py3-none-any.whl"
    matches = [
        a for a in release.get("assets", []) if isinstance(a, dict) and
        a.get("name") == filename and a.get("state") == "uploaded"
    ]
    if len(matches) != 1:
        raise LKSUError("Stable release has no unique wheel asset; refusing unverified update")
    asset = matches[0]
    match = DIGEST.fullmatch(asset.get("digest", ""))
    if not match:
        raise LKSUError("Release wheel has no GitHub-provided SHA-256 digest")
    url = asset.get("browser_download_url", "")
    expected = f"https://github.com/KeygenLTD/linux-kernel-security-updater/releases/download/{tag}/{filename}"
    if url != expected:
        raise LKSUError("Release download URL does not match the trusted repository")
    size = asset.get("size")
    if type(size) is not int or not 0 < size <= MAX_WHEEL_SIZE:
        raise LKSUError("Invalid release wheel size")
    return {"tag": tag, "url": url, "sha256": match.group(1).lower(), "size": size}


def _download(info, destination):
    req = urllib.request.Request(info["url"], headers={"User-Agent": "LKSU-SelfUpdater/0.3"})
    with urllib.request.urlopen(req, timeout=40) as response, destination.open("wb") as file:
        parsed = urlparse(response.geturl())
        if parsed.scheme != "https" or not parsed.hostname or (
            parsed.hostname != "github.com" and not parsed.hostname.endswith(".githubusercontent.com")
        ):
            raise LKSUError("Wheel download redirected to an untrusted host")
        digest = hashlib.sha256()
        received = 0
        for chunk in iter(lambda: response.read(64 * 1024), b""):
            received += len(chunk)
            if received > MAX_WHEEL_SIZE:
                raise LKSUError("Wheel download exceeded size limit")
            digest.update(chunk)
            file.write(chunk)
    if received != info["size"] or digest.hexdigest() != info["sha256"]:
        raise LKSUError("Release wheel SHA-256 or size mismatch; installation aborted")


def _cmd(*args):
    try:
        p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=180)
    except subprocess.TimeoutExpired as exc:
        raise LKSUError("Self-update command timed out") from exc
    if p.returncode:
        raise LKSUError(f"Self-update command failed: {args[0]}: {p.stderr.strip()[:400]}")
    return p.stdout


def _activate_release(target):
    """Switch the release pointer and executable wrappers, restoring on failure."""
    current = ROOT / "current"
    previous = os.readlink(current) if current.is_symlink() else None
    commands = ("lksu", "lksu-fleet")
    old_wrappers = {}
    for command in commands:
        executable = BIN_DIR / command
        if executable.is_symlink():
            old_wrappers[command] = ("link", os.readlink(executable))
        elif executable.exists():
            backup = ROOT / "legacy" / command
            backup.parent.mkdir(parents=True, exist_ok=True)
            if not backup.exists():
                shutil.copy2(executable, backup)
            old_wrappers[command] = ("file", str(backup))
        else:
            old_wrappers[command] = ("missing", "")
    def link_atomically(path, destination):
        temp = path.with_name(path.name + ".lksu-new")
        if temp.is_symlink():
            temp.unlink()
        os.symlink(str(destination), temp)
        os.replace(temp, path)
    try:
        link_atomically(current, target)
        for command in commands:
            link_atomically(BIN_DIR / command, current / "bin" / command)
        _cmd(str(BIN_DIR / "lksu"), "--help")
    except (LKSUError, OSError, subprocess.SubprocessError):
        if previous:
            link_atomically(current, previous)
        elif current.is_symlink():
            current.unlink()
        for command in commands:
            path = BIN_DIR / command
            kind, destination = old_wrappers[command]
            if kind == "link":
                link_atomically(path, destination)
            elif kind == "file":
                if path.is_symlink():
                    path.unlink()
                shutil.copy2(destination, path)
            elif path.is_symlink():
                path.unlink()
        raise


def check():
    current = installed_version()
    try:
        info = release_info()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {"status": "self-update-no-release", "installed_version": current}
        raise
    newer = version_tuple(info["tag"]) > version_tuple(current)
    return {"status": "self-update-available" if newer else "self-update-current",
            "installed_version": current, "release_version": info["tag"],
            "update_available": newer}


def update(*, automatic=False, enabled=False):
    if automatic and not enabled:
        return {"status": "self-update-disabled", "installed_version": installed_version()}
    if os.geteuid() != 0:
        raise LKSUError("Root privileges are required for LKSU self-update")
    ROOT.mkdir(parents=True, exist_ok=True)
    with open(ROOT / ".self-update.lock", "a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise LKSUError("Another LKSU self-update is running") from exc
        current = installed_version()
        try:
            info = release_info()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return {"status": "self-update-no-release", "installed_version": current}
            raise
        if version_tuple(info["tag"]) <= version_tuple(current):
            return {"status": "self-update-current", "installed_version": current, "release_version": info["tag"]}
        stage_root = ROOT / "releases"
        stage_root.mkdir(parents=True, exist_ok=True)
        target = stage_root / info["tag"]
        if target.exists():
            raise LKSUError("Release directory already exists; manual investigation required")
        with tempfile.TemporaryDirectory(prefix=".lksu-update-", dir=str(ROOT)) as temporary:
            wheel = Path(temporary) / f"lksu-{info['tag'][1:]}-py3-none-any.whl"
            _download(info, wheel)
            candidate = Path(temporary) / "venv"
            venv.EnvBuilder(with_pip=True, clear=False).create(str(candidate))
            _cmd(str(candidate / "bin" / "python"), "-m", "pip", "install",
                 "--no-index", "--no-deps", "--disable-pip-version-check", str(wheel))
            observed = _cmd(str(candidate / "bin" / "python"), "-c",
                            "import importlib.metadata; print(importlib.metadata.version('lksu'))").strip()
            if observed != info["tag"][1:]:
                raise LKSUError("Installed LKSU version does not match the release")
            _cmd(str(candidate / "bin" / "lksu"), "--help")
            os.replace(candidate, target)
        _activate_release(target)
        return {"status": "self-updated", "previous_version": current,
                "installed_version": info["tag"], "previous_release_retained": True,
                "rebooted": False}
