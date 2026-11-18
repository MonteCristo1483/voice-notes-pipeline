# Providers

The pipeline needs one LLM for summarization. Two modes are supported, and both produce the same structured JSON.

## Local: Ollama

```env
LLM_PROVIDER=local
LOCAL_MODEL=qwen2.5:7b
OLLAMA_URL=http://127.0.0.1:11434
```

- Private: nothing leaves the machine.
- Requires a model that supports JSON output. `qwen2.5:7b` works; larger models (14B+) need more VRAM than 8 GB and fall back to partial CPU offload.
- Before Whisper runs, the pipeline unloads the model with `keep_alive: 0` to free VRAM.

Quality: good at extracting explicit facts and decisions from clear speech; weak at abstraction and prone to plausible-sounding inventions on long, messy recordings.

## Cloud: any OpenAI-compatible API

```env
LLM_PROVIDER=cloud
LLM_API_BASE=https://api.openai.com/v1
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4.1-mini
```

Only the transcript text is sent. Audio never leaves the machine.

### Examples

**OpenAI**

```env
LLM_API_BASE=https://api.openai.com/v1
LLM_MODEL=gpt-4.1-mini
```

**DeepSeek**

```env
LLM_API_BASE=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
```

**ProxyAPI (Russian gateway, OpenAI/Claude/Gemini behind one key)**

```env
LLM_API_BASE=https://api.proxyapi.ru/openai/v1
LLM_MODEL=gpt-4.1-mini
```

**Google Gemini (OpenAI-compatible endpoint)**

```env
LLM_API_BASE=https://generativelanguage.googleapis.com/v1beta/openai
LLM_MODEL=gemini-2.5-flash
```

Gemini availability depends on your region; do not assume the free tier is reachable everywhere.

**OpenRouter**

```env
LLM_API_BASE=https://openrouter.ai/api/v1
LLM_MODEL=deepseek/deepseek-chat
```

### Model notes

- Classic chat models (`gpt-4.1-mini`, `gpt-4o-mini`, `deepseek-chat`) accept `max_tokens` and `temperature`.
- Reasoning models (`gpt-5*`, `gpt-6*`, `o3`, `o4`) reject `max_tokens`; the code automatically switches to `max_completion_tokens` and omits `temperature`.
- The pipeline first requests `response_format: {"type": "json_object"}`. If a gateway rejects it with HTTP 400, the request is retried without that field; the JSON skeleton is already in the prompt.

## Cost

A three-hour transcript is roughly 20–25k input tokens. On a mini-class model this is a few cents. Token usage is logged for every note:

```
[2026-01-01 12:00:00] INFO cloud tokens: 21455 in / 679 out
```

## Privacy

| Mode | Audio | Transcript text | Keys |
|---|---|---|---|
| Local | stays | stays | none |
| Cloud | stays | sent to provider | in `.env`, git-ignored |

If the recordings contain sensitive personal or business information, use local mode or a provider you trust contractually.
