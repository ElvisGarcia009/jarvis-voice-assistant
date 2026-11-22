# Jarvis Voice Assistant for Linux

Say **"Hey Jarvis"**, ask for something out loud, and **Claude** does it on your computer and answers with a natural voice.

Jarvis is a small Python app that connects a wake word, speech recognition and a local text-to-speech voice to [Claude Code](https://docs.claude.com/en/docs/claude-code/overview). Claude Code is what actually acts on your PC, so Jarvis can do the same things it can: open apps, check your disk, find files, install things, explain errors, and more.

> "Hey Jarvis... how much free space do I have?"
> "You have about 127 gigabytes free, roughly 68 percent of your disk."

## Features

- **Hands-free wake word**: "Hey Jarvis" is detected offline with [openWakeWord](https://github.com/dscripka/openWakeWord). Nothing leaves your PC until you wake it up.
- **Real actions on your PC**: requests are handled by Claude Code in non-interactive mode, with a safety-first permission mode.
- **Fast local voice**: [Kokoro](https://github.com/thewh1teagle/kokoro-onnx) speaks while the rest of the answer is still being generated. You can blend voices and make them deeper. Edge TTS is available as an online alternative or fallback.
- **Multilingual speech recognition** with Groq Whisper (free API key).
- **Natural conversation**: keep talking without repeating the wake word. Say "thank you" (or "OK, thank you", "that's all", "gracias"...) and Jarvis goes back to sleep.
- **Language practice mode**: Jarvis can always answer in a language you are learning, and tell you how to say your request in that language when you switch to your native one.
- **Visual feedback**: a small window shows whether Jarvis is sleeping, listening, thinking or speaking, plus the conversation. It has buttons to talk, interrupt and end, and it hides itself when the conversation is over.
- **Runs in the background** as a systemd user service and starts with your desktop.

## How it works

```
 microphone ──► openWakeWord ("Hey Jarvis", offline)
                     │
                     ▼
              Silero VAD records your request
                     │
                     ▼
              Groq Whisper (speech → text)
                     │
                     ▼
              Claude Code  `claude -p --permission-mode auto`
              (does the task on your PC, keeps the conversation)
                     │
                     ▼
              Kokoro TTS (local) ──► speakers
```

## Requirements

- Linux with **PipeWire** (`pw-record`, `pw-play`) and **systemd**. This covers most modern distributions.
- **Python 3.11+** with `venv` and the **GTK 3** bindings (`python3-gi`).
- **[Claude Code](https://docs.claude.com/en/docs/claude-code/overview)** installed and logged in, with a Claude subscription or API access.
- A free **[Groq API key](https://console.groq.com/keys)** for speech recognition.
- About 500 MB of disk space for the Python packages and voice models.
- A headset is recommended, so Jarvis does not hear itself or the people around you.

Tested on Pop!_OS 24.04 (COSMIC, Wayland).

## Installation

1. Install the system packages:

   ```bash
   # Debian / Ubuntu / Pop!_OS
   sudo apt install python3-venv python3-gi gir1.2-gtk-3.0 pipewire-bin curl git
   # Fedora
   sudo dnf install python3-gobject gtk3 pipewire-utils curl git
   # Arch
   sudo pacman -S python-gobject gtk3 pipewire curl git
   ```

2. Install Claude Code and log in, if you have not already:

   ```bash
   curl -fsSL https://claude.ai/install.sh | bash
   claude auth login
   ```

3. Clone this repository and run the installer:

   ```bash
   git clone https://github.com/ElvisGarcia009/jarvis-voice-assistant.git
   cd jarvis-voice-assistant
   ./install.sh
   ```

   The installer asks for your Groq API key, downloads the models, and starts Jarvis as a background service. It does not need `sudo`.

4. Say **"Hey Jarvis"**.

## Usage

| Action | How |
|---|---|
| Wake Jarvis | Say "Hey Jarvis", or press **🎤 Talk** in its window |
| Ask something | Just talk after the greeting |
| Interrupt | Press **🤫 Stop talking** |
| Finish | Say "thank you" / "OK, thank you" / "that's all", stay silent, or press **✋ End** |

Service commands:

```bash
systemctl --user restart jarvis     # after changing settings
systemctl --user stop jarvis        # turn it off
journalctl --user -u jarvis -f      # live log (also in ~/.local/state/jarvis/jarvis.log)
```

## Configuration

Edit `~/.config/jarvis/config.toml`, then restart the service. See [`config.example.toml`](config.example.toml) for every option.

```toml
[user]
name = "Alex"

[language]
reply = "English"     # or "auto" to answer in the language you speak
tutor = "Spanish"     # language practice mode

[voice]
engine = "kokoro"
kokoro_voice = "am_onyx+am_michael"   # blend voices with "+"
kokoro_speed = 1.15
kokoro_deepen = 0.08                  # deeper "butler" voice

[claude]
model = "sonnet"      # fast for voice; "opus" is smarter but slower
```

## Security

Jarvis gives a voice interface to a tool that can run commands on your computer. Please read this section.

- Anyone (or any video) near your microphone can say "Hey Jarvis". **Use a headset** and keep Jarvis off when you share the room or stream.
- Jarvis runs Claude Code with `--permission-mode auto`, which lets Claude Code's safety classifier block risky actions. Its instructions also tell it to ask for a spoken "yes" before deleting, uninstalling or changing settings. **Do not switch to `bypassPermissions`.**
- `sudo` does not work from Jarvis. It tells you to run those commands yourself.
- Your Groq key is stored in `~/.config/jarvis/groq_key` with `600` permissions. Never commit it.
- Audio is only sent to Groq **after** the wake word is detected. Your requests are sent to Anthropic through Claude Code, as with any Claude Code use.

## Troubleshooting

- **It never wakes up**: check that the right microphone is the default input, and look at the log. You can lower `[wake] threshold`.
- **It wakes up by mistake**: raise `[wake] threshold` (for example to `0.7`).
- **"I'm not logged in to Claude"**: run `claude auth login` in a terminal.
- **No voice**: test `pw-play /usr/share/sounds/freedesktop/stereo/complete.oga`. Kokoro falls back to Edge TTS automatically if it fails.
- **"Missing Groq API key"**: run `./install.sh` again, or write the key to `~/.config/jarvis/groq_key`.

## Uninstall

```bash
./uninstall.sh            # keeps your settings
./uninstall.sh --purge    # also deletes settings and the Groq key
```

## Credits and licenses

- Code: [MIT License](LICENSE).
- [openWakeWord](https://github.com/dscripka/openWakeWord) (Apache-2.0). The pre-trained "hey jarvis" model is released by its author under **CC BY-NC-SA 4.0** (non-commercial). It is downloaded at install time, not distributed here.
- [Silero VAD](https://github.com/snakers4/silero-vad) (MIT), bundled with openWakeWord.
- [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) (Apache-2.0) through [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx) (MIT).
- [edge-tts](https://github.com/rany2/edge-tts) (LGPL-3.0), optional online voice.
- Speech recognition by [Groq](https://groq.com). Actions by [Claude Code](https://docs.claude.com/en/docs/claude-code/overview).

This is an independent community project. It is not affiliated with or endorsed by Anthropic, Groq, Microsoft or Marvel.
