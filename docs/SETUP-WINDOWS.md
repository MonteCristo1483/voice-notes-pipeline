# Setup on Windows (no admin rights)

The pipeline is designed to run from a user folder without installing system-wide services. Everything below works with a normal user account.

## 1. Python

Install Python 3.10+ or use a portable distribution. Verify:

```powershell
python --version
```

Create a virtual environment inside the project:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
```

## 2. Whisper bundle

Download the portable [Faster-Whisper-XXL](https://github.com/Purfview/whisper-standalone-win/releases) build and unpack it anywhere, for example `C:\Tools\Faster-Whisper-XXL`.

The folder should contain:

- `faster-whisper-xxl.exe`
- `ffmpeg.exe` (the bundle ships its own copy)
- `postprocess.py`

Point `.env` to it:

```env
WHISPER_DIR=C:\Tools\Faster-Whisper-XXL
WHISPER_MODEL=large-v3-turbo
```

The model is downloaded on first use. CUDA with a recent NVIDIA driver is required for the default `float16` mode; on CPU, change `WHISPER_COMPUTE_TYPE=int8` and expect a large slowdown.

## 3. Local LLM (optional)

Install [Ollama](https://ollama.com) or use the portable `ollama.exe` bundle:

```powershell
$env:OLLAMA_HOST = "127.0.0.1:11434"
ollama serve
ollama pull qwen2.5:7b
```

If registry access is blocked by your provider, import a GGUF manually:

```powershell
ollama create qwen2.5:7b -f Modelfile
```

Or skip local entirely and configure a cloud provider — see [PROVIDERS.md](PROVIDERS.md).

## 4. Configure

```powershell
copy .env.example .env
notepad .env
```

Minimum to fill in:

```env
VAULT_PERSONAL=C:\Users\you\Obsidian\Personal
INBOX_PERSONAL=C:\Users\you\Inbox\Personal
WHISPER_DIR=C:\Tools\Faster-Whisper-XXL
```

## 5. Run

One file:

```powershell
.venv\Scripts\python.exe -m voice_notes.cli "C:\recordings\note.mp3" --profile personal
```

Watcher:

```powershell
.venv\Scripts\python.exe -m voice_notes.watcher
```

## 6. Autostart without admin

Windows allows per-user autostart through `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`. Create a VBS wrapper so no console window appears.

`start-watcher.vbs`:

```vbscript
Set shell = CreateObject("WScript.Shell")
shell.Run "C:\Tools\voice-notes-pipeline\.venv\Scripts\pythonw.exe -m voice_notes.watcher", 0, False
```

Register it:

```powershell
$vbs = "C:\Tools\voice-notes-pipeline\start-watcher.vbs"
New-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" `
  -Name "VoiceNotesWatcher" -Value "wscript.exe `"$vbs`"" -PropertyType String -Force
```

Remove:

```powershell
Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "VoiceNotesWatcher"
```

## 7. Syncing recordings and notes

The pipeline does not care how files arrive. Common setups:

- **Phone → PC:** Syncthing between the recorder folder and `INBOX_PERSONAL`.
- **Work laptop → PC:** a synced Obsidian vault; drop recordings into `INBOX_WORK` and let the vault sync handle the rest.

Use exactly one sync tool per folder. Two sync clients on the same vault cause duplicated and conflicting notes.

## 8. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `CUDA error: unknown error` in Whisper | Local LLM occupies VRAM | The pipeline unloads it automatically; if it persists, stop the model manually (`ollama stop <model>`) or use cloud mode |
| `no SRT produced` | Broken recording or missing model | Check the ffmpeg log line and disk space; try another file |
| Note is empty or vague | Bad audio / poor ASR | Re-record closer to the mic; try `WHISPER_MODEL=large-v3` |
| File stays in inbox | Still being copied | Wait for the next poll; the size must be stable for several checks |
| Everything is quarantined | Ollama is not running and cloud is not configured | Start Ollama or set `LLM_PROVIDER=cloud` with a key |
| Ports/keys exposed | Cloud key committed | Rotate the key, keep `.env` out of git |
