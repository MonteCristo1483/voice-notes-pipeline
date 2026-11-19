# Architecture

## Components

| Module | Responsibility |
|---|---|
| `config.py` | Reads `.env`, builds an immutable `Settings` object |
| `transcribe.py` | Stages the file, converts to WAV, enforces the duration threshold, runs Whisper, normalizes speaker labels |
| `providers.py` | Calls Ollama or an OpenAI-compatible API and returns parsed JSON |
| `schemas.py` | JSON schemas for personal and work notes |
| `prompts.py` | Prompt templates and per-profile field descriptions |
| `render.py` | Turns validated fields into Markdown |
| `summarize.py` | Chooses a profile, splits long transcripts, merges chunk summaries |
| `notes.py` | Writes the final note into the vault |
| `watcher.py` | Polls inboxes, checks file stability, routes results |
| `pipeline.py` | Orchestrates one file end to end |
| `cli.py` | One-shot command-line entry point |

## Data flow

1. The watcher finds a file with a media extension in an inbox.
2. It ignores files younger than `MIN_FILE_AGE_PERSONAL` / `MIN_FILE_AGE_WORK` (cloud sync may still be writing them) and waits until the size is stable for `STABLE_CHECKS` consecutive checks.
3. It hashes the content. If the hash is already in `seen.json`, the file is moved to `skipped/` — sync clients often re-upload a recording that was already handled.
4. `transcribe()` copies the file under an ASCII name, converts it to mono 16 kHz WAV and computes the exact duration from the PCM byte rate.
5. Files shorter than `MIN_DURATION_SEC` raise `TooShortError` and are moved to `skipped/`.
6. Before Whisper starts, the local LLM is unloaded from VRAM (`keep_alive: 0`) when the provider is local.
7. Whisper writes SRT. A valid SRT is accepted even if the process exits non-zero.
8. `postprocess.py` groups subtitles by speaker. It runs with `PYTHONIOENCODING=utf-8` under a console Python: the script prints emoji and dies on cp1251 when piped from `pythonw.exe`. If it produces nothing, plain SRT text is used.
9. Speaker labels are normalized: one speaker → labels removed; several → `Speaker N:` inline.
10. `summarize()` sends the transcript (or chunks) to the configured LLM with a JSON schema.
11. `render_*()` builds Markdown from validated fields.
12. `write_note()` adds a header and the full transcript in a collapsed block, then writes into `<vault>/AI/Транскрипты/`.
13. The source file moves to `processed/YYYY-MM/`.

## State machine for an input file

```
new → unstable (still copying)
    → too short → skipped/
    → processed → processed/YYYY-MM/
    → failure   → quarantine/
```

A failed file is quarantined immediately. Retrying a broken file every poll interval is worse than losing it silently: the watcher logs the error and keeps the file for manual inspection.

## Concurrency

The watcher is deliberately single-threaded. Transcription and summarization both compete for GPU/VRAM, and a queue of two makes memory behaviour unpredictable. Throughput is not the goal; predictable resource usage is.

## Failure modes

| Failure | Detection | Handling |
|---|---|---|
| Partially copied file | Size changes between checks | Wait for the next poll |
| Cloud sync writes the file in chunks | File is younger than the minimum age | Wait; do not process yet |
| Sync re-uploads an already handled file | SHA-1 is in `seen.json` | Move to `skipped/` |
| Broken mp3 header | ffmpeg exit code / no WAV | Quarantine with the ffmpeg tail in the log |
| Whisper crash after SRT | Non-zero exit code, SRT exists | Continue; log a warning |
| Speaker grouping prints emoji under cp1251 | Child exits non-zero, no grouped file | UTF-8 env + console Python; fall back to plain SRT |
| Empty diarization | No grouped text file | Fall back to plain SRT text |
| Silent recording | Empty transcript | Quarantine |
| Whisper CUDA error | Non-zero exit, no SRT | Auto-unload the local LLM before the next attempt; quarantine current file |
| LLM timeout / bad JSON | Parse exception | Retry once, then fall back to the local model |
| Cloud auth/balance error | HTTP 401/402/429 | Log a specific message, fall back locally |
| Context overflow | Transcript above threshold | Chunking + batched merging |

## Performance reference

On an RTX 2060 Super (8 GB), `large-v3-turbo`, CUDA float16:

| Input | Whisper + diarization | Summary (cloud) | Summary (local 7B) |
|---|---|---|---|
| 1.2 min | ~35 s | ~2 s | ~5 s |
| 40 min | ~1.5 min | ~5 s | ~2 min |
| 3 h | ~9 min | ~7 s | ~3.5 min |

Numbers are indicative; the first run after boot is slower because models load into VRAM.

## Privacy boundary

- Audio never leaves the machine.
- With `LLM_PROVIDER=cloud`, the transcript text is sent to the configured provider.
- With `LLM_PROVIDER=local`, nothing leaves the machine.
- Keys live in `.env`, which is git-ignored.
