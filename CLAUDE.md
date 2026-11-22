# Jarvis Voice Assistant — notes for Claude Code

"Hey Jarvis" voice assistant for Linux. Python 3.11+, GTK 3 + Cairo, runs as a systemd user service.

## Files

- `jarvis.py` — the pipeline and the `Assistant` class: microphone (`pw-record`), wake word (openWakeWord `hey_jarvis`), Silero VAD listening, Groq Whisper transcription, Claude Code calls (`claude -p --output-format json --permission-mode auto --resume <session>`), Kokoro/Edge TTS, voice interruption (`_barge_monitor`), goodbye and unfinished-sentence detection.
- `jarvis_ui.py` — the floating bubble (`Bubble`): transparent window pinned with gtk-layer-shell (falls back to keep-above), everything drawn with Cairo + Pango. It reads `assistant.mic_level`, `assistant.voice_level()` and `assistant.current_caption()`.
- `install.sh` / `uninstall.sh` — per-user install into `~/.local/share/jarvis` (venv with `--system-site-packages` for GTK), models, Groq key prompt, systemd unit.
- `config.example.toml` — every setting with comments. Defaults live in `DEFAULTS` in `jarvis.py`; keep both in sync.

## Runtime locations

- Code: `~/.local/share/jarvis/{jarvis.py,jarvis_ui.py,venv,models}`
- Settings: `~/.config/jarvis/config.toml`, Groq key: `~/.config/jarvis/groq_key` (never read it aloud, print it or commit it)
- Log: `~/.local/state/jarvis/jarvis.log`, service: `systemctl --user ... jarvis`

## Develop and test

```bash
python3 -m py_compile jarvis.py jarvis_ui.py          # syntax check
install -m 755 jarvis.py ~/.local/share/jarvis/        # deploy without the full installer
install -m 644 jarvis_ui.py ~/.local/share/jarvis/
systemctl --user restart jarvis
systemctl --user kill --kill-whom=main -s USR1 jarvis  # wake Jarvis without speaking
tail -f ~/.local/state/jarvis/jarvis.log
```

- Always use `--kill-whom=main` with the USR1 wake: without it the signal also reaches `pw-record` and kills the microphone.
- Pure functions (`is_goodbye`, `looks_unfinished`, sentence splitting) can be tested by importing the module with the venv Python and calling them with example strings.
- The interrupt monitor logs `Interrupt monitor: ... max voice score ...`; use it to tune `[interrupt]` thresholds.

## Gotchas

- `sudo` does not work from the Claude desktop app's shells (no_new_privs). Ask the user to run sudo/apt commands in their own terminal.
- The app's shells cannot see `~/.gitconfig` or `~/.ssh`: the user commits and pushes from their own terminal. End commit messages with the Claude co-author line.
- COSMIC hides privileged Wayland protocols (layer-shell) from Flatpak apps, but native apps like Jarvis get them.
- Kokoro voice is generated faster than real time and streamed raw to `pw-play --raw --format f32`; "deeper" voices play at `24000 * (1 - kokoro_deepen)` Hz.
- Keep spoken replies free of markdown: the system prompt in `build_system_prompt()` forbids lists, code blocks and emojis.

## Style

- Comments and docs in English; user-facing strings come from `config.toml` `[phrases]` when possible.
- Small focused changes; update `README.md` and `config.example.toml` when behavior or settings change.
