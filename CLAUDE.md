# Jarvis Voice Assistant — notes for Claude Code

"Hey Jarvis" voice assistant for Linux. Python 3.11+, GTK 3 + Cairo, runs as a systemd user service.

## Files

- `jarvis.py` — the pipeline and the `Assistant` class: microphone (`pw-record`), wake word (openWakeWord `hey_jarvis` through `WakeDetector`: `[wake] patience` chunks in a row, stricter `media_threshold` while `MediaWatch` sees media playing via `playerctl`, near misses logged), Silero VAD listening, transcription (`[stt] engine`: local faster-whisper through `LocalSTT`, or Groq; local falls back to Groq if a key exists), Claude Code calls (`ask_and_speak`: `claude -p --output-format stream-json --verbose --include-partial-messages --permission-mode auto --resume <session>`, built by `_claude_cmd()` with `--tools <[claude] tools>` and, unless `[claude] extensions`, `--strict-mcp-config --disable-slash-commands` — the full default tool set is ~25k tokens per request, the 8 tools ~1k — read line by line in a thread; `SentenceStream` hands each finished sentence to the TTS; `[phrases] working` is said on the first tool use if nothing was said yet; `ActivityConsole` writes each tool call (`$ command`) and result to `~/.local/state/jarvis/activity.log` and opens a terminal (`terminal_command()`: cosmic-term `-e`, gnome-terminal `--`...) running `tail -c +<offset> -F` on it; the window is reused while its process is alive (terminals must stay in the foreground: `gnome-terminal --wait`) and `close()` ends it when the conversation ends; the short voice commands "activate / deactivate terminal" (`terminal_switch()` ignores `FILLER_WORDS`, then at most 4 words may remain; handled in `conversation()` without calling Claude; other wordings reach Claude, whose system prompt explains the switch file) write `on`/`off` to `~/.local/state/jarvis/activity_terminal`, which wins over `[activity] show_terminal`; ✕ / orb-while-thinking sets `end_requested` and `_stop_claude` kills Claude's whole process group; `compact_memory` still uses the non-streaming `_run_claude`), Kokoro/Edge TTS, voice interruption (`_barge_monitor`), goodbye and unfinished-sentence detection, memory between conversations (`_resume_session`, `compact_memory`: resume the Claude session within `resume_hours`; after a conversation whose context exceeds `max_context_tokens`, summarize it with `summary_model` and start fresh with the summary appended to the system prompt).
- `jarvis_stt.py` — the local Whisper worker. `LocalSTT` in `jarvis.py` starts it as a child process on wake (`load()`, so loading overlaps the greeting), talks to it over stdin/stdout (JSON line + float32 samples), and stops it `unload_after` seconds after the conversation (`unload_later()`). Gaming mode (`~/.local/state/jarvis/gaming_mode` exists) runs `gaming_model` on the CPU instead.
- `jarvis_ui.py` — the floating bubble (`Bubble`): transparent window pinned with gtk-layer-shell (falls back to keep-above), everything drawn with Cairo + Pango. It reads `assistant.mic_level`, `assistant.voice_level()` and `assistant.current_caption()`.
- `install.sh` / `uninstall.sh` — per-user install into `~/.local/share/jarvis` (venv with `--system-site-packages` for GTK), models, Groq key prompt, systemd unit.
- `benchmark.py` — resource measurements (dev tool, not installed): `monitor` samples the service's cgroup (CPU, PSS RAM, VRAM per activity, Claude and its commands included); `components` times Kokoro, both Whisper models and, with `--claude`, one real request; `tokens` reads Jarvis' questions from Claude Code's history (`~/.claude/projects/-home-<user>/*.jsonl`, sessions containing "Your name is Jarvis") and prices them with `PRICES` (update it when Anthropic's prices change); `tokens --live [--model m]` asks three sample questions and uses Claude Code's `total_cost_usd`. Jarvis logs `Claude usage: N tokens (...), $cost` after every request (`_log_usage`). Update the README "Resource usage" table when the numbers change.
- `config.example.toml` — every setting with comments. Defaults live in `DEFAULTS` in `jarvis.py`; keep both in sync.

## Runtime locations

