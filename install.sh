#!/usr/bin/env bash
# Jarvis Voice Assistant installer (per-user, no sudo needed for Jarvis itself).
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="$HOME/.local/share/jarvis"
CONFIG_DIR="$HOME/.config/jarvis"
SERVICE_DIR="$HOME/.config/systemd/user"
VENV="$DATA_DIR/venv"
KOKORO_URL="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"

say()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m[x]\033[0m %s\n' "$*"; exit 1; }

# ---------------------------------------------------------------- 1. checks
say "Checking system requirements..."
missing=()
command -v python3 >/dev/null || missing+=("python3")
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null \
  || fail "Python 3.11 or newer is required."
python3 -c 'import venv, ensurepip' 2>/dev/null || missing+=("python3-venv")
python3 -c 'import gi; gi.require_version("Gtk", "3.0"); from gi.repository import Gtk' 2>/dev/null \
  || missing+=("python3-gi + GTK 3 introspection")
command -v pw-record >/dev/null || missing+=("pipewire tools (pw-record / pw-play)")
command -v curl >/dev/null || missing+=("curl")
command -v systemctl >/dev/null || missing+=("systemd")

if [ ${#missing[@]} -gt 0 ]; then
  warn "Missing: ${missing[*]}"
  echo "  Debian/Ubuntu/Pop!_OS: sudo apt install python3-venv python3-gi gir1.2-gtk-3.0 pipewire-bin curl"
  echo "  Fedora:                sudo dnf install python3-gobject gtk3 pipewire-utils curl"
  echo "  Arch:                  sudo pacman -S python-gobject gtk3 pipewire curl"
  fail "Install the missing packages and run ./install.sh again."
fi

# ---------------------------------------------------------------- 2. files
say "Installing Jarvis into $DATA_DIR ..."
mkdir -p "$DATA_DIR/models" "$CONFIG_DIR" "$SERVICE_DIR"
install -m 755 "$REPO_DIR/jarvis.py" "$DATA_DIR/jarvis.py"

# ---------------------------------------------------------------- 3. python env
if [ ! -x "$VENV/bin/python" ]; then
  say "Creating Python environment (uses system GTK bindings)..."
  python3 -m venv --system-site-packages "$VENV"
fi
say "Installing Python packages (this can take a few minutes)..."
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q -r "$REPO_DIR/requirements.txt"
"$VENV/bin/pip" install -q --no-deps "openwakeword==0.6.0"

# ---------------------------------------------------------------- 4. models
say "Downloading the 'Hey Jarvis' wake word model..."
"$VENV/bin/python" -c 'from openwakeword import utils; utils.download_models(["hey_jarvis"])' >/dev/null

for f in kokoro-v1.0.int8.onnx voices-v1.0.bin; do
  if [ ! -s "$DATA_DIR/models/$f" ]; then
    say "Downloading Kokoro voice model: $f ..."
    curl -fL --progress-bar -o "$DATA_DIR/models/$f" "$KOKORO_URL/$f"
  fi
done

# ---------------------------------------------------------------- 5. config
if [ ! -f "$CONFIG_DIR/config.toml" ]; then
  cp "$REPO_DIR/config.example.toml" "$CONFIG_DIR/config.toml"
  say "Created $CONFIG_DIR/config.toml (edit it to change voice, language, name...)"
fi

if [ ! -s "$CONFIG_DIR/groq_key" ]; then
  echo
  echo "Jarvis uses Groq (free) to turn your voice into text."
  echo "Create a key at https://console.groq.com/keys and paste it below (it stays hidden)."
  read -rsp "Groq API key: " GROQ_KEY; echo
  [ -n "$GROQ_KEY" ] || fail "No key entered."
  ( umask 077; printf '%s\n' "$GROQ_KEY" > "$CONFIG_DIR/groq_key" )
  unset GROQ_KEY
  say "Key saved to $CONFIG_DIR/groq_key (readable only by you)."
fi

# ---------------------------------------------------------------- 6. claude code
CLAUDE_BIN="$(command -v claude || true)"
[ -z "$CLAUDE_BIN" ] && [ -x "$HOME/.local/bin/claude" ] && CLAUDE_BIN="$HOME/.local/bin/claude"
[ -z "$CLAUDE_BIN" ] && CLAUDE_BIN="$(ls -d "$HOME"/.config/Claude/claude-code/*/*/claude 2>/dev/null | sort -V | tail -1 || true)"
if [ -z "$CLAUDE_BIN" ]; then
  warn "Claude Code was not found. Install it and log in, then restart Jarvis:"
  echo "    curl -fsSL https://claude.ai/install.sh | bash"
  echo "    claude auth login"
else
  say "Claude Code found: $CLAUDE_BIN"
  echo "    If you have never logged in from a terminal, run:  $CLAUDE_BIN auth login"
fi

# ---------------------------------------------------------------- 7. service
say "Installing and starting the background service..."
install -m 644 "$REPO_DIR/jarvis.service" "$SERVICE_DIR/jarvis.service"
systemctl --user daemon-reload
systemctl --user enable jarvis.service >/dev/null 2>&1
systemctl --user restart jarvis.service

echo
say "Done! Say \"Hey Jarvis\" to start."
echo "    Settings: $CONFIG_DIR/config.toml   (then: systemctl --user restart jarvis)"
echo "    Log:      ~/.local/state/jarvis/jarvis.log"
