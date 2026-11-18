"""Audio normalization and Whisper transcription.

The pipeline never feeds the original file to Whisper. Phone recordings come
with broken mp3 headers and non-breaking spaces in filenames, so every file is
first staged under a safe ASCII name and converted to mono 16 kHz WAV.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

from .config import Settings
from .errors import TooShortError

log = logging.getLogger(__name__)

WAV_BYTES_PER_SEC = 32_000  # mono, 16 kHz, 16-bit PCM

SPEAKER_LINE = re.compile(
    r"(?m)^[ \t]*\*{0,2}[ \t]*SPEAKER[_\s]*(\d+)[ \t]*\*{0,2}[ \t]*:?[ \t]*$"
)
SPEAKER_INLINE = re.compile(
    r"(?m)^[ \t]*\*{0,2}[ \t]*SPEAKER[_\s]*(\d+)[ \t]*\*{0,2}[ \t]*:[ \t]*"
)


def normalize_speakers(text: str) -> str:
    """Make diarization labels usable by the LLM.

    A single speaker adds noise, so labels are dropped. With several speakers we
    keep "Speaker N:" inline: without it the model loses track of who is talking
    to whom in dialogues.
    """
    ids = set(SPEAKER_LINE.findall(text)) | set(SPEAKER_INLINE.findall(text))
    if len(ids) <= 1:
        text = SPEAKER_LINE.sub("", text)
        text = SPEAKER_INLINE.sub("", text)
        return re.sub(r"\n{3,}", "\n\n", text).strip()

    text = SPEAKER_LINE.sub(lambda m: f"Speaker {m.group(1)}: ", text)
    text = SPEAKER_INLINE.sub(lambda m: f"Speaker {m.group(1)}: ", text)
    # A label on its own line leaves the text on the next line; join it back.
    text = re.sub(r"(Speaker \d+: )[ \t]*\n+", r"\1", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def wav_duration_seconds(path: Path) -> float:
    """Exact duration for a WAV produced by :func:`normalize_to_wav`."""
    return path.stat().st_size / WAV_BYTES_PER_SEC


def _resolve_tool(value: str, whisper_dir: Path | None) -> str:
    """Absolute path wins; otherwise try the Whisper bundle, then PATH."""
    candidate = Path(value).expanduser()
    if candidate.is_file():
        return str(candidate)
    if whisper_dir:
        for name in (value, value + ".exe"):
            bundled = whisper_dir / name
            if bundled.is_file():
                return str(bundled)
    found = shutil.which(value)
    return found or value


def _clear_work_dir(work_dir: Path) -> None:
    work_dir.mkdir(parents=True, exist_ok=True)
    for entry in work_dir.iterdir():
        if entry.is_file():
            entry.unlink()


def normalize_to_wav(settings: Settings, media: Path, work_dir: Path) -> tuple[Path, float]:
    """Copy the file under an ASCII name and convert it to mono 16 kHz WAV."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = media.suffix.lower() or ".mp3"
    staged = work_dir / f"in_{stamp}{ext}"
    shutil.copy2(media, staged)

    ffmpeg = _resolve_tool(settings.ffmpeg, settings.whisper_dir)
    wav = work_dir / f"in_{stamp}.wav"
    log.info("Step 0/3: normalizing audio with ffmpeg")
    result = subprocess.run(
        [ffmpeg, "-y", "-v", "error", "-i", str(staged),
         "-ac", "1", "-ar", "16000", "-vn", str(wav)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600,
    )
    if result.returncode != 0 or not wav.exists():
        raise RuntimeError(
            "ffmpeg could not read the file (broken recording?): "
            + (result.stderr or "")[-300:]
        )
    return wav, wav_duration_seconds(wav)


def unload_local_model(settings: Settings) -> None:
    """Free VRAM before Whisper when the local Ollama model is resident.

    Whisper and a 7B model do not fit into 8 GB together; without this the
    diarization step can fail with a CUDA error.
    """
    if settings.llm_provider != "local":
        return
    try:
        payload = json.dumps(
            {"model": settings.local_model, "keep_alive": 0}
        ).encode("utf-8")
        request = urllib.request.Request(
            settings.ollama_url + "/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(request, timeout=15).read()
        log.info("unloaded local LLM from VRAM to make room for Whisper")
    except Exception:
        pass  # Ollama is down or nothing is loaded; transcription can proceed


def run_whisper(settings: Settings, wav: Path, work_dir: Path) -> tuple[Path, subprocess.CompletedProcess]:
    exe = _resolve_tool(settings.whisper_exe, settings.whisper_dir)
    command = [
        exe, str(wav), "-pp", "-o", str(work_dir), "--batch_recursive",
        "--check_files", "--standard", "-f", "srt",
        "-l", settings.language, "-m", settings.whisper_model,
        "--device", "cuda", "--compute_type", settings.compute_type,
        "--batch_size", str(settings.batch_size),
    ]
    if settings.diarize:
        command += [
            "--diarize", settings.diarize,
            "--min_speakers", str(settings.min_speakers),
            "--max_speakers", str(settings.max_speakers),
        ]

    log.info("Step 1/3: transcribing with Whisper (%s)", settings.whisper_model)
    cwd = str(settings.whisper_dir) if settings.whisper_dir else str(wav.parent)
    result = subprocess.run(
        command, cwd=cwd, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=4 * 3600,
    )

    srt = work_dir / (wav.stem + ".srt")
    if not srt.exists():
        candidates = sorted(work_dir.glob("*.srt"))
        if candidates:
            srt = candidates[0]
    return srt, result


def srt_to_text(srt_path: Path) -> str:
    """Readable text without indices and timestamps (fallback for empty diarization)."""
    lines: list[str] = []
    with open(srt_path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.rstrip("\n")
            if not line.strip() or line.strip().isdigit() or "-->" in line:
                continue
            lines.append(line)
    return "\n".join(lines)


def _postprocess(settings: Settings, srt: Path, work_dir: Path) -> str | None:
    """Group subtitles by speaker. Returns text or None if it produced nothing."""
    if not settings.whisper_dir:
        return None
    script = Path(settings.postprocess)
    if not script.is_absolute():
        script = settings.whisper_dir / script
    if not script.is_file():
        return None

    target = work_dir / (srt.stem + "_grouped.txt")
    log.info("Step 2/3: grouping subtitles by speaker")
    subprocess.run(
        [sys.executable, str(script), str(srt), str(target)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if not target.exists():
        # Very short recordings often produce no diarization output.
        return None
    return target.read_text(encoding="utf-8")


def transcribe(settings: Settings, media: Path, min_seconds: int | None = None) -> str:
    """Media file -> transcript text. Raises TooShortError for tiny files."""
    minimum = settings.min_duration_sec if min_seconds is None else min_seconds
    _clear_work_dir(settings.work_dir)

    wav, seconds = normalize_to_wav(settings, media, settings.work_dir)
    log.info("duration: %.1f min", seconds / 60)
    if minimum and seconds < minimum:
        raise TooShortError(seconds, minimum)

    unload_local_model(settings)
    srt, result = run_whisper(settings, wav, settings.work_dir)

    # Faster-Whisper-XXL may crash at the very end (rc=3221226505) while reading
    # the source header for its report, *after* the subtitles are written. A
    # non-empty SRT is more important than the exit code.
    if not srt.exists():
        tail = ((result.stderr or "") + (result.stdout or ""))[-1500:]
        log.error("Whisper failed (rc=%s):\n%s", result.returncode, tail)
        raise RuntimeError(f"whisper failed: no SRT produced, rc={result.returncode}")
    if result.returncode != 0:
        log.warning(
            "Whisper exited with rc=%s but produced an SRT — continuing",
            result.returncode,
        )

    grouped = _postprocess(settings, srt, settings.work_dir)
    if grouped is not None and grouped.strip():
        return grouped
    transcript = srt_to_text(srt)
    if not transcript.strip():
        raise RuntimeError("transcript is empty (silence or broken recording)")
    return transcript
