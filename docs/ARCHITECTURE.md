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
2. It waits until the size is stable for `STABLE_CHECKS` consecutive checks, so partially copied files are not processed.
3. `transcribe()` copies the file under an ASCII name, converts it to mono 16 kHz WAV and computes the exact duration from the PCM byte rate.
4. Files shorter than `MIN_DURATION_SEC` raise `TooShortError` and are moved to `skipped/`.
5. Before Whisper starts, the local LLM is unloaded from VRAM (`keep_alive: 0`) when the provider is local.
6. Whisper writes SRT. A valid SRT is accepted even if the process exits non-zero.
7. `postprocess.py` groups subtitles by speaker. If it produces nothing (short recordings), plain SRT text is used.
8. Speaker labels are normalized: one speaker → labels removed; several → `Speaker N:` inline.
9. `summarize()` sends the transcript (or chunks) to the configured LLM with a JSON schema.
10. `render_*()` builds Markdown from validated fields.
11. `write_note()` adds a header and the full transcript in a collapsed block, then writes into `<vault>/AI/Транскрипты/`.
12. The source file moves to `processed/YYYY-MM/`.

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
| Broken mp3 header | ffmpeg exit code / no WAV | Quarantine with the ffmpeg tail in the log |
| Whisper crash after SRT | Non-zero exit code, SRT exists | Continue; log a warning |
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
