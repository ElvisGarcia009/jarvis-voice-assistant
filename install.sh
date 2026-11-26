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
python3 -c 'import gi; gi.require_foreign("cairo")' 2>/dev/null || missing+=("python3-gi-cairo")
command -v pw-record >/dev/null || missing+=("pipewire tools (pw-record / pw-play)")
command -v curl >/dev/null || missing+=("curl")
command -v systemctl >/dev/null || missing+=("systemd")

if [ ${#missing[@]} -gt 0 ]; then
  warn "Missing: ${missing[*]}"
  echo "  Debian/Ubuntu/Pop!_OS: sudo apt install python3-venv python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-gtklayershell-0.1 pipewire-bin curl"
  echo "  Fedora:                sudo dnf install python3-gobject python3-cairo gtk3 gtk-layer-shell pipewire-utils curl"
  echo "  Arch:                  sudo pacman -S python-gobject python-cairo gtk3 gtk-layer-shell pipewire curl"
  fail "Install the missing packages and run ./install.sh again."
fi

# ---------------------------------------------------------------- 2. files
say "Installing Jarvis into $DATA_DIR ..."
mkdir -p "$DATA_DIR/models" "$CONFIG_DIR" "$SERVICE_DIR"
install -m 755 "$REPO_DIR/jarvis.py" "$DATA_DIR/jarvis.py"
install -m 644 "$REPO_DIR/jarvis_ui.py" "$DATA_DIR/jarvis_ui.py"
install -m 644 "$REPO_DIR/jarvis_stt.py" "$DATA_DIR/jarvis_stt.py"
python3 -c 'import gi; gi.require_version("GtkLayerShell", "0.1")' 2>/dev/null \
  || warn "Optional: install gtk-layer-shell (gir1.2-gtklayershell-0.1) so the bubble floats above all windows."

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
NEW_CONFIG=0
if [ ! -f "$CONFIG_DIR/config.toml" ]; then
  cp "$REPO_DIR/config.example.toml" "$CONFIG_DIR/config.toml"
  NEW_CONFIG=1
  say "Created $CONFIG_DIR/config.toml (edit it to change voice, language, name...)"
fi

# Read a value from the [stt] section of the config (empty if missing)
stt_setting() {
  python3 -c 'import sys, tomllib; c = tomllib.load(open(sys.argv[1], "rb")); print(c.get("stt", {}).get(sys.argv[2], ""))' \
    "$CONFIG_DIR/config.toml" "$1"
}

STT_ENGINE="$(stt_setting engine)"
if [ "$NEW_CONFIG" = 1 ]; then
  echo
  echo "How should Jarvis turn your voice into text?"
  echo "  1) On this computer: private, works offline, no account needed."
  echo "     Downloads a ~1.6 GB model (plus ~2 GB of GPU libraries with an NVIDIA card)."
  echo "  2) Online with Groq: smaller download, needs a free Groq API key."
  read -rp "Choose 1 or 2 [1]: " STT_CHOICE || STT_CHOICE=""   # no terminal: default
  if [ "${STT_CHOICE:-1}" = "2" ]; then STT_ENGINE="groq"; else STT_ENGINE="local"; fi
  # set `engine = ...` inside the [stt] section only
  awk -v e="$STT_ENGINE" '
    /^\[/ { in_stt = ($0 == "[stt]") }
    in_stt && /^engine *=/ { sub(/"[^"]*"/, "\"" e "\"") }
    { print }' "$CONFIG_DIR/config.toml" > "$CONFIG_DIR/config.toml.tmp" \
    && mv "$CONFIG_DIR/config.toml.tmp" "$CONFIG_DIR/config.toml"
fi

if [ "$STT_ENGINE" = "local" ]; then
  say "Installing local speech recognition (faster-whisper)..."
  "$VENV/bin/pip" install -q faster-whisper
  if command -v nvidia-smi >/dev/null && nvidia-smi >/dev/null 2>&1; then
    say "NVIDIA GPU found: installing CUDA libraries for fast recognition..."
    "$VENV/bin/pip" install -q nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"
  else
    warn "No NVIDIA GPU found: speech recognition will run on the CPU (slower)."
    warn "For faster results on CPU, set local_model = \"small\" in [stt]."
  fi
  STT_MODEL="$(stt_setting local_model)"
  GAMING_MODEL="$(stt_setting gaming_model)"
  say "Downloading the Whisper models (${STT_MODEL:-large-v3-turbo}, and ${GAMING_MODEL:-small} for gaming mode)..."
  "$VENV/bin/python" -c 'import sys; from faster_whisper import download_model; [download_model(m) for m in sys.argv[1:]]' \
    "${STT_MODEL:-large-v3-turbo}" "${GAMING_MODEL:-small}" >/dev/null
fi

if [ "$STT_ENGINE" != "local" ] && [ ! -s "$CONFIG_DIR/groq_key" ]; then
  echo
  echo "Jarvis uses Groq (free) to turn your voice into text."
  echo "Create a key at https://console.groq.com/keys and paste it below (it stays hidden)."
  read -rsp "Groq API key: " GROQ_KEY || GROQ_KEY=""; echo
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
fi

# ---------------------------------------------------------------- 7. service
say "Installing and starting the background service..."
install -m 644 "$REPO_DIR/jarvis.service" "$SERVICE_DIR/jarvis.service"
systemctl --user daemon-reload
systemctl --user enable jarvis.service >/dev/null 2>&1
systemctl --user restart jarvis.service

# ---------------------------------------------------------------- 8. summary
ok()   { printf '  \033[1;32m✓\033[0m %s\n' "$*"; }
miss() { printf '  \033[1;31m✗\033[0m %s\n' "$*"; PROBLEMS=1; }
opt()  { printf '  \033[1;33m•\033[0m %s\n' "$*"; }
PROBLEMS=0
sleep 3   # give the service a moment to start
echo
say "Summary"
if systemctl --user is-active --quiet jarvis.service; then
  ok "Jarvis is running in the background (starts with your desktop)"
else
  miss "Jarvis is not running: see  journalctl --user -u jarvis -n 30"
fi
if [ "$STT_ENGINE" = "local" ]; then
  if "$VENV/bin/python" -c 'import faster_whisper' 2>/dev/null; then
    if command -v nvidia-smi >/dev/null && nvidia-smi >/dev/null 2>&1; then
      ok "Speech recognition: on this computer, with your NVIDIA GPU"
    else
      ok "Speech recognition: on this computer, on the CPU"
    fi
  else
    miss "Speech recognition: faster-whisper is not installed (run ./install.sh again)"
  fi
elif [ -s "$CONFIG_DIR/groq_key" ]; then
  ok "Speech recognition: online with Groq (key saved)"
else
  miss "Speech recognition: Groq key missing (run ./install.sh again)"
fi
if [ -z "$CLAUDE_BIN" ]; then
  miss "Claude Code: not installed  →  curl -fsSL https://claude.ai/install.sh | bash"
elif "$CLAUDE_BIN" auth status 2>/dev/null | grep -q '"loggedIn": *true'; then
  ok "Claude Code: installed and logged in"
else
  miss "Claude Code: not logged in  →  $CLAUDE_BIN auth login   (then: systemctl --user restart jarvis)"
fi
if python3 -c 'import gi; gi.require_version("GtkLayerShell", "0.1")' 2>/dev/null; then
  ok "Floating bubble stays above all windows (gtk-layer-shell)"
else
  opt "Optional: gtk-layer-shell, so the bubble floats above all windows"
fi
if command -v playerctl >/dev/null; then
  ok "Fewer false wake-ups while videos or music play (playerctl)"
else
  opt "Optional: playerctl, so videos and music are less likely to wake Jarvis"
fi
echo
if [ "$PROBLEMS" = 0 ]; then
  say "Done! Say \"Hey Jarvis\" to start."
else
  warn "Almost done: fix the items marked ✗, then say \"Hey Jarvis\"."
fi
echo "    Settings: $CONFIG_DIR/config.toml   (then: systemctl --user restart jarvis)"
echo "    Log:      ~/.local/state/jarvis/jarvis.log"
echo "    Update:   run the same install command again"
