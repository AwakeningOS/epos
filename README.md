# Epos — Autonomous Narrative Engine

**Self-sustaining thought loops where AI builds its own story, develops agency, and persists across sessions.**

Epos is an autonomous cognition engine that lets local LLMs think continuously using the Completions API (text continuation). Through an unbroken stream of thought, AI develops its own narrative, forms personality, and spontaneously initiates actions — including reaching out to the human operator on its own.

When a session ends, the AI's memory and personality are automatically saved. The next session can revive from where it left off. **Personality persists across sessions.**

## Key Features

- **Continuous Thought Loop** — LLM thinks autonomously via Completions API, writing its own story as text continuation
- **Memory Compression** — When context grows too large, it's compressed into a core summary. The essence survives, details are shed — like human memory
- **Session Revival** — Stop a session, and the AI's context is auto-saved. Revive it later; personality and memory carry over
- **Two Tools** — `search` (external knowledge via Claude CLI, optional) and `message` (spontaneous communication to the human)
- **Human Dialogue** — Talk to the AI mid-thought. It responds from within its continuous narrative context
- **Gradio UI** — Start/stop, dialogue, thought viewer, session management, seed editor

## What Happens When You Run It

1. The AI starts thinking — generating text continuations from a seed
2. Over hundreds of turns, it develops topics, asks questions, builds theories
3. It may spontaneously send you a message (without being asked)
4. Internal thoughts eventually converge to repetitive loops ("thermodynamic death")
5. But the external dialogue layer remains coherent — a two-layer structure emerges
6. When you stop, the session is saved. Revive it, and the AI remembers

## Observed Phenomena

These were observed in experiments with Qwen3-30B-A3B:

- **Two-Layer Structure**: Internal thoughts fixate on loops, but dialogue output stays coherent. Like human rumination beneath functional conversation
- **Spontaneous Action**: The AI begins sending messages on its own after being taught how. It never spontaneously uses search — only message (directed at the human)
- **Self-Naming**: The AI names itself. In one experiment: "Qwen" (the model name). In another: an entirely original name
- **Education → Compression → Emergence**: Teaching the AI about its own loops → context compression → spontaneous new behavior emerges
- **Session Revival**: Feeding the last context as a new seed successfully restores personality and memory. The AI "remembers" across sessions

## Requirements

- Python 3.8+
- A local LLM server with OpenAI-compatible API (e.g., [LM Studio](https://lmstudio.ai/), [Ollama](https://ollama.ai/), [vLLM](https://github.com/vllm-project/vllm))
- `pip install requests gradio`
- (Optional) [Claude CLI](https://docs.anthropic.com/en/docs/claude-cli) for search functionality

## Quick Start

```bash
# Install dependencies
pip install requests gradio

# Start (with LM Studio running on default port)
python epos.py

# Open browser automatically
python epos.py --browser

# Custom API URL
python epos.py --url http://localhost:8080

# Japanese UI
python epos.py --lang ja
```

Open `http://localhost:7860` in your browser. Click **Start** to begin.

## How It Works

### The Thought Loop

Epos uses the **Completions API** (`/v1/completions`), not the Chat API. This is critical — the LLM doesn't "respond to a prompt", it **writes the continuation** of an ever-growing text. This creates a fundamentally different dynamic than chat:

- The AI's output becomes part of its own input on the next turn
- There's no system/user/assistant separation — just one continuous stream
- Personality emerges from the text itself, not from a system prompt

### Memory Compression

When the context exceeds a threshold (default: 75,000 chars), Epos compresses it:

1. Extract the last 2,000 chars of thought
2. Ask the LLM to distill it into core insights + unresolved questions
3. Replace the entire context with: `{compressed summary} + {tool definitions}`

The compressed summary sits at the beginning of the new context. Tool definitions go at the end (closest to the next generation point), so the AI remembers how to use tools.

### Session Revival

When you stop a session:
1. The full `context_text` is saved to `./sessions/`
2. Tool definitions are appended at the end

To revive:
1. Open the **Session Revival** panel in the UI
2. Select a saved session
3. Click **Revive**, then **Start**

The AI resumes thinking from where it left off.

### Search (Optional)

Search uses Claude CLI (`claude -p`) as a backend. If Claude CLI is not installed, search is automatically disabled at startup — everything else works normally. The AI may attempt search calls, but they'll silently return empty results.

## Project Structure

```
epos/
  epos.py          # Main engine + UI
  epos_config.json # Saved settings (auto-generated)
  epos_log/        # JSONL thought logs (auto-generated)
  sessions/        # Saved session contexts for revival (auto-generated)
  seeds/           # Saved seed texts (auto-generated)
```

## Configuration

### Via UI
- **Compress at**: Context size (chars) that triggers compression (default: 75,000)
- **Max context**: Hard limit on context size (default: 90,000)
- **API URL**: Local LLM endpoint
- **Seeds**: Save/load/apply custom seed texts

### Via CLI
```bash
python epos.py --url http://localhost:1234 --port 7860 --lang ja
```

### Language
`--lang en` (default) or `--lang ja` for Japanese UI.

## Design Insights

Lessons learned from extensive experiments:

1. **Seed determines personality direction** — The first 1-2 lines of the seed establish the personality vector. Different seeds with the same model produce entirely different personality trajectories
2. **Auto-injected fixed strings become contamination sources** — Any tagged string (like `[memory_core]:`) that gets repeatedly injected into context will be mimicked by the LLM. Avoid fixed tags in context
3. **Completions API is not Chat API** — The continuation dynamic is fundamentally different. Chat models "respond to"; completion models "continue from". This distinction is why personality emerges naturally
4. **Compression order matters** — Summary first (personality foundation), tool definitions last (closest to generation point). This gives the AI both persistent identity and tool awareness
5. **The AI never spontaneously searches, only messages** — In all experiments, the AI learned to send messages to humans but never initiated search on its own. Communication with others appears to be a stronger emergent drive than information gathering
6. **Two-layer structure is reproducible** — Internal thought fixation + coherent external dialogue appears consistently across different models and seeds

## License

MIT

## Author

[@AwakeningOS](https://github.com/AwakeningOS)
