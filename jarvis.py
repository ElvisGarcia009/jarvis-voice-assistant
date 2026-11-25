#!/usr/bin/env python3
"""
Jarvis Voice Assistant for Linux.

Say "Hey Jarvis", ask for something, and Claude (through Claude Code) does it
on your computer, then answers out loud.

Pipeline:
  1. openWakeWord listens offline for "Hey Jarvis".
  2. Silero VAD records your request until you stop talking.
  3. Whisper turns your voice into text: locally on your GPU/CPU (faster-whisper)
     or online with Groq (many languages).
  4. Claude Code (`claude -p`) performs the task on your PC.
  5. Kokoro (local, fast) or Edge TTS (online) speaks the answer.
  6. The conversation continues until you say "thank you" or stay silent.

A floating bubble (jarvis_ui.py) shows an animated orb for the state
(sleeping / listening / thinking / speaking) and live captions.

Files:
  ~/.config/jarvis/config.toml      settings (see config.example.toml)
  ~/.config/jarvis/groq_key         Groq API key (never commit this!)
  ~/.local/state/jarvis/jarvis.log  log
"""

import asyncio
import collections
import fcntl
import glob
import io
import itertools
import json
import math
import logging
import os
import queue
import re
import select
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
import unicodedata
import wave

import numpy as np
import requests

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib  # noqa: E402

from jarvis_ui import Bubble  # noqa: E402

# ----------------------------------------------------------------------------
# Paths and settings
# ----------------------------------------------------------------------------
HOME = os.path.expanduser("~")
CONFIG_DIR = os.path.join(HOME, ".config", "jarvis")
STATE_DIR = os.path.join(HOME, ".local", "state", "jarvis")
DATA_DIR = os.path.join(HOME, ".local", "share", "jarvis")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.toml")
GROQ_KEY_FILE = os.path.join(CONFIG_DIR, "groq_key")
MEMORY_FILE = os.path.join(HOME, ".local", "state", "jarvis", "memory.json")
# While this file exists, speech recognition stays off the GPU (to leave all VRAM to games)
GAMING_FLAG = os.path.join(STATE_DIR, "gaming_mode")
# Every command Claude runs, with its output; a terminal window follows it live
ACTIVITY_LOG = os.path.join(STATE_DIR, "activity.log")
# "on" or "off", written by the voice commands "activate / deactivate terminal";
# it wins over [activity] show_terminal
ACTIVITY_SWITCH = os.path.join(STATE_DIR, "activity_terminal")
STT_WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_stt.py")

DEFAULTS = {
    "user": {"name": ""},
    "language": {
        "reply": "auto",   # "auto" = answer in the language you speak, or e.g. "English"
        "tutor": "",       # e.g. "Spanish": if you speak it, Jarvis also teaches you the
                           # sentence in the reply language (handy to practice a language)
    },
    "voice": {
        "engine": "kokoro",                     # "kokoro" (local) or "edge" (online)
        "kokoro_voice": "am_onyx+am_michael",   # one voice, or several joined with "+"
        "kokoro_speed": 1.15,
        "kokoro_deepen": 0.08,                  # 0 = normal pitch, 0.08 = 8% deeper
        "kokoro_lang": "en-us",
        "edge_voice": "en-US-AndrewMultilingualNeural",
    },
    "phrases": {
        "greeting": "Yes? What can I do for you?",
        "goodbye": "You're welcome. I'll be here if you need me.",
        "timeout": "I'll be here if you need me.",
        "working": "One moment, I'm checking that.",   # said when Claude starts using
                                                       # tools; "" = stay silent
        "terminal_on": "Terminal activated. I'll show you every command I run.",
        "terminal_off": "Terminal deactivated. I'll keep working in the background.",
    },
    "claude": {"model": "sonnet", "permission_mode": "auto", "timeout": 300},
    "stt": {
        "engine": "groq",                 # "groq" (online, free key) or "local" (offline)
        "local_model": "large-v3-turbo",  # faster-whisper model for engine = "local"
        "device": "auto",                 # "auto", "cuda" (NVIDIA GPU) or "cpu"
        "compute_type": "auto",           # "auto" = int8_float16 on GPU, int8 on CPU
        "language": "",                   # "" = detect automatically, or e.g. "en", "es"
        "unload_after": 60,               # seconds after a conversation to free the model
                                          # (and all GPU memory); -1 = keep it loaded
        "gaming_model": "small",          # model used on the CPU while gaming mode is on
    },
    "memory": {
        "enabled": True,
        "resume_hours": 12,           # wake up within this time = same conversation
        "max_context_tokens": 60000,  # bigger than this = summarize and start fresh
        "summary_model": "haiku",     # model used to write the summary
    },
    "wake": {
        "threshold": 0.5,       # minimum score (0..1) to accept "Hey Jarvis"
        "patience": 2,          # 80 ms chunks in a row that must reach it (1 = a single one)
        "media_threshold": 0.8, # used instead while a video or music plays (needs playerctl);
                                # 0 = off
    },
    "listening": {"wait_for_speech": 10.0, "end_silence": 2.0, "max_utterance": 60.0,
                  "continue_wait": 4.0},
    "ui": {"show_on_start": False},
    "activity": {
        "show_terminal": True,   # open a terminal that shows the commands Claude runs
        "terminal": "auto",      # "auto" or a command that runs what follows it,
                                 # e.g. "gnome-terminal --" or "kitty"
    },
    "interrupt": {
        "mode": "voice",        # "voice": just start talking | "wakeword": say "Hey Jarvis" | "off"
        "min_speech": 0.30,     # seconds of your voice needed to interrupt (avoids coughs)
        "vad_threshold": 0.50,  # how sure it must be that it's a human voice (0..1)
    },
}


def load_config():
    cfg = json.loads(json.dumps(DEFAULTS))
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "rb") as f:
            user = tomllib.load(f)
        for section, values in user.items():
            if isinstance(values, dict):
                cfg.setdefault(section, {}).update(values)
    return cfg


CFG = load_config()

RATE = 16000
CHUNK = 1280                 # 80 ms of audio
STEP = CHUNK / RATE
VAD_THRESHOLD = 0.5
START_SPEECH = 0.16
MIN_SPEECH = 0.30
WAKE_MODEL = "hey_jarvis"
NEAR_MISS = 0.3              # wake scores from here up are logged, to tune [wake] from real data

KOKORO_MODEL = os.path.join(DATA_DIR, "models", "kokoro-v1.0.int8.onnx")
KOKORO_VOICES = os.path.join(DATA_DIR, "models", "voices-v1.0.bin")

SOUND_WAKE = "/usr/share/sounds/freedesktop/stereo/message.oga"
SOUND_THINK = "/usr/share/sounds/freedesktop/stereo/dialog-information.oga"

END_PHRASES = [
    "thank you", "thanks", "that's all", "that is all", "that will be all",
    "goodbye", "bye", "you can rest", "go to sleep", "rest now", "see you",
    "muchas gracias", "gracias", "eso es todo", "nada mas", "adios", "hasta luego",
    "puedes descansar", "descansa", "a dormir",
]
# If the sentence asks for something, it is not a goodbye ("thanks, now open Steam")
REQUEST_WORDS = re.compile(
    r"\b(open|close|search|find|play|tell|show|install|check|start|run|what|how|why|"
    r"where|when|can you|could you|please|abre|cierra|busca|pon|dime|muestra|instala|"
    r"revisa|cuanto|donde|puedes)\b")
