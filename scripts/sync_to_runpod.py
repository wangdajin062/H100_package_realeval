#!/usr/bin/env python3
"""Sync local workspace files to RunPod Jupyter workspace via Contents API.

Usage:
  python scripts/sync_to_runpod.py --base-url https://xxxx.proxy.runpod.net --token TOKEN \
      --local-root d:/Projects/H100_package_realeval --remote-root /workspace/H100_package_realeval --dry-run

  python scripts/sync_to_runpod.py --base-url ... --token ...

Notes:
- This script uploads/overwrites selected files only; it does not delete remote files.
- Excludes large/generated folders by default (data/, outputs/, .git/, .venv/...).
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import posixpath
import time
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_EXCLUDE_DIRS = {
    ".git",
    ".vscode",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ipynb_checkpoints",
    "node_modules",
    "data",
    "outputs",
}

DEFAULT_EXCLUDE_SUFFIX = {
    ".pt",
    ".pth",
    ".bin",
    ".safetensors",
    ".npy",
    ".npz",
    ".ckpt",
    ".tar",
    ".zip",
    ".7z",
    ".log",
}


class RunpodSync:
    def __init__(self, base_url: str, token: str, timeout: int = 60):
        self.base = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.headers = {
            "User-Agent": "runpod-sync/1.0",
            "Accept": "application/json,text/plain,*/*",
            "Content-Type": "application/json",
            "Referer": f"{self.base}/lab",
        }

    def _api_url(self, remote_path: str) -> str:
        quoted = urllib.parse.quote(remote_path, safe="/")
        q = urllib.parse.urlencode({"token": self.token})
        return f"{self.base}/api/contents{quoted}?{q}"

    def _request(self, method: str, remote_path: str, body: dict | None = None) -> dict:
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            self._api_url(remote_path),
            data=data,
            headers=self.headers,
            method=method,
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            raw = r.read()
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8"))

    def ensure_directory(self, remote_dir: str) -> None:
        try:
            self._request("GET", remote_dir)
            return
        except Exception:
            pass
        self._request("PUT", remote_dir, {"type": "directory"})

    def upload_file(self, local_file: Path, remote_file: str, retries: int = 2) -> None:
        b = local_file.read_bytes()
        payload = {
            "type": "file",
            "format": "base64",
            "mimetype": mimetypes.guess_type(str(local_file))[0] or "application/octet-stream",
            "content": base64.b64encode(b).decode("ascii"),
        }
        err = None
        for i in range(retries + 1):
            try:
                self._request("PUT", remote_file, payload)
                return
            except Exception as e:  # noqa: BLE001
                err = e
                time.sleep(0.8 + i)
        raise RuntimeError(f"upload failed: {local_file} -> {remote_file}: {err}")


def should_exclude(path: Path, root: Path, exclude_dirs: set[str], exclude_suffix: set[str]) -> bool:
    # Jupyter Contents API returns HTTP 400 for dotfiles
    if path.name.startswith("."):
        return True
    rel = path.relative_to(root)
    for part in rel.parts:
        if part in exclude_dirs:
            return True
    if path.is_file() and path.suffix.lower() in exclude_suffix:
        return True
    return False


def gather_files(root: Path, exclude_dirs: set[str], exclude_suffix: set[str], max_mb: int) -> list[Path]:
    files: list[Path] = []
    max_bytes = max_mb * 1024 * 1024
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if should_exclude(p, root, exclude_dirs, exclude_suffix):
            continue
        if p.stat().st_size > max_bytes:
            continue
        files.append(p)
    return files


def main() -> int:
    ap = argparse.ArgumentParser(description="Sync local files to RunPod Jupyter workspace")
    ap.add_argument("--base-url", required=True, help="RunPod proxy base URL, e.g. https://xxxx.proxy.runpod.net")
    ap.add_argument("--token", required=True, help="Jupyter token")
    ap.add_argument("--local-root", default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument("--remote-root", default="/workspace/H100_package_realeval")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-file-mb", type=int, default=20)
    args = ap.parse_args()

    local_root = Path(args.local_root).resolve()
    remote_root = args.remote_root.rstrip("/")

    sync = RunpodSync(args.base_url, args.token)

    files = gather_files(
        local_root,
        exclude_dirs=set(DEFAULT_EXCLUDE_DIRS),
        exclude_suffix=set(DEFAULT_EXCLUDE_SUFFIX),
        max_mb=args.max_file_mb,
    )
    total = len(files)
    print(f"[scan] local_root={local_root}")
    print(f"[scan] candidate files={total}")

    if args.dry_run:
        for i, f in enumerate(files[:80], 1):
            rel = f.relative_to(local_root).as_posix()
            print(f"[dry] {i}/{total} {rel}")
        if total > 80:
            print(f"[dry] ... and {total - 80} more")
        return 0

    ok, fail = 0, 0
    for i, f in enumerate(files, 1):
        rel = f.relative_to(local_root).as_posix()
        remote_file = posixpath.join(remote_root, rel)
        remote_dir = posixpath.dirname(remote_file)
        try:
            sync.ensure_directory(remote_dir)
            sync.upload_file(f, remote_file)
            ok += 1
            if i % 20 == 0 or i == total:
                print(f"[sync] {i}/{total} ok={ok} fail={fail}")
        except Exception as e:  # noqa: BLE001
            fail += 1
            print(f"[fail] {rel}: {e}")

    print("=" * 72)
    print(f"DONE total={total} ok={ok} fail={fail}")
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
