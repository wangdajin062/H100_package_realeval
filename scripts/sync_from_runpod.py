#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_from_runpod.py — 把 RunPod 容器文件经 base64-PTY 拉回本地。

RunPod 代理不支持 scp/sftp（scp -O 静默失败），只能开一条 ssh -tt 伪终端，
远端 base64 输出、本地解码后写盘。要点：
  - 远端先 `stty -echo` 关回显、设 cols 400，避免 76 字符 base64 行被终端重排；
  - GNU coreutils `base64` 默认按 76 字符分行，本地合并解码（base64 忽略换行）；
  - 大文件按块 `dd | base64` 分次传输，每块独立连接，结束后比对 sha256。

用法:
  python scripts/sync_from_runpod.py pull <remote> <local>
  python scripts/sync_from_runpod.py sha256 <remote>      # 打印远端 sha256
"""
import hashlib
import os
import re
import subprocess
import sys
import time

POD = "mhypfkvge474n8-64411fb1@ssh.runpod.io"
KEY = os.path.expanduser("~/.ssh/id_ed25519")
CHUNK_MB = int(os.environ.get("SYNC_CHUNK_MB", "8"))   # 大文件每块二进制大小，可用环境变量覆盖
ANSI_RE = re.compile(rb"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07|\x1b[=>]")


def ssh_run(cmd):
    """开一条 ssh -tt，把命令喂进 stdin，返回过滤后的 stdout 字节。

    RunPod 代理给的远端 shell 执行完不会自己退出，必须末尾 `; exit`
    让连接关闭、stdout 才出 EOF，read() 才能返回。
    """
    proc = subprocess.Popen(
        ["ssh", "-tt", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20",
         "-o", "StrictHostKeyChecking=accept-new", "-o", "ServerAliveInterval=15",
         "-o", "ServerAliveCountMax=4", "-i", KEY, POD],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    try:
        proc.stdin.write((cmd + "\nexit\n").encode())
        proc.stdin.flush()
        proc.stdin.close()   # RunPod 代理需 stdin EOF 才开始转发执行
    except Exception as e:
        proc.terminate()
        raise RuntimeError("SSH 写入失败: %s" % e)
    try:
        out = proc.stdout.read()
    except Exception:
        out = b""
    try:
        proc.wait(timeout=120)
    except subprocess.TimeoutExpired:
        proc.terminate()
    out = ANSI_RE.sub(b"", out)
    out = out.replace(b"\r", b"\n")
    return out


def remote_bytes(cmd, marker_in=b"B64IN", marker_out=b"B64OUT"):
    """执行命令并抽出两个标记行之间的字节（合并为一个字节串，去掉换行）。"""
    full = ssh_run(f"stty -echo 2>/dev/null; export PS1=''; stty cols 400 rows 50 2>/dev/null; "
                   f"echo {marker_in.decode()}; {cmd}; echo {marker_out.decode()}")
    lines = full.split(b"\n")
    start = end = None
    for i, ln in enumerate(lines):
        if ln.strip() == marker_in and start is None:
            start = i + 1
        elif ln.strip() == marker_out and start is not None:
            end = i
            break
    if start is None or end is None or end <= start:
        # 调试：打印原始输出前 500 字节
        print("[DEBUG] 未找到标记，原始输出前 500B:", full[:500], file=sys.stderr)
        raise RuntimeError("远程命令输出中未找到 B64IN/B64OUT 标记")
    body = b"".join(lines[start:end])
    return body


def remote_sha256(path):
    """远端文件 sha256（十六进制字符串）。"""
    out = ssh_run(f"sha256sum {path} 2>/dev/null; echo HASH_DONE")
    m = re.search(rb"([0-9a-f]{64})\s+", out)
    if not m:
        raise RuntimeError("未取到远端 sha256: %s" % path)
    return m.group(1).decode()


def remote_size(path):
    out = ssh_run(f"stat -c %s {path} 2>/dev/null; echo SIZE_DONE")
    m = re.search(rb"(?m)^\s*(\d+)\s*$", out)
    if not m:
        raise RuntimeError("未取到远端文件大小: %s" % path)
    return int(m.group(1))


def b64decode_strip(body):
    body = re.sub(rb"[^A-Za-z0-9+/=]", b"", body)
    return base64_decode(body)


def base64_decode(b):
    import base64
    # 补齐 padding（base64 合并后可能整体 padding 正确，逐行 padding 会被忽略）
    b = re.sub(rb"[^A-Za-z0-9+/=]", b"", b)
    return base64.b64decode(b + b"=" * (-len(b) % 4))


def pull_file(remote, local, verify=True):
    size = remote_size(remote)
    print("== %s (%d bytes) -> %s" % (remote, size, local))
    os.makedirs(os.path.dirname(os.path.abspath(local)), exist_ok=True)

    if size <= CHUNK_MB * 1024 * 1024:
        t0 = time.time()
        body = remote_bytes(f"base64 {remote} 2>/dev/null")
        data = base64_decode(body)
        with open(local, "wb") as f:
            f.write(data)
        dt = time.time() - t0
        print("   拉取 %d bytes，耗时 %.1fs（%.1f MB/s）" % (len(data), dt, len(data) / dt / 1e6))
    else:
        n_chunks = (size + CHUNK_MB * 1024 * 1024 - 1) // (CHUNK_MB * 1024 * 1024)
        print("   大文件，分 %d 块 × %dMB 拉取" % (n_chunks, CHUNK_MB))
        with open(local, "wb") as f:
            for ci in range(n_chunks):
                for attempt in range(3):
                    try:
                        t0 = time.time()
                        body = remote_bytes(
                            f"dd if={remote} bs={CHUNK_MB}M skip={ci} count=1 2>/dev/null | base64")
                        data = base64_decode(body)
                        f.write(data)
                        f.flush()
                        break
                    except Exception as e:
                        if attempt == 2:
                            raise
                        print("   块 %d/%d 失败（第 %d 次重试）: %s" % (ci + 1, n_chunks, attempt + 1, e))
                        time.sleep(2)
                dt = time.time() - t0
                got = ci * CHUNK_MB * 1024 * 1024 + len(data)
                print("   块 %d/%d: %d bytes (%.1f MB/s, 累计 %d/%d)"
                      % (ci + 1, n_chunks, len(data), len(data) / dt / 1e6, got, size))

    if verify:
        lh = hashlib.sha256(open(local, "rb").read()).hexdigest()
        rh = remote_sha256(remote)
        if lh == rh:
            print("   [OK] sha256 match: %s" % lh)
        else:
            print("   [FAIL] sha256 mismatch! local=%s remote=%s" % (lh, rh), file=sys.stderr)
            return False
    return True


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "pull":
        ok = pull_file(sys.argv[2], sys.argv[3])
        sys.exit(0 if ok else 1)
    elif len(sys.argv) == 3 and sys.argv[1] == "sha256":
        print(remote_sha256(sys.argv[2]))
    elif len(sys.argv) == 3 and sys.argv[1] == "size":
        print(remote_size(sys.argv[2]))
    else:
        print(__doc__)