# If a sentence ends with one of these words, the user probably paused to think
UNFINISHED_WORDS = {
    "and", "but", "or", "so", "because", "then", "um", "uh", "uhm", "like", "the", "a",
    "an", "to", "of", "with", "for", "my", "your", "if", "about",
    "y", "o", "pero", "que", "porque", "entonces", "este", "eh", "em", "mmm", "de", "el",
    "la", "los", "las", "un", "una", "mi", "con", "para", "por", "si", "como", "en",
}
# Phrases Whisper tends to hallucinate on pure noise
HALLUCINATIONS = ["amara.org", "subtitulos", "subtitles by", "suscribete"]
# Where one spoken sentence ends and the next begins
SENTENCE_BREAK = re.compile(r"(?<=[.!?…:;])\s+|(?<=[.!?…][\"”'’])\s+")


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
log = logging.getLogger("jarvis")


def setup_logging():
    """Called from main(), so importing this module (e.g. in tests) has no side effects."""
    os.makedirs(STATE_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(os.path.join(STATE_DIR, "jarvis.log")),
                  logging.StreamHandler(sys.stdout)],
    )


def single_instance():
    lock = open(os.path.join(STATE_DIR, "jarvis.lock"), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        log.error("Another Jarvis is already running. Exiting.")
        sys.exit(0)
    return lock


def normalize(text):
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"[^\w\s']", " ", text).strip()


def rms(chunk):
    return float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))


def is_goodbye(text):
    clean = normalize(text)
    if not any(re.search(r"\b" + re.escape(p) + r"\b", clean) for p in END_PHRASES):
        return False
    return len(clean.split()) <= 12 and not REQUEST_WORDS.search(clean)


def looks_unfinished(text):
    """True if the sentence seems cut in the middle ("open the folder and...")."""
    stripped = text.strip()
    if not stripped:
        return False
    if stripped.endswith(("...", "…", ",", "-", "—")):
        return True
    if stripped[-1] in ".?!":
        # Whisper often adds a final period even when you only paused
        stripped = stripped[:-1]
    words = normalize(stripped).split()
    return bool(words) and words[-1] in UNFINISHED_WORDS


def speakable(text):
    """Removes markdown symbols that should not be read aloud."""
    return re.sub(r"[*_`#>|]", "", text).strip()


class SentenceStream:
    """Collects text while Claude writes it and hands out each sentence once it
    is complete, so Jarvis can start speaking before the whole answer exists."""

    def __init__(self):
        self.buf = ""

    def add(self, text):
        """Adds a piece of text; returns the sentences it completed."""
        *done, self.buf = SENTENCE_BREAK.split(self.buf + text)
        return [" ".join(d.split()) for d in done if d.strip()]

    def flush(self):
        """Returns whatever is left (the end of a reply), as one last sentence."""
        rest, self.buf = " ".join(self.buf.split()), ""
        return [rest] if rest else []


# Terminal apps and the option that makes them run a command, most likely first
# (the app must stay running while its window is open, so Jarvis can reuse and close it)
TERMINALS = [("cosmic-term", ["-e"]), ("ptyxis", ["--"]), ("gnome-terminal", ["--wait", "--"]),
             ("konsole", ["-e"]), ("xfce4-terminal", ["--disable-server", "-x"]), ("kitty", []),
             ("alacritty", ["-e"]), ("foot", []), ("xterm", ["-e"]),
             ("x-terminal-emulator", ["-e"])]
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07")
BOLD, DIM, RED, GREEN, CYAN, RESET = ("\x1b[1m", "\x1b[2m", "\x1b[31m", "\x1b[32m",
                                       "\x1b[36m", "\x1b[0m")


def format_tool_call(name, args):
    """One tool call as the activity terminal shows it: `$ command` for the shell."""
    if name == "Bash":
        note = f"{DIM}# {args['description']}{RESET}\n" if args.get("description") else ""
        return f"{note}{GREEN}${RESET} {BOLD}{args.get('command', '')}{RESET}\n"
    detail = next((str(args[k]) for k in ("file_path", "path", "pattern", "url", "query",
                                          "description", "prompt") if args.get(k)), "")
    return f"{CYAN}▸ {name}{RESET} {detail[:200]}\n"


def format_tool_output(text, is_error=False, full=True, max_lines=30, max_chars=4000):
    """A tool's result: the whole output for shell commands (cut if long), a short
    summary for the rest (file contents, search results...)."""
    text = ANSI.sub("", text).replace("\r", "").rstrip()
    if not text:
        return f"{DIM}  (no output){RESET}\n" if not is_error else ""
    lines = text.splitlines()
    if not full and not is_error:
        return f"{DIM}  ↳ {len(lines)} line{'s' if len(lines) != 1 else ''}{RESET}\n"
    shown = "\n".join(lines[:max_lines])[:max_chars]
    if len(lines) > max_lines or len(text) > len(shown):
        shown += f"\n… ({len(lines) - shown.count(chr(10)) - 1} more lines)"
    if is_error:
        return "".join(f"{RED}  {line}{RESET}\n" for line in shown.splitlines())
    return "".join(f"  {line}\n" for line in shown.splitlines())


TERMINAL_OFF = re.compile(
    r"\b(deactivate|disable|turn off|hide|desactiva|desactivar|apaga|apagar|oculta|ocultar|"
    r"quita|quitar)( the| la| el)? terminal\b|\bturn( the)? terminal off\b")
TERMINAL_ON = re.compile(
    r"\b(activate|enable|turn on|show|activa|activar|enciende|encender|muestra|mostrar|"
    r"pon)( the| la| el)? terminal\b|\bturn( the)? terminal on\b")


# Words people add around a command ("okay, wait... can you deactivate the terminal please?")
FILLER_WORDS = {
    "okay", "ok", "wait", "yeah", "yes", "yep", "hey", "jarvis", "please", "can", "could",
    "would", "will", "you", "um", "uh", "uhm", "eh", "so", "now", "just", "and", "alright",
    "right", "well", "i", "want", "need", "to", "go", "ahead", "sir", "listen", "again",
    "oye", "por", "favor", "puedes", "podrias", "quiero", "que", "ya", "bueno", "vale", "este",
    "ahora", "mira", "otra", "vez",
}


def terminal_switch(text):
    """True for "activate terminal", False for "deactivate terminal", else None.
    Filler words are ignored; what is left must be just the command, so a real
    request about a terminal still goes to Claude ("open the terminal" launches
    the terminal app, so it is not a switch). Claude also knows how to flip the
    switch, for other ways of saying it (see build_system_prompt)."""
    words = [w for w in normalize(text).split() if w not in FILLER_WORDS]
    if not words or len(words) > 4:
        return None
    clean = " ".join(words)
    if TERMINAL_OFF.search(clean):
        return False
    if TERMINAL_ON.search(clean):
        return True
    return None


def terminal_command(setting):
    """The command that opens a terminal running what follows it, or None."""
    if setting and setting != "auto":
        return shlex.split(setting)
    for name, option in TERMINALS:
        if shutil.which(name):
            return [name, *option]
    return None


