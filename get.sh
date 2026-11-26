#!/usr/bin/env bash
# One-command installer for Jarvis Voice Assistant:
#
#   curl -fsSL https://raw.githubusercontent.com/ElvisGarcia009/jarvis-voice-assistant/main/get.sh | bash
#
# It downloads Jarvis (or updates an earlier download), offers to install the
# system packages it needs (asking before using sudo), then runs install.sh.
# Running it again later updates Jarvis and keeps your settings.
#
# Options (environment variables):
#   JARVIS_DIR   where the source code goes (default ~/.local/src/jarvis-voice-assistant)
#   JARVIS_REPO  git URL to download from
#   JARVIS_REF   branch or tag (default main)
set -euo pipefail

JARVIS_DIR="${JARVIS_DIR:-$HOME/.local/src/jarvis-voice-assistant}"
JARVIS_REPO="${JARVIS_REPO:-https://github.com/ElvisGarcia009/jarvis-voice-assistant.git}"
JARVIS_REF="${JARVIS_REF:-main}"

say()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m[x]\033[0m %s\n' "$*"; exit 1; }

# With `curl | bash` the script itself arrives on stdin, so questions are read
# from the terminal. Without a terminal, Jarvis installs with default answers.
has_tty() { { : < /dev/tty; } 2>/dev/null; }

ask_yes() {   # ask_yes "Question" -> 0 for yes (the default), 1 for no
  local answer
  has_tty || return 1
  read -rp "$1 [Y/n] " answer < /dev/tty || return 1
  [[ -z "$answer" || "$answer" =~ ^[YySs] ]]
}

# --------------------------------------------------------------- system packages
detect_packages() {
  # Sets PM, INSTALL (command prefix), REQUIRED and OPTIONAL package lists
  if command -v apt-get >/dev/null; then
    PM=apt; INSTALL="sudo apt-get install -y"
    REQUIRED="python3-venv python3-gi python3-gi-cairo gir1.2-gtk-3.0 pipewire-bin curl git"
    OPTIONAL="gir1.2-gtklayershell-0.1 playerctl"
  elif command -v dnf >/dev/null; then
    PM=dnf; INSTALL="sudo dnf install -y"
    REQUIRED="python3-gobject python3-cairo gtk3 pipewire-utils curl git"
    OPTIONAL="gtk-layer-shell playerctl"
  elif command -v pacman >/dev/null; then
    PM=pacman; INSTALL="sudo pacman -S --needed --noconfirm"
    REQUIRED="python-gobject python-cairo gtk3 pipewire curl git"
    OPTIONAL="gtk-layer-shell playerctl"
  else
    PM=""
  fi
}

is_installed() {
  case "$PM" in
    apt) dpkg-query -W -f='${Status}' "$1" 2>/dev/null | grep -q "install ok installed" ;;
    dnf) rpm -q "$1" >/dev/null 2>&1 ;;
    pacman) pacman -Q "$1" >/dev/null 2>&1 ;;
  esac
}

install_packages() {
  detect_packages
  if [ -z "$PM" ]; then
    warn "Unknown package manager: make sure Python 3.11+, venv, PyGObject (GTK 3), PipeWire, curl and git are installed."
    return
  fi
  local missing=() optional=() p
  for p in $REQUIRED; do is_installed "$p" || missing+=("$p"); done
  for p in $OPTIONAL; do is_installed "$p" || optional+=("$p"); done
  if [ ${#missing[@]} -eq 0 ] && [ ${#optional[@]} -eq 0 ]; then
    say "System packages: all present."
    return
  fi
  [ ${#missing[@]} -gt 0 ] && say "Needed system packages: ${missing[*]}"
  [ ${#optional[@]} -gt 0 ] && say "Recommended (bubble above all windows, fewer false wake-ups): ${optional[*]}"
  local all=("${missing[@]}" "${optional[@]}")
  if ask_yes "Install them now with sudo (it may ask for your password)?"; then
    [ "$PM" = apt ] && sudo apt-get update -qq
    # shellcheck disable=SC2086
    $INSTALL "${all[@]}" || warn "Some packages could not be installed."
  else
    warn "Skipped. To install them yourself:  $INSTALL ${all[*]}"
  fi
}

# --------------------------------------------------------------- source code
download() {
  if [ -d "$JARVIS_DIR/.git" ]; then
    say "Updating Jarvis in $JARVIS_DIR ..."
    git -C "$JARVIS_DIR" fetch --quiet --depth 1 origin "$JARVIS_REF" \
      && git -C "$JARVIS_DIR" checkout --quiet -B "$JARVIS_REF" FETCH_HEAD \
      || warn "Could not update; installing the copy that is already there."
  else
    [ -e "$JARVIS_DIR" ] && fail "$JARVIS_DIR exists but is not a Jarvis download. Move it or set JARVIS_DIR."
    say "Downloading Jarvis into $JARVIS_DIR ..."
    mkdir -p "$(dirname "$JARVIS_DIR")"
    git clone --quiet --depth 1 --branch "$JARVIS_REF" "$JARVIS_REPO" "$JARVIS_DIR"
  fi
}

main() {
  [ "$(id -u)" -ne 0 ] || fail "Run this as your normal user, not with sudo: Jarvis installs into your home folder."
  [ "$(uname -s)" = Linux ] || fail "Jarvis runs on Linux only."
  say "Jarvis Voice Assistant installer"
  install_packages
  command -v git >/dev/null || fail "git is required. Install it and run this command again."
  download
  if has_tty; then
    bash "$JARVIS_DIR/install.sh" < /dev/tty
  else
    warn "No terminal to ask questions: using the default answers."
    bash "$JARVIS_DIR/install.sh" < /dev/null
  fi
}

main "$@"   # everything above only defines functions: a cut-off download runs nothing
