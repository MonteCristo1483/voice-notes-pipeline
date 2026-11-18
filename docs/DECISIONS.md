# Design decisions

Short ADR-style notes explaining why the code looks the way it does. Most of these were written after a real failure, not in advance.

## ADR-001: Structured JSON output instead of "write Markdown"

**Context.** The first version asked the model to produce a finished Markdown note. A 7B model regularly produced headings in the wrong place, tags in the middle, empty sections and duplicated titles. Prompt engineering reduced but never eliminated this.

**Decision.** The model fills a JSON schema. Markdown is rendered deterministically in `render.py`.

**Consequences.** Formatting bugs disappear by construction. The trade-off is that the schema must cover every section, and changing note structure requires code changes, not just prompt edits.

## ADR-002: A valid SRT is more important than the exit code

**Context.** Faster-Whisper-XXL crashes with `rc=3221226505` (`STATUS_STACK_BUFFER_OVERRUN`) on old phone mp3 files *after* writing the subtitles, while reading the source header for its final report. Treating the exit code as success/failure discarded hours of valid work.

**Decision.** If a non-empty SRT exists, the pipeline continues and logs a warning.

**Consequences.** Genuine failures still fail (no SRT → exception), while the known crash pattern is tolerated.

## ADR-003: Normalize every file before transcription

**Context.** Two separate problems: broken mp3 headers, and filenames containing a non-breaking space (`\xa0`) written by the phone recorder. The latter broke post-processing and was impossible to type in some shells.

**Decision.** Copy the input to a staging folder under an ASCII name and convert it with ffmpeg to mono 16 kHz WAV.

**Consequences.** Whisper sees a clean file; duration can be computed exactly from the PCM byte rate (`bytes / 32 000`) without ffprobe. Cost: one extra copy and conversion.

## ADR-004: Quarantine after the first failure

**Context.** A broken file stayed in the inbox and was retried every poll cycle. Each attempt cost minutes on GPU and kept the fans spinning for hours.

**Decision.** Move a failed file to `quarantine/` immediately. Too-short files go to `skipped/` — they are not errors.

**Consequences.** No retry storms. The downside is that a transient failure (e.g. GPU temporarily busy) also quarantines the file; the log says why, and a manual re-run is intentional.

## ADR-005: Minimum duration of 60 seconds

**Context.** Accidental recordings and fragments produced meaningless notes and wasted GPU time.

**Decision.** Skip files shorter than `MIN_DURATION_SEC` (default 60). The CLI has `--allow-short` for deliberate overrides.

**Consequences.** No notes for genuine 40-second thoughts unless requested. The threshold is configuration, not a hard-coded rule.

## ADR-006: Unload the local LLM before Whisper

**Context.** On an 8 GB GPU, a resident 7B model (5 GB) plus Whisper and diarization overflows VRAM. Whisper then fails with `CUDA error: unknown error`, and the recording lands in quarantine.

**Decision.** Before transcription, if the provider is local, call Ollama with `keep_alive: 0`. The server keeps running; the model is reloaded on the next chat request.

**Consequences.** Summaries take slightly longer right after a transcription. The alternative — losing recordings — is worse. This only applies to the local provider; a cloud setup does not touch Ollama.

## ADR-007: Speaker labels are normalized, not deleted

**Context.** Meeting notes were retold as "Speaker 01 said…, Speaker 00 said…". Deleting labels fixed the retelling but broke dialogues: the model lost track of who was speaking to whom.

**Decision.** One speaker → labels removed. Multiple speakers → replace with `Speaker N:` inline.

**Consequences.** The model sees a readable dialogue without a machine-generated structure to copy. Diarization errors still leak into the note, which is an accepted limitation.

## ADR-008: Cloud with local fallback

**Context.** Local 7B summaries are usable for clear meetings but lose specifics on longer, messier recordings. At the same time, a hard dependency on a cloud API means a recording is lost when the network or balance fails.

**Decision.** `LLM_PROVIDER=cloud` is preferred when configured; any failure falls back to Ollama. Both paths use the same JSON schemas and renderer.

**Consequences.** Better notes when the cloud works, graceful degradation when it does not. The transcript text crosses the privacy boundary in cloud mode; this is documented and explicit.

## ADR-009: Chunk and merge for long recordings

**Context.** A three-hour transcript is tens of thousands of tokens. Sending it in one request exceeds small contexts; a naive single merge of 15 chunk summaries produced a rambling note.

**Decision.** Split on paragraph boundaries with overlap, summarize each chunk into the same schema subset, then merge in batches (max 6 summaries locally, 20 in the cloud, bounded by characters).

**Consequences.** Long recordings stay within context and keep details. The cost is more requests and a small risk of duplication at chunk boundaries, mitigated by the overlap and deduplication in the renderer.
