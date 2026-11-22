#!/usr/bin/env python3
"""
Jarvis Voice Assistant for Linux.

Say "Hey Jarvis", ask for something, and Claude (through Claude Code) does it
on your computer, then answers out loud.

Pipeline:
  1. openWakeWord listens offline for "Hey Jarvis".
  2. Silero VAD records your request until you stop talking.
  3. Groq Whisper turns your voice into text (many languages).
  4. Claude Code (`claude -p`) performs the task on your PC.
  5. Kokoro (local, fast) or Edge TTS (online) speaks the answer.
  6. The conversation continues until you say "thank you" or stay silent.

A small GTK window shows the state (sleeping / listening / thinking / speaking),
the conversation, and buttons to talk, interrupt, or end.

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
import json
import logging
import os
import queue
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import tomllib
import unicodedata
import wave

import numpy as np
import requests

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Pango  # noqa: E402

# ----------------------------------------------------------------------------
# Paths and settings
# ----------------------------------------------------------------------------
HOME = os.path.expanduser("~")
CONFIG_DIR = os.path.join(HOME, ".config", "jarvis")
STATE_DIR = os.path.join(HOME, ".local", "state", "jarvis")
DATA_DIR = os.path.join(HOME, ".local", "share", "jarvis")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.toml")
GROQ_KEY_FILE = os.path.join(CONFIG_DIR, "groq_key")

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
    },
    "claude": {"model": "sonnet", "permission_mode": "auto", "timeout": 300},
    "wake": {"threshold": 0.5},
    "listening": {"wait_for_speech": 10.0, "end_silence": 1.2, "max_utterance": 30.0},
    "ui": {"show_on_start": False},
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
# Phrases Whisper tends to hallucinate on pure noise
HALLUCINATIONS = ["amara.org", "subtitulos", "subtitles by", "suscribete"]


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
os.makedirs(STATE_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(os.path.join(STATE_DIR, "jarvis.log")),
              logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("jarvis")


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


def is_goodbye(text):
    clean = normalize(text)
    if not any(re.search(r"\b" + re.escape(p) + r"\b", clean) for p in END_PHRASES):
        return False
    return len(clean.split()) <= 12 and not REQUEST_WORDS.search(clean)


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
# Window
# ----------------------------------------------------------------------------
CSS = b"""
window.jarvis { background: #15171c; }
.status-box { background: #1f232b; border-radius: 14px; padding: 14px; }
.status-icon { font-size: 34px; }
.status-text { color: #e8eaed; font-size: 16px; font-weight: bold; }
.status-sub { color: #9aa0a6; font-size: 12px; }
.sleeping { border: 2px solid #3c4043; }
.listening { border: 2px solid #34a853; }
.thinking { border: 2px solid #fbbc04; }
.speaking { border: 2px solid #4f8ef7; }
.bubble-user { background: #2b3a55; color: #e8eaed; border-radius: 12px; padding: 8px 12px; }
.bubble-jarvis { background: #262a31; color: #e8eaed; border-radius: 12px; padding: 8px 12px; }
.who { color: #9aa0a6; font-size: 11px; font-weight: bold; }
button { border-radius: 10px; }
"""

STATES = {
    "sleeping":  ("😴", "Sleeping", "Say “Hey Jarvis” to wake me up"),
    "listening": ("👂", "Listening…", "Speak now"),
    "thinking":  ("🧠", "Thinking…", "Working on your request"),
    "speaking":  ("🔊", "Speaking…", "Press “Stop talking” to interrupt"),
}


class JarvisWindow(Gtk.Window):
    def __init__(self, assistant):
        super().__init__(title="Jarvis")
        self.set_default_size(440, 560)
        self.get_style_context().add_class("jarvis")
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            self.get_screen(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.connect("delete-event", lambda *_: self.hide() or True)  # close = hide

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        root.set_border_width(12)
        self.add(root)

        self.status_box = Gtk.Box(spacing=12)
        self.status_box.get_style_context().add_class("status-box")
        self.icon = Gtk.Label()
        self.icon.get_style_context().add_class("status-icon")
        texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.status = Gtk.Label(xalign=0)
        self.status.get_style_context().add_class("status-text")
        self.sub = Gtk.Label(xalign=0)
        self.sub.get_style_context().add_class("status-sub")
        texts.pack_start(self.status, False, False, 0)
        texts.pack_start(self.sub, False, False, 0)
        self.status_box.pack_start(self.icon, False, False, 0)
        self.status_box.pack_start(texts, True, True, 0)
        root.pack_start(self.status_box, False, False, 0)

        self.scroller = Gtk.ScrolledWindow()
        self.scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.chat = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.scroller.add(self.chat)
        root.pack_start(self.scroller, True, True, 0)

        buttons = Gtk.Box(spacing=8, homogeneous=True)
        talk = Gtk.Button(label="🎤 Talk")
        stop = Gtk.Button(label="🤫 Stop talking")
        end = Gtk.Button(label="✋ End")
        talk.connect("clicked", lambda *_: assistant.manual_wake.set())
        stop.connect("clicked", lambda *_: assistant.stop_speaking())
        end.connect("clicked", lambda *_: assistant.end_conversation())
        for b in (talk, stop, end):
            buttons.pack_start(b, True, True, 0)
        root.pack_start(buttons, False, False, 0)

        root.show_all()
        self.set_state("sleeping")

    # Called from other threads through GLib.idle_add
    def set_state(self, state):
        icon, title, sub = STATES[state]
        self.icon.set_text(icon)
        self.status.set_text(title)
        self.sub.set_text(sub)
        ctx = self.status_box.get_style_context()
        for s in STATES:
            ctx.remove_class(s)
        ctx.add_class(state)
        if state != "sleeping" and not self.get_visible():
            self.show()
        if state == "listening":
            self.present()
        return False

    def sleep_and_hide(self):
        self.set_state("sleeping")
        self.hide()
        return False

    def add_message(self, who, text):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        label_who = Gtk.Label(label="YOU" if who == "user" else "JARVIS",
                              xalign=1 if who == "user" else 0)
        label_who.get_style_context().add_class("who")
        msg = Gtk.Label(label=text, xalign=0, wrap=True, selectable=True)
        msg.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        msg.set_max_width_chars(42)
        msg.get_style_context().add_class("bubble-user" if who == "user" else "bubble-jarvis")
        msg.set_halign(Gtk.Align.END if who == "user" else Gtk.Align.START)
        box.pack_start(label_who, False, False, 0)
        box.pack_start(msg, False, False, 0)
        self.chat.pack_start(box, False, False, 0)
        box.show_all()
        GLib.timeout_add(60, self._scroll_bottom)
        return False

    def add_separator(self):
        sep = Gtk.Separator()
        self.chat.pack_start(sep, False, False, 4)
        sep.show()
        return False

    def _scroll_bottom(self):
        adj = self.scroller.get_vadjustment()
        adj.set_value(adj.get_upper())
        return False


# ----------------------------------------------------------------------------
# Assistant
# ----------------------------------------------------------------------------
class Assistant:
    def __init__(self):
        from openwakeword.model import Model
        from openwakeword.vad import VAD
        self.wake = Model(wakeword_models=[WAKE_MODEL], inference_framework="onnx")
        self.vad = VAD()
        self.mic = Microphone()
        self.session = None
        self.groq_key = self._load_groq_key()
        self.system_prompt = build_system_prompt()
        self.window = None
        self.manual_wake = threading.Event()
        self.end_requested = threading.Event()
        self.speak_cancel = threading.Event()
        self.player = None
        self.player_lock = threading.Lock()
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
        if key:
            return key
        log.error("Missing Groq API key in %s", GROQ_KEY_FILE)
        notify("Jarvis", "Missing Groq API key. Run install.sh again.")
        sys.exit(1)

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

    @staticmethod
    def _sentences(text):
        return [p.strip() for p in re.split(r"(?<=[.!?…:;])\s+", text) if p.strip()] or [text]

    def _kokoro_pieces(self, text):
        """First piece is short (up to the first comma) so speech starts sooner."""
        sentences = self._sentences(text)
        m = re.match(r"^(.{8,60}?[,—–])\s+(.+)$", sentences[0])
        if m and len(sentences[0]) > 50:
            return [m.group(1), m.group(2)] + sentences[1:]
        return sentences

    def _speak_kokoro(self, text):
        """Synthesizes locally and streams audio to the speaker while it is created."""
        v = CFG["voice"]
        player = subprocess.Popen(
            # playing slightly slower than synthesized = deeper pitch
            ["pw-play", "--raw", "--format", "f32", "--rate", str(int(24000 * (1 - self.deepen))),
             "--channels", "1", "-"],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with self.player_lock:
            self.player = player
        started = False
        try:
            for piece in self._kokoro_pieces(text):
                if self.speak_cancel.is_set() or self.end_requested.is_set():
                    break
                audio, _ = self.kokoro.create(piece, voice=self.voice_style,
                                              speed=float(v["kokoro_speed"]) / (1 - self.deepen),
                                              lang=v["kokoro_lang"])
                if not started:
                    self.ui("set_state", "speaking")
                    started = True
                try:
                    player.stdin.write(np.asarray(audio, dtype=np.float32).tobytes())
                    player.stdin.flush()
                except (BrokenPipeError, ValueError):
                    break  # interrupted
            try:
                player.stdin.close()
            except Exception:
                pass
            player.wait(timeout=180)
        except Exception as e:
            log.warning("Kokoro failed: %s", e)
            player.kill()
            return False
        finally:
            with self.player_lock:
                self.player = None
        return True

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

    def _speak_edge(self, text):
        """Online voice, sentence by sentence (the next one is prepared while one plays)."""
        ready = queue.Queue()

        def producer():
            for sentence in self._sentences(text):
                if self.speak_cancel.is_set() or self.end_requested.is_set():
                    break
                ready.put(self._synth_edge(sentence))
            ready.put(False)

        threading.Thread(target=producer, daemon=True).start()
        while True:
            mp3 = ready.get()
            if mp3 is False:
                break
            if mp3 is None:
                continue
            if not self.speak_cancel.is_set() and not self.end_requested.is_set():
                self.ui("set_state", "speaking")
                self._play(mp3)
            os.remove(mp3)

    def speak(self, text, show=True):
        text = re.sub(r"[*_`#>|]", "", text).strip()
        if not text:
            return
        log.info("Jarvis: %s", text)
        if show:
            self.ui("add_message", "jarvis", text)
        self.speak_cancel.clear()
        try:
            if self.kokoro is None or not self._speak_kokoro(text):
                self._speak_edge(text)
        finally:
            self.mic.flush()  # do not listen to ourselves

    # ---------- listening ----------
    def listen(self):
        """Returns a WAV of the user's sentence, or None if nobody spoke in time."""
        lc = CFG["listening"]
        wait_for, end_silence, max_len = (float(lc["wait_for_speech"]),
                                          float(lc["end_silence"]), float(lc["max_utterance"]))
        self.mic.flush()
        self.vad.reset_states()
        self.ui("set_state", "listening")
        waited = 0.0
        pre = collections.deque(maxlen=6)
        while waited < wait_for:
            frames, run, started = [], 0.0, False
            while waited < wait_for and not started:
                if self.end_requested.is_set():
                    return None
                try:
                    chunk = self.mic.read(timeout=2)
                except queue.Empty:
                    continue
                waited += STEP
                pre.append(chunk)
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

    # ---------- Claude ----------
    def ask_claude(self, text):
        c = CFG["claude"]
        cmd = [claude_binary(), "-p", text, "--output-format", "json",
               "--model", c["model"], "--permission-mode", c["permission_mode"],
               "--append-system-prompt", self.system_prompt]
        if self.session:
            cmd += ["--resume", self.session]
        log.info("Asking Claude: %s", text)
        try:
            out = subprocess.run(cmd, capture_output=True, text=True,
                                 timeout=int(c["timeout"]), cwd=HOME)
        except subprocess.TimeoutExpired:
            return "That is taking too long. It's better to do it directly in Claude Code."
        try:
            data = json.loads(out.stdout)
        except json.JSONDecodeError:
            log.error("Unexpected Claude output: %s %s", out.stdout[-500:], out.stderr[-500:])
            if "login" in (out.stdout + out.stderr).lower():
                return "I'm not logged in to Claude. Run claude auth login in a terminal."
            return "I had a problem talking to Claude."
        self.session = data.get("session_id") or self.session
        if data.get("is_error"):
            log.error("Claude returned an error: %s", str(data)[:500])
        return (data.get("result") or "").strip() or "Done."

    # ---------- conversation ----------
    def conversation(self):
        p = CFG["phrases"]
        self.session = None
        self.end_requested.clear()
        self.ui("add_separator")
        self._play(SOUND_WAKE)
        self.speak(p["greeting"])
        while not self.end_requested.is_set():
            wav = self.listen()
            if self.end_requested.is_set():
                break
            if wav is None:
                self.speak(p["timeout"])
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
            log.info("User: %s", text)
            self.ui("add_message", "user", text)
            if is_goodbye(text):
                self.speak(p["goodbye"])
                return
            self._play(SOUND_THINK)
            reply = self.ask_claude(text)
            if self.end_requested.is_set():
                break
            self.speak(reply)

    def run(self):
        log.info("Jarvis ready. Waiting for 'Hey Jarvis'...")
        notify("Jarvis", "Ready. Say “Hey Jarvis” when you need me.")
        threshold = float(CFG["wake"]["threshold"])
        while True:
            if self.manual_wake.is_set():
                self.manual_wake.clear()
                self._run_conversation("Talk button")
                continue
            try:
                chunk = self.mic.read(timeout=0.5)
            except queue.Empty:
                continue
            score = self.wake.predict(chunk).get(WAKE_MODEL, 0.0)
            if score >= threshold:
                self._run_conversation(f"score {score:.2f}")

    def _run_conversation(self, why):
        log.info("Wake up (%s)", why)
        try:
            self.conversation()
        except Exception as e:
            log.exception("Conversation error: %s", e)
            self.speak("Something went wrong. I'll wait for you.")
        self.end_requested.clear()
        self.wake.reset()
        self.mic.flush()
        self.ui("sleep_and_hide")
        log.info("Waiting for 'Hey Jarvis'...")


def main():
    signal.signal(signal.SIGTERM, lambda *_: os._exit(0))
    signal.signal(signal.SIGINT, lambda *_: os._exit(0))
    _lock = single_instance()  # noqa: F841 (keep the lock open)
    assistant = Assistant()
    assistant.window = JarvisWindow(assistant)
    if CFG["ui"]["show_on_start"]:
        assistant.window.show()
    else:
        assistant.window.hide()
    threading.Thread(target=assistant.run, daemon=True).start()
    Gtk.main()


if __name__ == "__main__":
    main()