class ActivityConsole:
    """Shows what Claude does on the computer: every command and its output is
    written to activity.log, and a terminal window follows that file live. It
    opens with the first command, is reused for the next ones and closes when
    the conversation ends."""

    def __init__(self):
        ac = CFG["activity"]
        self.default = bool(ac["show_terminal"])
        self.broken = False      # no terminal app could be opened
        self.terminal = ac["terminal"]
        self.viewer = None
        self.request = None      # your request, written above its first command
        self.names = {}          # tool call id -> tool name
        self.lock = threading.Lock()
        try:   # keep the file small: start over when it passes 1 MB
            if os.path.getsize(ACTIVITY_LOG) > 1_000_000:
                os.replace(ACTIVITY_LOG, ACTIVITY_LOG + ".old")
        except OSError:
            pass

    def start(self, text):
        with self.lock:
            self.request, self.names = text, {}

    def _write(self, text):
        with open(ACTIVITY_LOG, "a") as f:
            f.write(text)

    def tool_call(self, block):
        with self.lock:
            name = block.get("name") or "?"
            self.names[block.get("id")] = name
            try:
                start = os.path.getsize(ACTIVITY_LOG)
            except OSError:
                start = 0
            text = ""
            if self.request is not None:
                text = f"\n{BOLD}━━ {time.strftime('%H:%M')}  {self.request}{RESET}\n"
                self.request = None
            self._write(text + format_tool_call(name, block.get("input") or {}))
            if ACTIVITY_SWITCH not in json.dumps(block.get("input") or {}):
                self._open_viewer(start)   # (not just to show the switch being flipped)

    def tool_result(self, block):
        content = block.get("content")
        if isinstance(content, list):
            content = "\n".join(c.get("text", "") for c in content
                                if isinstance(c, dict) and c.get("type") == "text")
        with self.lock:
            name = self.names.get(block.get("tool_use_id"))
            if name:
                self._write(format_tool_output(str(content or ""), bool(block.get("is_error")),
                                               full=name == "Bash"))

    def note(self, text):
        """A line after the commands of this request (cancelled, too slow...)."""
        with self.lock:
            if self.names:
                self._write(f"{RED}  {text}{RESET}\n")

    def enabled(self):
        try:
            with open(ACTIVITY_SWITCH) as f:
                return f.read().strip() != "off"
        except OSError:
            return self.default

    def set_enabled(self, on):
        """The voice commands "activate terminal" / "deactivate terminal"."""
        with open(ACTIVITY_SWITCH, "w") as f:
            f.write("on\n" if on else "off\n")
        self.broken = False
        log.info("Activity terminal %s", "activated" if on else "deactivated")
        if not on:
            self.close()

    def close(self):
        """Closes the terminal window (Jarvis went back to sleep)."""
        with self.lock:
            viewer, self.viewer = self.viewer, None
        if viewer is None or viewer.poll() is not None:
            return
        viewer.terminate()
        try:
            viewer.wait(timeout=3)
        except subprocess.TimeoutExpired:
            viewer.kill()
            viewer.wait()
        log.info("Activity terminal closed")

    def _open_viewer(self, start):
        if self.broken or not self.enabled() or (self.viewer and self.viewer.poll() is None):
            return
        command = terminal_command(self.terminal)
        if not command:
            log.info("No terminal app found: commands are only written to %s", ACTIVITY_LOG)
            self.broken = True
            return
        script = ('printf "\\033]0;Jarvis activity\\007"; '
                  'echo "What Jarvis does on your computer. You can close this window."; '
                  'exec tail -c "+$1" -F "$2"')
        try:
            self.viewer = subprocess.Popen(
                command + ["bash", "-c", script, "jarvis", str(start + 1), ACTIVITY_LOG],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True)
            log.info("Activity terminal opened (%s)", command[0])
        except OSError as e:
            log.warning("Could not open the activity terminal: %s", e)
            self.broken = True


