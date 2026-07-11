"""Frame extraction tuned for the 10-minute / 2-vCPU harness budget.

Strategy: probe duration, pick timestamps, then extract each frame straight
from the remote URL with `ffmpeg -ss` (HTTP range seek — no full download).
If remote seek fails for a clip, download once to /tmp and extract locally.
"""
import asyncio
import os
import re
import sys
import tempfile

import httpx


def ffmpeg_bin() -> str:
    override = os.getenv("FFMPEG_BIN")
    if override:
        return override
    try:  # local dev on Windows: bundled static binary
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:  # container: apt-installed
        return "ffmpeg"


_DUR_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)")


async def _run(cmd: list[str], timeout: float = 60.0) -> tuple[int, bytes, bytes]:
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise
    return proc.returncode or 0, out, err


async def probe_duration(url: str) -> float:
    """Clip duration in seconds, parsed from ffmpeg banner (no ffprobe needed)."""
    _, _, err = await _run([ffmpeg_bin(), "-hide_banner", "-i", url], timeout=45)
    m = _DUR_RE.search(err.decode(errors="ignore"))
    if not m:
        return 60.0  # assume mid-range; spec says 30s-2min
    h, mnt, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
    return h * 3600 + mnt * 60 + s


def pick_timestamps(duration: float) -> list[float]:
    """5-10 samples: enough temporal coverage, cheap enough for the budget."""
    n = 5 if duration <= 45 else 8 if duration <= 90 else 10
    margin = min(1.5, duration * 0.05)
    usable = max(duration - 2 * margin, 1.0)
    return [round(margin + usable * i / (n - 1), 2) for i in range(n)]


def _fmt_ts(t: float) -> str:
    return f"{int(t // 60):02d}:{t % 60:04.1f}"


async def _extract_one(src: str, t: float) -> tuple[str, bytes] | None:
    code, out, _ = await _run(
        [
            ffmpeg_bin(), "-hide_banner", "-loglevel", "error",
            "-ss", str(t), "-i", src,
            "-frames:v", "1", "-vf", "scale=768:-2",
            "-q:v", "4", "-f", "image2pipe", "-vcodec", "mjpeg", "-",
        ],
        timeout=50,
    )
    if code == 0 and len(out) > 5000:  # sanity: a real JPEG, not a stub
        return (_fmt_ts(t), out)
    return None


async def _download(url: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    async with httpx.AsyncClient(timeout=180, follow_redirects=True) as c:
        async with c.stream("GET", url) as r:
            r.raise_for_status()
            with open(path, "wb") as f:
                async for chunk in r.aiter_bytes(1 << 20):
                    f.write(chunk)
    return path


async def extract_frames(url: str) -> list[tuple[str, bytes]]:
    """Timestamped JPEG frames for one clip. Remote-seek first, download fallback."""
    duration = await probe_duration(url)
    stamps = pick_timestamps(duration)

    sem = asyncio.Semaphore(3)

    async def guarded(src: str, t: float):
        async with sem:
            try:
                return await _extract_one(src, t)
            except Exception as e:  # noqa: BLE001
                print(f"[video] frame @{t}s failed: {e}", file=sys.stderr)
                return None

    frames = [f for f in await asyncio.gather(*(guarded(url, t) for t in stamps)) if f]

    if len(frames) < max(3, len(stamps) // 2):  # remote seek unreliable -> download once
        print(f"[video] remote seek weak ({len(frames)}/{len(stamps)}), downloading", file=sys.stderr)
        path = await _download(url)
        try:
            frames = [f for f in await asyncio.gather(*(guarded(path, t) for t in stamps)) if f]
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    if not frames:
        raise RuntimeError(f"no frames extracted from {url}")
    return frames