- Code: `~/.local/share/jarvis/{jarvis.py,jarvis_ui.py,venv,models}`
- Settings: `~/.config/jarvis/config.toml`, Groq key: `~/.config/jarvis/groq_key` (never read it aloud, print it or commit it)
- Memory: `~/.local/state/jarvis/memory.json` (session id, last use, context tokens, summary)
- Log: `~/.local/state/jarvis/jarvis.log`, commands Claude ran: `~/.local/state/jarvis/activity.log`, service: `systemctl --user ... jarvis`

## Develop and test

```bash
python3 -m py_compile jarvis.py jarvis_ui.py jarvis_stt.py   # syntax check
~/.local/share/jarvis/venv/bin/python -m pytest tests       # tests (once: venv/bin/pip install pytest)
python3 benchmark.py monitor 60                              # CPU/RAM/VRAM of the running service
python3 benchmark.py tokens                                  # tokens and cost per question (free)
install -m 755 jarvis.py ~/.local/share/jarvis/        # deploy without the full installer
install -m 644 jarvis_ui.py jarvis_stt.py ~/.local/share/jarvis/
systemctl --user restart jarvis
systemctl --user kill --kill-whom=main -s USR1 jarvis  # wake Jarvis without speaking
tail -f ~/.local/state/jarvis/jarvis.log
```

- Always use `--kill-whom=main` with the USR1 wake: without it the signal also reaches `pw-record` and kills the microphone.
- `tests/` covers the pure functions (`is_goodbye`, `looks_unfinished`, `normalize`, `_sentences`, `SentenceStream`, `format_tool_call`/`format_tool_output`, `terminal_switch`) and `WakeDetector` with a fake model. Importing `jarvis.py` must stay free of side effects: logging, the lock, the mic and GTK all start in `main()` / `Assistant()`.
- Wake tuning: the log has `Wake up (score ..., N chunks ≥ ...)` and `Near miss: wake score ...`; `Media playing: stricter wake threshold` when `playerctl` reports a player.
- The interrupt monitor logs `Interrupt monitor: ... max voice score ...`; use it to tune `[interrupt]` thresholds.

## Gotchas

- Local Whisper on CUDA needs cuBLAS/cuDNN: they come from the pip packages `nvidia-cublas-cu12` and `nvidia-cudnn-cu12` and are loaded by hand in `preload_cuda_libs()` in `jarvis_stt.py` (no system CUDA install needed).
- VRAM is shared with games on the user's 8 GB RTX 4060: never import ctranslate2/CUDA in the main Jarvis process. Only ending the worker process frees the CUDA context. Measured: idle 0 MiB, loaded `large-v3-turbo` int8_float16 ~1.3 GB with the CUDA context (float16 was 2.2 GB) and ~1.9 GB of RAM, 0.25 s per sentence, ~3–6 s to load; `small` on CPU ~1.6 s per sentence.

- `sudo` does not work from the Claude desktop app's shells (no_new_privs). Ask the user to run sudo/apt commands in their own terminal.
- The app's shells cannot see `~/.gitconfig` or `~/.ssh`: the user commits and pushes from their own terminal. End commit messages with the Claude co-author line.
- COSMIC hides privileged Wayland protocols (layer-shell) from Flatpak apps, but native apps like Jarvis get them.
- Kokoro voice is generated faster than real time and streamed raw to `pw-play --raw --format f32`; "deeper" voices play at `24000 * (1 - kokoro_deepen)` Hz.
- openWakeWord's own `predict(patience=...)` never fires (it stores the zeroed scores in its history), so `WakeDetector` counts the chunks itself.
- `claude --bare` would be even leaner but only accepts an API key, not the user's subscription login.
- Claude Code records the system prompt on a conversation's first request and reuses it on `--resume` until compaction: changes to `build_system_prompt()` reach new conversations only.
- Run `claude` with `stdin=DEVNULL`: when its stdin is a pipe it waits 3 s for input first.
- Keep spoken replies free of markdown: the system prompt in `build_system_prompt()` forbids lists, code blocks and emojis.

## Style

- Comments and docs in English; user-facing strings come from `config.toml` `[phrases]` when possible.
- Small focused changes; update `README.md` and `config.example.toml` when behavior or settings change.