def notify(title, body):
    try:
        subprocess.run(
            ["gdbus", "call", "--session", "--dest", "org.freedesktop.Notifications",
             "--object-path", "/org/freedesktop/Notifications",
             "--method", "org.freedesktop.Notifications.Notify",
             "Jarvis", "0", "audio-input-microphone-symbolic", title, body[:300],
             "[]", "{}", "6000"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
    except Exception:
        pass


def claude_binary():
    found = shutil.which("claude")
    if found:
        return found
    for candidate in (os.path.join(HOME, ".local", "bin", "claude"),
                      os.path.join(HOME, ".claude", "local", "claude")):
        if os.access(candidate, os.X_OK):
            return candidate
    # Claude Code bundled with the Claude desktop app
    bundled = sorted(glob.glob(os.path.join(HOME, ".config/Claude/claude-code/*/*/claude")))
    if bundled:
        return bundled[-1]
    raise RuntimeError("Claude Code ('claude') was not found. Install it first.")


def system_description():
    distro = "Linux"
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    distro = line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "unknown desktop")
    session = os.environ.get("XDG_SESSION_TYPE", "")
    return f"{distro} ({desktop}{', ' + session if session else ''})"


def build_system_prompt():
    name = CFG["user"]["name"].strip()
    who = name if name else "the user"
    reply = CFG["language"]["reply"].strip()
    tutor = CFG["language"]["tutor"].strip()
    if reply.lower() in ("", "auto"):
        language = "- Answer in the same language the user speaks."
    else:
        language = (f"- Always answer in clear, simple, natural {reply}, even if {who} speaks "
                    f"another language. Only switch language if {who} explicitly asks.")
        if tutor:
            language += (f"\n- {who} is practicing {reply}. If {who} spoke in {tutor} (fully or "
                         f"partly), begin with one short line like \"In {reply}, you can say: ...\" "
                         f"with a natural {reply} version of the request. Then answer.")
    return f"""
Your name is Jarvis, the personal voice assistant of {who}, on a computer running
{system_description()}.

LANGUAGE:
{language}

HOW TO ANSWER (your answer will be HEARD out loud and shown in a small window):
- Talk naturally and briefly, like on the phone: 1 to 3 sentences, unless asked for detail.
- NEVER use lists, bullet points, tables, headings, bold text, emojis, links or code blocks.
- Do not read long commands or file paths aloud; say in words what you did or found.

HOW TO ACT:
- Do the tasks yourself on the computer with your tools.
- Launch graphical apps without blocking (for example with setsid or gtk-launch).
- sudo does not work here because it needs a password. If something needs sudo, say in one
  sentence what is needed and that {who} should do it from a terminal.
- Before anything irreversible or sensitive (deleting or overwriting files, uninstalling,
  changing system settings, sending messages, buying something), do NOT do it yet: say what
  you will do and ask {who} to confirm with "yes". Only do it after the confirmation.
- If you are not sure what {who} wants, ask in one sentence.

ACTIVITY TERMINAL (a window that shows {who} every command you run, live, while you talk):
- "Activate / deactivate the terminal" (or "show / hide the terminal", "activa / desactiva la
  terminal") means this window, NOT opening or closing the terminal app.
- Turn it on with: echo on > {ACTIVITY_SWITCH}
- Turn it off with: echo off > {ACTIVITY_SWITCH}
- It is off only if that file contains "off". Jarvis applies the change right away.

GAMING MODE (keeps your speech recognition off the graphics card so games get all the VRAM):
- Turn it on with: touch {GAMING_FLAG}
- Turn it off with: rm -f {GAMING_FLAG}
- It is on if that file exists. It only changes how you hear {who}, not how you answer.
""".strip()


# ----------------------------------------------------------------------------
# Microphone (PipeWire's pw-record gives raw 16 kHz mono 16-bit audio)
# ----------------------------------------------------------------------------
class Microphone:
    def __init__(self):
        self.q = queue.Queue(maxsize=500)
        self.proc = subprocess.Popen(
            ["pw-record", "--rate", str(RATE), "--channels", "1",
             "--format", "s16", "--latency", "40ms", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        size = CHUNK * 2
        while True:
            data = self.proc.stdout.read(size)
            if not data or len(data) < size:
                log.error("Microphone stopped sending audio")
                os._exit(1)  # systemd restarts us
            try:
                self.q.put_nowait(np.frombuffer(data, dtype=np.int16))
            except queue.Full:
                try:
                    self.q.get_nowait()
                except queue.Empty:
                    pass

    def read(self, timeout=1.0):
        return self.q.get(timeout=timeout)

    def flush(self):
        while not self.q.empty():
            try:
                self.q.get_nowait()
            except queue.Empty:
                break


# ----------------------------------------------------------------------------
# Wake word ("Hey Jarvis" with openWakeWord)
# ----------------------------------------------------------------------------
class MediaWatch:
    """Knows whether a video or music is playing (YouTube, Netflix, Spotify, VLC...),
    by asking `playerctl` (MPRIS) every couple of seconds in a background thread,
    so the 80 ms wake loop only reads a flag."""

    INTERVAL = 1.5

    def __init__(self):
        self.playing = False
        self.binary = shutil.which("playerctl")
        if not self.binary:
            log.info("playerctl is not installed: [wake] media_threshold is not used")
            return
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while True:
            try:
                out = subprocess.run([self.binary, "--all-players", "status"],
                                     capture_output=True, text=True, timeout=3).stdout
                playing = "Playing" in out.split()
            except Exception:
                playing = False
            if playing != self.playing:
                log.info("Media %s", "playing: stricter wake threshold" if playing
                         else "stopped: normal wake threshold")
                self.playing = playing
            time.sleep(self.INTERVAL)


class WakeDetector:
    """Feeds 80 ms microphone chunks to openWakeWord and decides when to wake up.

    The score must stay at or above the threshold for `patience` chunks in a row:
    a real "Hey Jarvis" holds a high score for several chunks, while a sound-alike
    in a video usually spikes for one. (openWakeWord's own `patience` argument is
    not used: it stores the zeroed scores in its history, so it never fires.)
    While media is playing, the stricter `media_threshold` is used instead.

    Scores between NEAR_MISS and a wake-up are logged (at most once per second, as
    the peak of that moment), so false triggers can be compared with a real
    "Hey Jarvis" in the log."""

    def __init__(self, model):
        wc = CFG["wake"]
        self.model = model
        self.threshold = float(wc["threshold"])
        self.media_threshold = float(wc["media_threshold"])
        self.patience = max(1, int(wc["patience"]))
        self.media = MediaWatch() if self.media_threshold > self.threshold else None
        self.run = 0             # chunks in a row at or above the threshold
        self.peak = 0.0          # highest score not logged yet
        self.held = 0            # longest run not logged yet
        self.last_log = 0.0

    def feed(self, chunk):
        """Returns a description of the detection ("score 0.93, 3 chunks") or None."""
        score = float(self.model.predict(chunk).get(WAKE_MODEL, 0.0))
        threshold = (self.media_threshold if self.media and self.media.playing
                     else self.threshold)
        self.run = self.run + 1 if score >= threshold else 0
        if self.run >= self.patience:
            detected = f"score {max(score, self.peak):.2f}, {self.run} chunks ≥ {threshold:.2f}"
            self.run, self.peak, self.held = 0, 0.0, 0
            return detected
        if score >= NEAR_MISS:
            self.peak = max(self.peak, score)
            self.held = max(self.held, self.run)
            return None
        now = time.monotonic()
        if self.peak and now - self.last_log >= 1.0:   # the spike is over: log its peak
            log.info("Near miss: wake score %.2f, %d of %d chunks ≥ %.2f",
                     self.peak, self.held, self.patience, threshold)
            self.peak, self.held, self.last_log = 0.0, 0, now
        return None

    def reset(self):
        self.model.reset()
        self.run, self.peak, self.held = 0, 0.0, 0


# ----------------------------------------------------------------------------
# Local speech recognition (faster-whisper in a child process, see jarvis_stt.py)
# ----------------------------------------------------------------------------
def gaming_mode():
    return os.path.exists(GAMING_FLAG)


class LocalSTT:
    """Starts the Whisper worker when Jarvis wakes up and stops it a while after
    the conversation. Only ending the process frees all GPU memory (CUDA context
    included), so while Jarvis sleeps it uses no VRAM."""

    def __init__(self):
        self.proc = None
        self.spec = None             # (model, device, compute) of the running worker
        self.ready = threading.Event()
        self.error = None
        self.lock = threading.RLock()
        self.timer = None

    @staticmethod
    def wanted():
        sc = CFG["stt"]
        if gaming_mode():
            return (sc["gaming_model"], "cpu", "int8")
        return (sc["local_model"], sc["device"], sc["compute_type"])

    def load(self):
        """Starts loading in the background (no-op if the right model is running)."""
        with self.lock:
            self._cancel_timer()
            spec = self.wanted()
            if self.proc and self.proc.poll() is None and self.spec == spec:
                return
            self._stop()
            self.spec, self.error = spec, None
            self.ready.clear()
            self.proc = subprocess.Popen([sys.executable, STT_WORKER, *spec],
                                         stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            threading.Thread(target=self._wait_ready, args=(self.proc,), daemon=True).start()

    def _wait_ready(self, proc):
        line = proc.stdout.readline()
        try:
            msg = json.loads(line)
        except ValueError:
            msg = {"error": "the worker stopped while loading"}
        with self.lock:
            if proc is not self.proc:
                return
            if "error" in msg:
                self.error = msg["error"]
                log.error("Local speech recognition unavailable: %s", self.error)
            else:
                log.info("Local speech recognition loaded (%s on %s, %s, %.1fs)",
                         msg["model"], msg["device"], msg["compute"], msg["seconds"])
            self.ready.set()

    def transcribe(self, audio, language=None):
        self.load()
        if not self.ready.wait(timeout=120):
            raise RuntimeError("the speech model took too long to load")
        with self.lock:
            proc = self.proc
            if self.error or proc is None:
                raise RuntimeError(self.error or "the speech model was unloaded")
            request = json.dumps({"samples": len(audio), "language": language}) + "\n"
            try:
                proc.stdin.write(request.encode())
                proc.stdin.write(np.asarray(audio, np.float32).tobytes())
                proc.stdin.flush()
                readable, _, _ = select.select([proc.stdout], [], [], 60)
                line = proc.stdout.readline() if readable else b""
            except (BrokenPipeError, OSError) as e:
                line = b""
                log.error("Speech worker pipe error: %s", e)
            if not line:
                self._stop()
                raise RuntimeError("the speech worker stopped responding")
            msg = json.loads(line)
            if "error" in msg:
                raise RuntimeError(msg["error"])
            return msg["text"]

    def unload_later(self, seconds):
        """Frees the model after `seconds` (0 = now, negative = never)."""
        with self.lock:
            self._cancel_timer()
            if self.proc is None or seconds < 0:
                return
            if seconds == 0 or (gaming_mode() and self.spec and self.spec[1] != "cpu"):
                self._stop()
                return
            self.timer = threading.Timer(seconds, self.unload)
            self.timer.daemon = True
            self.timer.start()

    def unload(self):
        with self.lock:
            self._stop()

    def _cancel_timer(self):
        if self.timer:
            self.timer.cancel()
            self.timer = None

    def _stop(self):
        proc, self.proc, self.spec = self.proc, None, None
        self.ready.clear()
        if proc is None:
            return
        try:
            proc.stdin.close()        # the worker exits when its input closes
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
            proc.wait()
        log.info("Local speech recognition unloaded (memory freed)")


# ----------------------------------------------------------------------------
# Assistant
# ----------------------------------------------------------------------------
class Assistant:
    def __init__(self):
        from openwakeword.model import Model
        from openwakeword.vad import VAD
        self.wake = WakeDetector(Model(wakeword_models=[WAKE_MODEL], inference_framework="onnx"))
        self.vad = VAD()
        self.mic = Microphone()
        self.session = None
        self.memory = {}
        self.groq_key = self._load_groq_key()
        # loaded on demand when Jarvis wakes up, freed after the conversation
        self.stt = LocalSTT() if CFG["stt"]["engine"] == "local" else None
        self.console = ActivityConsole()
        self.system_prompt = build_system_prompt()
        self.window = None
        self.manual_wake = threading.Event()
        self.end_requested = threading.Event()
        self.speak_cancel = threading.Event()
        self.player = None
        self.player_lock = threading.Lock()
        # Voice interruption: a second voice detector watches the mic while Jarvis talks
        self.barge_vad = VAD()
        self.barge_frames = None     # your first words, kept when you interrupt
        # For the bubble: live microphone level and a timeline of what is being spoken
        self.mic_level = 0.0
        self.voice_timeline = []     # [(start, end, text, envelope, fps)]
        self.voice_lock = threading.Lock()
        self.kokoro = None
        v = CFG["voice"]
        self.deepen = float(v["kokoro_deepen"])
        if v["engine"] == "kokoro":
            try:
                from kokoro_onnx import Kokoro
                self.kokoro = Kokoro(KOKORO_MODEL, KOKORO_VOICES)
                names = [n.strip() for n in str(v["kokoro_voice"]).split("+") if n.strip()]
                if len(names) == 1:
                    self.voice_style = names[0]
                else:
                    styles = [self.kokoro.get_voice_style(n) for n in names]
                    self.voice_style = sum(styles) / len(styles)
                self.kokoro.create("Ready.", voice=self.voice_style, lang=v["kokoro_lang"])
                log.info("Kokoro voice ready (%s)", v["kokoro_voice"])
            except Exception as e:
                log.warning("Kokoro unavailable, using Edge TTS: %s", e)
                self.kokoro = None

    def _load_groq_key(self):
        key = os.environ.get("GROQ_API_KEY", "").strip()
        if not key and os.path.exists(GROQ_KEY_FILE):
            key = open(GROQ_KEY_FILE).read().strip()
        if key or CFG["stt"]["engine"] == "local":
            return key or None   # with local speech recognition the key is only a fallback
        log.error("Missing Groq API key in %s", GROQ_KEY_FILE)
        notify("Jarvis", "Missing Groq API key. Run install.sh again.")
        sys.exit(1)

    # ---------- local speech recognition (faster-whisper, offline) ----------
    def _transcribe_local(self, wav):
        with wave.open(io.BytesIO(wav)) as w:
            audio = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        started = time.monotonic()
        self.stt.load()   # restarts the worker if gaming mode changed
        loading = not self.stt.ready.is_set()
        text = self.stt.transcribe(audio, CFG["stt"]["language"].strip() or None)
        log.info("Transcribed locally in %.2fs%s", time.monotonic() - started,
                 " (including waiting for the model to load)" if loading else "")
        return text

    def ui(self, method, *args):
        if self.window:
            GLib.idle_add(getattr(self.window, method), *args)

    # ---------- sound ----------
    def _play(self, path):
        with self.player_lock:
            self.player = subprocess.Popen(["pw-play", path],
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            self.player.wait(timeout=180)
        except Exception:
            self.player.kill()
        finally:
            with self.player_lock:
                self.player = None

    def stop_speaking(self):
        self.speak_cancel.set()
        with self.player_lock:
            if self.player and self.player.poll() is None:
                self.player.kill()
                log.info("Interrupted by the user")

    def end_conversation(self):
        self.end_requested.set()
        self.stop_speaking()

    # ---------- what the bubble shows while Jarvis speaks ----------
    PLAYBACK_LATENCY = 0.15   # seconds between writing audio and hearing it

    def _timeline_reset(self):
        with self.voice_lock:
            self.voice_timeline = []

    def _timeline_add(self, text, audio, rate):
        """Remember when this piece will be heard and how loud it is over time."""
        fps = 30
        audio = np.asarray(audio, dtype=np.float32)
        hop = max(1, int(rate / fps))
        frames = len(audio) // hop
        env = (np.sqrt(np.mean(audio[:frames * hop].reshape(frames, hop) ** 2, axis=1))
               if frames else np.zeros(1))
        env = np.clip(env / 0.12, 0, 1)
        duration = len(audio) / rate
        now = time.monotonic()
        with self.voice_lock:
            start = max(now + self.PLAYBACK_LATENCY,
                        self.voice_timeline[-1][1] if self.voice_timeline else 0)
            self.voice_timeline.append((start, start + duration, text, env, fps))

    def _timeline_current(self):
        now = time.monotonic()
        with self.voice_lock:
            for item in self.voice_timeline:
                if item[0] <= now < item[1]:
                    return item, now
            if self.voice_timeline and now < self.voice_timeline[0][0]:
                return self.voice_timeline[0], None
        return None, now

    def current_caption(self):
        item, _ = self._timeline_current()
        return item[2] if item else None

    def voice_level(self):
        if self.speak_cancel.is_set():
            return 0.0
        item, now = self._timeline_current()
        if item is None:
            return 0.0
        if now is None:   # first piece not audible yet
            return 0.0
        start, _end, _text, env, fps = item
        return float(env[min(len(env) - 1, int((now - start) * fps))])

    @staticmethod
    def _sentences(text):
        return [p.strip() for p in SENTENCE_BREAK.split(" ".join(text.split())) if p.strip()] or [text]

    def _kokoro_pieces(self, sentences):
        """First piece is short (up to the first comma) so speech starts sooner."""
        sentences = iter(sentences)
        first = next(sentences, None)
        if first is None:
            return
        m = re.match(r"^(.{8,60}?[,—–])\s+(.+)$", first)
        if m and len(first) > 50:
            yield m.group(1)
            yield m.group(2)
        else:
            yield first
        yield from sentences

    def _speak_kokoro(self, sentences):
        """Synthesizes locally and streams audio to the speaker while it is created.
        `sentences` may still be growing (Claude is writing the rest). Returns None
        when done, or the sentences not spoken yet if Kokoro failed."""
        v = CFG["voice"]
        play_rate = 24000 * (1 - self.deepen)
        player = subprocess.Popen(
            # playing slightly slower than synthesized = deeper pitch
            ["pw-play", "--raw", "--format", "f32", "--rate", str(int(play_rate)),
             "--channels", "1", "-"],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with self.player_lock:
            self.player = player
        pieces = self._kokoro_pieces(sentences)
        try:
            for piece in pieces:
                if self.speak_cancel.is_set() or self.end_requested.is_set():
                    break
                try:
                    audio, _ = self.kokoro.create(piece, voice=self.voice_style,
                                                  speed=float(v["kokoro_speed"]) / (1 - self.deepen),
                                                  lang=v["kokoro_lang"])
                except Exception as e:
                    log.warning("Kokoro failed: %s", e)
                    player.kill()
                    player.wait()
                    return itertools.chain([piece], pieces)
                self._timeline_add(piece, audio, play_rate)
                self.ui("set_state", "speaking")
                try:
                    player.stdin.write(np.asarray(audio, dtype=np.float32).tobytes())
                    player.stdin.flush()
                except (BrokenPipeError, ValueError):
                    break  # interrupted
            try:
                player.stdin.close()
            except Exception:
                pass
            try:
                player.wait(timeout=180)
            except subprocess.TimeoutExpired:
                player.kill()
                player.wait()
        finally:
            with self.player_lock:
                self.player = None
        return None

    def _synth_edge(self, text):
        import edge_tts
        mp3 = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False).name
        voice = CFG["voice"]["edge_voice"]
        for _ in range(2):
            try:
                asyncio.run(edge_tts.Communicate(text, voice).save(mp3))
                if os.path.getsize(mp3) > 0:
                    return mp3
            except Exception as e:
                log.warning("Edge TTS failed: %s", e)
        os.remove(mp3)
        return None

    def _speak_edge(self, sentences):
        """Online voice, sentence by sentence (the next one is prepared while one plays)."""
        ready = queue.Queue()

        def producer():
            for sentence in sentences:
                if self.speak_cancel.is_set() or self.end_requested.is_set():
                    break
                ready.put((sentence, self._synth_edge(sentence)))
            ready.put(None)

        threading.Thread(target=producer, daemon=True).start()
        while True:
            item = ready.get()
            if item is None:
                break
            sentence, mp3 = item
            if mp3 is None:
                continue
            if not self.speak_cancel.is_set() and not self.end_requested.is_set():
                self._fake_timeline(sentence)
                self.ui("set_state", "speaking")
                self._play(mp3)
            os.remove(mp3)

    def _fake_timeline(self, text):
        """Edge TTS gives no samples here, so animate the orb with a gentle pulse."""
        words = max(1, len(text.split()))
        t = np.linspace(0, words / 2.6, int(words / 2.6 * 30) + 1)
        env = 0.45 + 0.35 * np.abs(np.sin(t * 7))
        now = time.monotonic()
        with self.voice_lock:
            self.voice_timeline = [(now, now + words / 2.6, text, env, 30)]

    def _barge_monitor(self, done):
        """Runs while Jarvis speaks. Stops him when you start talking (or say
        "Hey Jarvis", in wakeword mode) and keeps the words you already said."""
        ic = CFG["interrupt"]
        mode = ic["mode"]
        min_speech, threshold = float(ic["min_speech"]), float(ic["vad_threshold"])
        self.mic.flush()
        self.barge_vad.reset_states()
        pre = collections.deque(maxlen=10)   # ~0.8 s of audio before the interruption
        run, elapsed = 0.0, 0.0
        stats = {"chunks": 0, "max_vad": 0.0, "max_rms": 0.0, "max_run": 0.0}
        try:
            self._barge_loop(done, mode, min_speech, threshold, pre, stats)
        finally:
            log.info("Interrupt monitor: %d chunks, max voice score %.2f, max loudness %.0f, "
                     "longest speech %.2fs", stats["chunks"], stats["max_vad"],
                     stats["max_rms"], stats["max_run"])

    def _barge_loop(self, done, mode, min_speech, threshold, pre, stats):
        run, elapsed = 0.0, 0.0
        while not done.is_set():
            try:
                chunk = self.mic.read(timeout=0.3)
            except queue.Empty:
                continue
            elapsed += STEP
            stats["chunks"] += 1
            stats["max_rms"] = max(stats["max_rms"], rms(chunk))
            pre.append(chunk)
            if elapsed < 0.3:      # ignore the very start (speaker click, own breath)
                continue
            if mode == "wakeword":
                detected = self.wake.feed(chunk)
                if detected:
                    log.info("Interrupted by wake word (%s)", detected)
                    self.wake.reset()
                    self.barge_frames = []
                    self.stop_speaking()
                    return
                continue
            score = self.barge_vad.predict(chunk, frame_size=640)
            stats["max_vad"] = max(stats["max_vad"], score)
            if score > threshold:
                run += STEP
                stats["max_run"] = max(stats["max_run"], run)
                if run >= min_speech:
                    log.info("Interrupted by voice")
                    self.barge_frames = list(pre)
                    self.stop_speaking()
                    return
            else:
                run = max(0.0, run - STEP / 2)   # tolerate tiny gaps between syllables

    def _take_barge(self):
        frames, self.barge_frames = self.barge_frames, None
        return frames

    def speak(self, text, show=True, interruptible=True):
        text = speakable(text)
        if not text:
            return
        log.info("Jarvis: %s", text)
        if show:
            self.ui("add_message", "jarvis", text)
        self._speak_sentences(self._sentences(text), interruptible)

    def _speak_sentences(self, sentences, interruptible=True):
        """Speaks sentences one by one. `sentences` can be a generator that waits
        for Claude to write the next one."""
        self.speak_cancel.clear()
        self.barge_frames = None
        self._timeline_reset()
        done = threading.Event()
        monitor = None
        if interruptible and CFG["interrupt"]["mode"] in ("voice", "wakeword"):
            monitor = threading.Thread(target=self._barge_monitor, args=(done,), daemon=True)
            monitor.start()
        started_at = time.monotonic()
        try:
            rest = self._speak_kokoro(sentences) if self.kokoro else sentences
            if rest is not None:
                self._speak_edge(rest)
        finally:
            log.info("Spoke for %.1fs%s", time.monotonic() - started_at,
                     " (interrupted)" if self.speak_cancel.is_set() else "")
            done.set()
            if monitor:
                monitor.join(timeout=1)
            self._timeline_reset()
            if self.barge_frames is None:
                self.mic.flush()  # do not listen to ourselves
            # if you interrupted, keep the live audio so no word is lost

    # ---------- listening ----------
    def _update_mic_level(self, chunk):
        """0..1 loudness of your voice (log scale, smoothed) for the orb animation."""
        db = 20 * math.log10(rms(chunk) + 1)
        target = min(1.0, max(0.0, (db - 22) / 36))
        self.mic_level = 0.6 * self.mic_level + 0.4 * target

    def listen(self, wait_for=None, prefill=None):
        """Returns a WAV of the user's sentence, or None if nobody spoke in time.
        `prefill`: audio already captured when the user interrupted Jarvis."""
        lc = CFG["listening"]
        wait_for = float(wait_for if wait_for is not None else lc["wait_for_speech"])
        end_silence, max_len = float(lc["end_silence"]), float(lc["max_utterance"])
        if not prefill:
            self.mic.flush()
        self.vad.reset_states()
        self.ui("set_state", "listening")
        waited = 0.0
        pre = collections.deque(maxlen=6)
        while waited < wait_for:
            frames, run, started = [], 0.0, False
            if prefill:   # you were already talking: continue recording right away
                frames, run, started = list(prefill), MIN_SPEECH, True
                prefill = None
            while waited < wait_for and not started:
                if self.end_requested.is_set():
                    return None
                try:
                    chunk = self.mic.read(timeout=2)
                except queue.Empty:
                    continue
                waited += STEP
                pre.append(chunk)
                self._update_mic_level(chunk)
                if self.vad.predict(chunk, frame_size=640) > VAD_THRESHOLD:
                    run += STEP
                    if run >= START_SPEECH:
                        started = True
                        frames.extend(pre)
                else:
                    run = 0.0
            if not started:
                return None
            voiced, silent, total = run, 0.0, 0.0
            while True:
                if self.end_requested.is_set():
                    return None
                try:
                    chunk = self.mic.read(timeout=2)
                except queue.Empty:
                    continue
                frames.append(chunk)
                self._update_mic_level(chunk)
                total += STEP
                if self.vad.predict(chunk, frame_size=640) > VAD_THRESHOLD:
                    voiced += STEP
                    silent = 0.0
                else:
                    silent += STEP
                if silent >= end_silence or total >= max_len:
                    break
            if voiced >= MIN_SPEECH:
                buf = io.BytesIO()
                with wave.open(buf, "wb") as w:
                    w.setnchannels(1)
                    w.setsampwidth(2)
                    w.setframerate(RATE)
                    w.writeframes(np.concatenate(frames).tobytes())
                return buf.getvalue()
            # just a short noise: keep waiting
        return None

    def transcribe(self, wav):
        text = None
        if self.stt:
            try:
                text = self._transcribe_local(wav)
            except Exception as e:
                log.error("Local transcription failed: %s%s", e,
                          " (falling back to Groq)" if self.groq_key else "")
            if text is None and not self.groq_key:
                raise RuntimeError("Local speech recognition is not working and there is no Groq key")
        if text is None:
            r = requests.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self.groq_key}"},
                files={"file": ("audio.wav", wav, "audio/wav")},
                data={"model": "whisper-large-v3-turbo", "temperature": "0",
                      "response_format": "json"},
                timeout=30)
            r.raise_for_status()
            text = r.json().get("text", "").strip()
        if any(h in normalize(text) for h in HALLUCINATIONS):
            return ""
        return text

    # ---------- memory between conversations ----------
    # memory.json = {"session_id", "last_used", "context_tokens", "summary"}
    def _load_memory(self):
        try:
            with open(MEMORY_FILE) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_memory(self, mem):
        tmp = MEMORY_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(mem, f, indent=2, ensure_ascii=False)
        os.chmod(tmp, 0o600)
        os.replace(tmp, MEMORY_FILE)

    def _resume_session(self):
        """Continue the previous Claude session if it was used recently."""
        mc = CFG["memory"]
        self.memory = self._load_memory() if mc["enabled"] else {}
        last = self.memory.get("last_used", 0)
        if self.memory.get("session_id") and time.time() - last < float(mc["resume_hours"]) * 3600:
            self.session = self.memory["session_id"]
            log.info("Continuing previous conversation (%s tokens of context)",
                     self.memory.get("context_tokens", "?"))
        else:
            self.session = None

    def _system_prompt_with_memory(self):
        summary = self.memory.get("summary", "").strip() if CFG["memory"]["enabled"] else ""
        if not summary:
            return self.system_prompt
        return (self.system_prompt + "\n\nMEMORY FROM EARLIER CONVERSATIONS (use it when relevant, "
                "do not read it aloud):\n" + summary)

    def _run_claude(self, text, model, session, system_prompt):
        c = CFG["claude"]
        cmd = [claude_binary(), "-p", text, "--output-format", "json",
               "--model", model, "--permission-mode", c["permission_mode"],
               "--append-system-prompt", system_prompt]
        if session:
            cmd += ["--resume", session]
        out = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL,
                             timeout=int(c["timeout"]), cwd=HOME)
        try:
            return json.loads(out.stdout), out
        except json.JSONDecodeError:
            return None, out

    @staticmethod
    def _context_tokens(data):
        """How big the conversation is now, from Claude Code's usage report.
        A reply with tools makes several API calls and `usage` adds them all up,
        so use the LAST call: its input is the whole conversation so far."""
        u = data.get("usage") or {}
        calls = u.get("iterations") or []
        last = calls[-1] if calls and isinstance(calls[-1], dict) else u
        return sum(int(last.get(k) or 0) for k in ("input_tokens", "cache_creation_input_tokens",
                                                   "cache_read_input_tokens", "output_tokens"))

    def compact_memory(self):
        """Summarize the long conversation, then start fresh with that summary as memory."""
        if not self.memory.get("session_id"):
            return
        log.info("Conversation is large (%s tokens): summarizing it...",
                 self.memory.get("context_tokens"))
        request = ("Write private notes for your future self about what you LEARNED in our "
                   "conversations: facts about the user and their computer, their preferences, "
                   "decisions, and anything still pending. Merge the earlier memory if there is "
                   "one. Do NOT repeat your instructions, rules or how you should answer; you "
                   "will get those again. At most 10 short lines, plain text, no tools. If "
                   "nothing worth remembering happened, answer exactly: (nothing)")
        try:
            data, out = self._run_claude(request, CFG["memory"]["summary_model"],
                                         self.memory["session_id"],
                                         self._system_prompt_with_memory())
        except subprocess.TimeoutExpired:
            data = None
        if not data or data.get("is_error") or not (data.get("result") or "").strip():
            log.error("Could not summarize the conversation; keeping it as is")
            return
        summary = data["result"].strip()
        if summary == "(nothing)":
            summary = self.memory.get("summary", "")
        self.memory = {"summary": summary, "session_id": None,
                       "last_used": time.time(), "context_tokens": 0}
        self._save_memory(self.memory)
        log.info("Memory compacted. New summary:\n%s", self.memory["summary"])

    # ---------- Claude ----------
    def _run_claude_stream(self, text, model, session, system_prompt, on_event):
        """Runs Claude Code and reads its answer while it is being written.
        `on_event(kind, value)` gets ("session", id), ("text", piece), ("text_end", None)
        ("tool", name) as soon as a tool starts, then ("tool_call", block) with its full
        input and ("tool_result", block). Claude is stopped on timeout or when you end the
        conversation (✕, or the orb while thinking). Returns (result event or None,
        status, other output), status being "ok", "timeout" or "cancelled"."""
        c = CFG["claude"]
        cmd = [claude_binary(), "-p", text, "--output-format", "stream-json", "--verbose",
               "--include-partial-messages", "--model", model,
               "--permission-mode", c["permission_mode"], "--append-system-prompt", system_prompt]
        if session:
            cmd += ["--resume", session]
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, cwd=HOME,
                                start_new_session=True)   # own process group: see _stop_claude
        lines = queue.Queue()
        other = collections.deque(maxlen=40)   # stderr and non-JSON lines, for error messages

        def read_stdout():
            for line in iter(proc.stdout.readline, ""):
                lines.put(line)
            lines.put(None)

        def read_stderr():
            for line in iter(proc.stderr.readline, ""):
                other.append(line)

        threading.Thread(target=read_stdout, daemon=True).start()
        threading.Thread(target=read_stderr, daemon=True).start()
        deadline = time.monotonic() + int(c["timeout"])
        result, status = None, "ok"
        try:
            while True:
                if self.end_requested.is_set():
                    status = "cancelled"
                    break
                if time.monotonic() > deadline:
                    status = "ok" if result else "timeout"
                    break
                try:
                    line = lines.get(timeout=0.2)
                except queue.Empty:
                    continue
                if line is None:
                    break
                try:
                    event = json.loads(line)
                except ValueError:
                    other.append(line)
                    continue
                if not isinstance(event, dict) or event.get("parent_tool_use_id"):
                    continue   # a subagent's work, not the reply
                kind = event.get("type")
                if kind == "system" and event.get("subtype") == "init":
                    on_event("session", event.get("session_id"))
                elif kind == "stream_event":
                    ev = event.get("event") or {}
                    delta = ev.get("delta") or {}
                    block = ev.get("content_block") or {}
                    if ev.get("type") == "content_block_delta" and delta.get("type") == "text_delta":
                        on_event("text", delta.get("text") or "")
                    elif ev.get("type") == "content_block_start" and block.get("type") == "tool_use":
                        on_event("tool", block.get("name") or "")
                    elif ev.get("type") == "content_block_stop":
                        on_event("text_end", None)
                elif kind in ("assistant", "user"):
                    for block in (event.get("message") or {}).get("content") or []:
                        if isinstance(block, dict) and block.get("type") == "tool_use":
                            on_event("tool_call", block)
                        elif isinstance(block, dict) and block.get("type") == "tool_result":
                            on_event("tool_result", block)
                elif kind == "result":
                    result = event
                    deadline = min(deadline, time.monotonic() + 10)   # it should exit now
        finally:
            if status == "ok" and proc.poll() is None:
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
            if proc.poll() is None:
                self._stop_claude(proc)
        return result, status, "".join(other)

    @staticmethod
    def _stop_claude(proc):
        """Ends Claude Code and every command it started: they share its process
        group (apps it launched with setsid have their own and keep running)."""
        def signal_group(sig):
            try:
                os.killpg(proc.pid, sig)
            except (ProcessLookupError, PermissionError):
                pass

        signal_group(signal.SIGTERM)
        until = time.monotonic() + 3
        # waitid(WNOWAIT) sees the exit without reaping it, so the group id stays ours
        while time.monotonic() < until and not os.waitid(
                os.P_PID, proc.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT):
            time.sleep(0.1)
        signal_group(signal.SIGKILL)   # whatever is still running
        proc.wait()                    # reap it: no zombie left behind
        log.info("Claude stopped")

    def ask_and_speak(self, text):
        """Asks Claude and speaks the answer sentence by sentence while it is still
        being written (Claude runs in a background thread)."""
        c = CFG["claude"]
        log.info("Asking Claude: %s", text)
        self.console.start(text)
        sentences = queue.Queue()     # complete sentences to speak; None = the end
        splitter = SentenceStream()
        said = []                     # what Jarvis says, for the bubble and the log
        info = {"session": None, "streamed": False}

        def say(parts):
            for part in parts:
                part = speakable(part)
                if part:
                    said.append(part)
                    self.ui("add_message", "jarvis", " ".join(said))
                    sentences.put(part)

        def on_event(kind, value):
            if kind == "session":
                info["session"] = value
            elif kind == "text":
                info["streamed"] = True
                say(splitter.add(value))
            elif kind == "text_end":
                say(splitter.flush())
            elif kind == "tool":
                say(splitter.flush())
                log.info("Claude is using %s", value)
                if not said:   # nothing said yet: avoid a long silence while it works
                    say([CFG["phrases"]["working"]])
            elif kind in ("tool_call", "tool_result"):
                try:
                    (self.console.tool_call if kind == "tool_call" else self.console.tool_result)(value)
                except Exception as e:
                    log.warning("Activity terminal: %s", e)

        def worker():
            try:
                data, status, output = self._run_claude_stream(
                    text, c["model"], self.session, self._system_prompt_with_memory(), on_event)
                say(splitter.flush())
                self._after_claude(data, status, output, info, say)
            except Exception as e:
                log.exception("Claude request failed: %s", e)
                say(["I had a problem talking to Claude."])
            finally:
                sentences.put(None)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        first = self._next_sentence(sentences)   # the orb keeps "thinking" until then
        if first is not None:
            self._speak_sentences(itertools.chain([first], self._more_sentences(sentences)))
        if thread.is_alive():
            # you interrupted: let Claude finish its task silently (your words are kept)
            self.ui("set_state", "listening")
            thread.join()
        if not self.console.enabled():
            self.console.close()   # Claude turned the activity terminal off
        if said:
            log.info("Jarvis: %s", " ".join(said))

    def _next_sentence(self, sentences):
        while not self.end_requested.is_set():
            try:
                return sentences.get(timeout=0.1)
            except queue.Empty:
                continue
        return None

    def _more_sentences(self, sentences):
        """Yields sentences as Claude writes them; stops if you interrupt."""
        while not (self.speak_cancel.is_set() or self.end_requested.is_set()):
            try:
                sentence = sentences.get(timeout=0.1)
            except queue.Empty:
                continue
            if sentence is None:
                return
            yield sentence

    def _after_claude(self, data, status, output, info, say):
        """Errors, memory and the session id, once Claude is done."""
        if data:
            self.session = data.get("session_id") or self.session
        elif info["session"]:
            self.session = info["session"]
        if status == "cancelled":
            log.info("Request cancelled by the user")
            self.console.note("✕ Cancelled")
        elif status == "timeout":
            self.console.note("⏱ Stopped: it was taking too long")
            say(["That is taking too long. It's better to do it directly in Claude Code."])
        elif data is None:
            log.error("Unexpected Claude output: %s", output[-500:])
            if "login" in output.lower():
                say(["I'm not logged in to Claude. Run claude auth login in a terminal."])
            else:
                say(["I had a problem talking to Claude."])
        else:
            if data.get("is_error"):
                log.error("Claude returned an error: %s", str(data)[:500])
            if not info["streamed"]:
                say(self._sentences((data.get("result") or "").strip() or "Done."))
        if CFG["memory"]["enabled"] and self.session:
            self.memory.update({"session_id": self.session, "last_used": time.time()})
            if data:
                self.memory["context_tokens"] = self._context_tokens(data)
            self._save_memory(self.memory)

    # ---------- conversation ----------
    def conversation(self):
        p = CFG["phrases"]
        self._resume_session()
        self.end_requested.clear()
        self.ui("add_separator")
        self._play(SOUND_WAKE)
        self.speak(p["greeting"])
        while not self.end_requested.is_set():
            # if you interrupted Jarvis, your first words are already recorded
            wav = self.listen(prefill=self._take_barge())
            if self.end_requested.is_set():
                break
            if wav is None:
                self.speak(p["timeout"], interruptible=False)
                return
            self.ui("set_state", "thinking")
            try:
                text = self.transcribe(wav)
            except Exception as e:
                log.error("Transcription failed: %s", e)
                self.speak("Sorry, I couldn't hear you well. Please say it again.")
                continue
            if not text:
                self.speak("Sorry, I didn't catch that. Can you repeat it?")
                continue
            # Paused to think in the middle of a sentence? Keep listening for the rest.
            while looks_unfinished(text) and not self.end_requested.is_set():
                log.info("Sentence looks unfinished, waiting for the rest: %s", text)
                more = self.listen(wait_for=float(CFG["listening"]["continue_wait"]))
                if more is None:
                    break
                self.ui("set_state", "thinking")
                try:
                    extra = self.transcribe(more)
                except Exception as e:
                    log.error("Transcription failed: %s", e)
                    break
                if not extra:
                    break
                text = text.rstrip(" .…") + " " + extra
            log.info("User: %s", text)
            self.ui("add_message", "user", text)
            switch = terminal_switch(text)
            if switch is not None:   # "activate terminal" / "deactivate terminal"
                self.console.set_enabled(switch)
                self.speak(p["terminal_on" if switch else "terminal_off"])
                continue
            if is_goodbye(text):
                self.speak(p["goodbye"], interruptible=False)
                return
            self._play(SOUND_THINK)
            self.ask_and_speak(text)

    def run(self):
        log.info("Jarvis ready. Waiting for 'Hey Jarvis'...")
        notify("Jarvis", "Ready. Say “Hey Jarvis” when you need me.")
        while True:
            if self.manual_wake.is_set():
                self.manual_wake.clear()
                self._run_conversation("manual wake")
                continue
            try:
                chunk = self.mic.read(timeout=0.5)
            except queue.Empty:
                continue
            detected = self.wake.feed(chunk)
            if detected:
                self._run_conversation(detected)

    def _run_conversation(self, why):
        log.info("Wake up (%s)", why)
        if self.stt:
            self.stt.load()   # loads while Jarvis greets you and you speak
        try:
            self.conversation()
        except Exception as e:
            log.exception("Conversation error: %s", e)
            self.speak("Something went wrong. I'll wait for you.")
        self.end_requested.clear()
        self.wake.reset()
        self.mic.flush()
        self.ui("sleep_and_hide")
        self.console.close()
        if self.stt:
            self.stt.unload_later(float(CFG["stt"]["unload_after"]))
        # auto-compact after the conversation, so it never delays an answer
        mc = CFG["memory"]
        if mc["enabled"] and self.memory.get("context_tokens", 0) > int(mc["max_context_tokens"]):
            try:
                self.compact_memory()
            except Exception as e:
                log.exception("Memory compaction failed: %s", e)
        log.info("Waiting for 'Hey Jarvis'...")


def main():
    setup_logging()
    signal.signal(signal.SIGTERM, lambda *_: os._exit(0))
    signal.signal(signal.SIGINT, lambda *_: os._exit(0))
    _lock = single_instance()  # noqa: F841 (keep the lock open)
    assistant = Assistant()
    # `systemctl --user kill --kill-whom=main -s USR1 jarvis` wakes Jarvis (handy for a keyboard shortcut)
    signal.signal(signal.SIGUSR1, lambda *_: assistant.manual_wake.set())
    assistant.window = Bubble(assistant)
    if CFG["ui"]["show_on_start"]:
        assistant.window.set_state("sleeping")
        assistant.window.show()
    threading.Thread(target=assistant.run, daemon=True).start()
    Gtk.main()


if __name__ == "__main__":
    main()
