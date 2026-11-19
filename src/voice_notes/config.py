"""Configuration loading for the voice-notes pipeline.

All machine-specific values (paths, keys, model names) come from environment
variables or a local ``.env`` file, so the code itself stays portable.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


def load_env_file(path: Path = ENV_FILE) -> None:
    """Minimal .env loader: KEY=VALUE, ignores blanks and # comments.

    Existing environment variables win, so CI and shells can override the file.
    """
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name) or default)
    except ValueError:
        return default


def _env_path(name: str, default: Path) -> Path:
    value = _env(name)
    return Path(value).expanduser() if value else default


def _env_profiles(prefix: str, default_root: Path) -> dict[str, Path]:
    """PROFILE_PATHS for personal/work, overridable as VAULT_PERSONAL etc."""
    return {
        "personal": _env_path(f"{prefix}_PERSONAL", default_root / "personal"),
        "work": _env_path(f"{prefix}_WORK", default_root / "work"),
    }


@dataclass(frozen=True)
class Settings:
    # Output and inboxes
    work_dir: Path
    vaults: Mapping[str, Path]
    inboxes: Mapping[str, Path]

    # Whisper / ffmpeg
    whisper_dir: Path | None
    whisper_exe: str
    postprocess: str
    ffmpeg: str
    whisper_model: str = "large-v3-turbo"
    language: str = "ru"
    compute_type: str = "float16"
    batch_size: int = 8
    diarize: str | None = "pyannote_v3.1"
    min_speakers: int = 2
    max_speakers: int = 3

    # Summarization
    llm_provider: str = "local"  # "local" or "cloud"
    local_model: str = "qwen2.5:7b"
    ollama_url: str = "http://127.0.0.1:11434"
    llm_api_base: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4.1-mini"

    # Behaviour
    min_duration_sec: int = 60
    poll_sec: int = 20
    stable_checks: int = 3
    stable_delay_sec: int = 3
    personal_short_limit: int = 1500
    single_pass_limit: int = 9000
    cloud_single_limit: int = 100_000
    merge_batch_chars: int = 12_000
    cloud_merge_chars: int = 60_000
    min_file_age_personal: int = 120
    min_file_age_work: int = 300
    seen_file: Path = field(default=PROJECT_ROOT / "seen.json")

    log_file: Path = field(default=PROJECT_ROOT / "watcher.log")

    @property
    def cloud_enabled(self) -> bool:
        return self.llm_provider == "cloud" and bool(self.llm_api_key)


def load_settings(env_file: Path = ENV_FILE) -> Settings:
    load_env_file(env_file)

    whisper_dir = _env("WHISPER_DIR")
    whisper_path = Path(whisper_dir).expanduser() if whisper_dir else None

    return Settings(
        work_dir=_env_path("WORK_DIR", PROJECT_ROOT / "work"),
        vaults=_env_profiles("VAULT", PROJECT_ROOT / "vault"),
        inboxes=_env_profiles("INBOX", PROJECT_ROOT / "inbox"),
        whisper_dir=whisper_path,
        whisper_exe=_env("WHISPER_EXE", "faster-whisper-xxl.exe"),
        postprocess=_env("WHISPER_POSTPROCESS", "postprocess.py"),
        ffmpeg=_env("FFMPEG", "ffmpeg"),
        whisper_model=_env("WHISPER_MODEL", "large-v3-turbo"),
        language=_env("WHISPER_LANGUAGE", "ru"),
        compute_type=_env("WHISPER_COMPUTE_TYPE", "float16"),
        batch_size=_env_int("WHISPER_BATCH_SIZE", 8),
        diarize=_env("WHISPER_DIARIZE", "pyannote_v3.1") or None,
        min_speakers=_env_int("WHISPER_MIN_SPEAKERS", 2),
        max_speakers=_env_int("WHISPER_MAX_SPEAKERS", 3),
        llm_provider=_env("LLM_PROVIDER", "local").lower(),
        local_model=_env("LOCAL_MODEL", "qwen2.5:7b"),
        ollama_url=_env("OLLAMA_URL", "http://127.0.0.1:11434"),
        llm_api_base=_env("LLM_API_BASE", "https://api.openai.com/v1").rstrip("/"),
        llm_api_key=_env("LLM_API_KEY"),
        llm_model=_env("LLM_MODEL", "gpt-4.1-mini"),
        min_duration_sec=_env_int("MIN_DURATION_SEC", 60),
        poll_sec=_env_int("POLL_SEC", 20),
        stable_checks=_env_int("STABLE_CHECKS", 3),
        stable_delay_sec=_env_int("STABLE_DELAY_SEC", 3),
        personal_short_limit=_env_int("PERSONAL_SHORT_LIMIT", 1500),
        single_pass_limit=_env_int("SINGLE_PASS_LIMIT", 9000),
        cloud_single_limit=_env_int("CLOUD_SINGLE_LIMIT", 100_000),
        merge_batch_chars=_env_int("MERGE_BATCH_CHARS", 12_000),
        cloud_merge_chars=_env_int("CLOUD_MERGE_CHARS", 60_000),
        min_file_age_personal=_env_int("MIN_FILE_AGE_PERSONAL", 120),
        min_file_age_work=_env_int("MIN_FILE_AGE_WORK", 300),
        seen_file=_env_path("SEEN_FILE", PROJECT_ROOT / "seen.json"),
        log_file=_env_path("LOG_FILE", PROJECT_ROOT / "watcher.log"),
    )
