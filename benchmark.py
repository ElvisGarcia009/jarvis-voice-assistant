#!/usr/bin/env python3
"""
Measures how much CPU, RAM, GPU memory (VRAM) and Claude tokens Jarvis uses.

  python3 benchmark.py monitor [SECONDS]
      Watches the running Jarvis service (everything it starts counts too:
      Whisper, Claude Code and the commands Claude runs) and prints one line per
      second, then a summary per activity: sleeping, listening, speaking,
      Claude working... Talk to Jarvis while it runs. Ctrl+C stops it early.

  ~/.local/share/jarvis/venv/bin/python benchmark.py components [--claude]
      Measures each piece on its own: the Kokoro voice, the Whisper models
      (gaming mode on the CPU and the normal one) and, with --claude, one real
      Claude request that runs a terminal command (uses a little of your plan).

  python3 benchmark.py tokens [--since YYYY-MM-DD]
      Tokens and cost of every question you asked Jarvis, read from Claude
      Code's own conversation history (~/.claude/projects). Free: no requests.

  ~/.local/share/jarvis/venv/bin/python benchmark.py tokens --live [--model sonnet]
      Asks Claude three sample questions the way Jarvis does (a chat answer, one
      shell command, a few commands) in one fresh conversation and reports each
      one's tokens and cost. Uses a little of your plan.

Cost is what the tokens would cost at Anthropic's API prices. With a Claude
subscription you pay the plan instead; the tokens count toward its usage limits.

RAM is PSS (shared libraries split between the processes that use them), the
fairest "how much does this cost" number. CPU % is of the whole processor.
"""
import glob
import json
import os
import statistics
import subprocess
import sys
import threading
import time

TICK = os.sysconf("SC_CLK_TCK")
NCPU = os.cpu_count() or 1


# ---------------------------------------------------------------- process info
def proc_name(pid):
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            args = f.read().split(b"\0")
    except OSError:
        return "?"
    text = b" ".join(args).decode(errors="replace")
    if "jarvis_stt.py" in text:
        return "whisper"
    if "jarvis.py" in text:
        return "jarvis"
    base = os.path.basename(args[0].decode(errors="replace")) if args and args[0] else "?"
    # Claude Code is a node/bun program: its real name shows up in the arguments
    return "claude" if "claude" in text and base in ("node", "bun", "claude") else base


def pss_mb(pid):
    try:
        with open(f"/proc/{pid}/smaps_rollup") as f:
            for line in f:
                if line.startswith("Pss:"):
                    return int(line.split()[1]) / 1024
    except OSError:
        pass
    return 0.0


def cpu_seconds(pid):
    try:
        with open(f"/proc/{pid}/stat") as f:
            fields = f.read().rsplit(")", 1)[1].split()
        return (int(fields[11]) + int(fields[12])) / TICK   # utime + stime
    except (OSError, IndexError, ValueError):
        return 0.0


def descendants(root):
    """root and all its children, grandchildren..."""
    children = {}
    for entry in os.listdir("/proc"):
        if entry.isdigit():
            try:
                with open(f"/proc/{entry}/stat") as f:
                    ppid = int(f.read().rsplit(")", 1)[1].split()[1])
                children.setdefault(ppid, []).append(int(entry))
            except (OSError, IndexError, ValueError):
                pass
    found, todo = [], [root]
    while todo:
        pid = todo.pop()
        found.append(pid)
        todo.extend(children.get(pid, []))
    return found


def vram_by_pid():
    """{pid: MiB} from nvidia-smi ({} without an NVIDIA GPU)."""
    try:
        out = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,used_memory",
                              "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.TimeoutExpired):
        return {}
    usage = {}
    for line in out.splitlines():
        try:
            pid, mib = line.split(",")
            usage[int(pid)] = usage.get(int(pid), 0) + float(mib)
        except ValueError:
            pass
    return usage


class Sampler:
    """Samples a set of processes in the background: peak RAM and VRAM, CPU time."""

    def __init__(self, pids_fn, every=0.25):
        self.pids_fn, self.every = pids_fn, every
        self.peak_ram = self.peak_vram = 0.0
        self.cpu = {}
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._loop, daemon=True)

    def _loop(self):
        n = 0
        while not self.stop_event.is_set():
            pids = self.pids_fn()
            self.peak_ram = max(self.peak_ram, sum(pss_mb(p) for p in pids))
            for p in pids:
                self.cpu[p] = cpu_seconds(p)
            if n % 4 == 0:   # nvidia-smi is slow: once a second
                vram = vram_by_pid()
                self.peak_vram = max(self.peak_vram, sum(vram.get(p, 0) for p in pids))
            n += 1
            self.stop_event.wait(self.every)

    def __enter__(self):
        self.start_cpu = {p: cpu_seconds(p) for p in self.pids_fn()}
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop_event.set()
        self.thread.join()

    def cpu_used(self):
        return sum(v - self.start_cpu.get(p, 0.0) for p, v in self.cpu.items())


# ---------------------------------------------------------------- monitor
def service_cgroup():
    path = subprocess.run(["systemctl", "--user", "show", "-p", "ControlGroup", "--value",
                           "jarvis"], capture_output=True, text=True).stdout.strip()
    if not path:
        sys.exit("The jarvis service is not running (systemctl --user start jarvis).")
    return "/sys/fs/cgroup" + path


def cgroup_cpu_usec(cg):
    with open(f"{cg}/cpu.stat") as f:
        for line in f:
            if line.startswith("usage_usec"):
                return int(line.split()[1])
    return 0


def activity(names):
    if "claude" in names:
        return "Claude working"
    if "pw-play" in names:
        return "speaking"
    if "whisper" in names:
        return "awake (Whisper loaded)"
    return "sleeping"


def monitor(seconds):
    cg = service_cgroup()
    print(f"Watching Jarvis for {seconds}s (Ctrl+C to stop). CPU % = share of all {NCPU} threads.")
    print(f"{'time':8} {'activity':24} {'CPU %':>6} {'RAM MB':>7} {'VRAM MB':>8}  processes")
    stats = {}
    last_cpu, last_t = cgroup_cpu_usec(cg), time.monotonic()
    end = last_t + seconds
    try:
        while time.monotonic() < end:
            time.sleep(1)
            cpu, now = cgroup_cpu_usec(cg), time.monotonic()
            cpu_pct = (cpu - last_cpu) / 1e6 / (now - last_t) / NCPU * 100
            last_cpu, last_t = cpu, now
            with open(f"{cg}/cgroup.procs") as f:
                pids = [int(p) for p in f.read().split()]
            names = [proc_name(p) for p in pids]
            ram = sum(pss_mb(p) for p in pids)
            vram_all = vram_by_pid()
            vram = sum(vram_all.get(p, 0) for p in pids)
            act = activity(names)
            counts = {n: names.count(n) for n in dict.fromkeys(names)}
            shown = " ".join(n if c == 1 else f"{n}×{c}" for n, c in counts.items())
            print(f"{time.strftime('%H:%M:%S'):8} {act:24} {cpu_pct:6.1f} {ram:7.0f} {vram:8.0f}  {shown}")
            s = stats.setdefault(act, {"n": 0, "cpu": 0.0, "cpu_max": 0.0, "ram": 0.0, "vram": 0.0})
            s["n"] += 1
            s["cpu"] += cpu_pct
            s["cpu_max"] = max(s["cpu_max"], cpu_pct)
            s["ram"] = max(s["ram"], ram)
            s["vram"] = max(s["vram"], vram)
    except KeyboardInterrupt:
        pass
    print("\nSummary per activity:")
    print(f"{'activity':24} {'seconds':>7} {'CPU avg %':>9} {'CPU max %':>9} {'RAM max MB':>10} {'VRAM max MB':>11}")
    for act, s in stats.items():
        print(f"{act:24} {s['n']:7d} {s['cpu'] / s['n']:9.1f} {s['cpu_max']:9.1f} "
              f"{s['ram']:10.0f} {s['vram']:11.0f}")


# ---------------------------------------------------------------- components
def components(with_claude):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import numpy as np
    import jarvis
    from kokoro_onnx import Kokoro

    me = os.getpid()
    v = jarvis.CFG["voice"]
    print("== Kokoro voice (runs inside the Jarvis process)")
    with Sampler(lambda: [me]) as s:
        t = time.monotonic()
        kokoro = Kokoro(jarvis.KOKORO_MODEL, jarvis.KOKORO_VOICES)
        load = time.monotonic() - t
    print(f"   load {load:.1f}s, process RAM after loading {pss_mb(me):.0f} MB")
    text = ("You have about ninety gigabytes free on your disk. That is roughly half of it, "
            "so there is plenty of room for a couple of new games.")
    voice = v["kokoro_voice"].split("+")[0]
    kokoro.create("Ready.", voice=voice, lang=v["kokoro_lang"])   # warm-up, like Jarvis
    with Sampler(lambda: [me]) as s:
        t = time.monotonic()
        audio, rate = kokoro.create(text, voice=voice, speed=float(v["kokoro_speed"]),
                                    lang=v["kokoro_lang"])
        took = time.monotonic() - t
    seconds = len(audio) / rate
    print(f"   {seconds:.1f}s of speech made in {took:.2f}s ({seconds / took:.1f}× faster than "
          f"real time), CPU {s.cpu_used():.1f} s = {s.cpu_used() / took / NCPU * 100:.0f}% of the "
          f"processor while it works")

    clip = np.interp(np.arange(0, len(audio), rate / 16000), np.arange(len(audio)), audio)
    clip = (clip / max(1e-6, float(np.abs(clip).max())) * 0.5).astype(np.float32)
    sc = jarvis.CFG["stt"]
    specs = [(sc["gaming_model"], "cpu", "int8", "gaming mode (CPU)"),
             (sc["local_model"], sc["device"], sc["compute_type"], "normal")]
    for model, device, compute, label in specs:
        print(f"== Whisper {model} on {device} — {label}")
        stt = jarvis.LocalSTT()
        stt.wanted = lambda spec=(model, device, compute): spec
        with Sampler(lambda: [p.pid] if (p := stt.proc) else []) as s:
            t = time.monotonic()
            stt.load()
            stt.ready.wait(180)
            load = time.monotonic() - t
            if stt.error:
                print(f"   unavailable: {stt.error}")
                stt.unload()
                continue
            times = []
            for _ in range(3):
                t = time.monotonic()
                heard = stt.transcribe(clip, "en")
                times.append(time.monotonic() - t)
        print(f"   load {load:.1f}s, transcribe {seconds:.0f}s of speech in {times[0]:.2f}s "
              f"(then {min(times[1:]):.2f}s), RAM {s.peak_ram:.0f} MB, VRAM {s.peak_vram:.0f} MB")
        print(f"   heard: {heard.strip()[:90]}")
        stt.unload()

    if with_claude:
        print(f"== Claude request with a terminal command (model {jarvis.CFG['claude']['model']})")
        jarvis.CFG["memory"]["enabled"] = False   # do not touch Jarvis' real memory
        a = jarvis.Assistant.__new__(jarvis.Assistant)
        a.session, a.memory = None, {}
        a.end_requested = threading.Event()
        a.system_prompt = jarvis.build_system_prompt()
        marks = {}
        t0 = time.monotonic()

        def on_event(kind, _value):
            marks.setdefault(kind, time.monotonic() - t0)

        with Sampler(lambda: [p for p in descendants(me) if p != me]) as s:
            data, status, _ = a._run_claude_stream(
                "Count the files in my Downloads folder with one shell command and tell me "
                "the number in one short sentence.", jarvis.CFG["claude"]["model"], None,
                a.system_prompt, on_event)
            total = time.monotonic() - t0
        answer = (data or {}).get("result", status)
        print(f"   first words after {marks.get('text', 0):.1f}s, tool used after "
              f"{marks.get('tool', 0):.1f}s, finished after {total:.1f}s")
        print(f"   Claude Code + its commands: RAM {s.peak_ram:.0f} MB, CPU {s.cpu_used():.1f} s "
              f"(about {s.cpu_used() / total / NCPU * 100:.1f}% of the processor on average)")
        print(f"   answer: {answer[:100]}")


# ---------------------------------------------------------------- tokens
# USD per million tokens (Anthropic API, prompts up to 100k tokens). Claude Code
# writes its cache with a 1-hour lifetime (2x input price); reads are cheap.
PRICES = {   # model: (input, output, cache write 5 min, cache write 1 h, cache read)
    "haiku-5-5": (0.10, 0.50, 0.125, 0.20, 0.01),
    "sonnet-5-5": (2.00, 10.00, 2.50, 4.00, 0.10),
    "opus-5-5": (4.00, 20.00, 5.00, 8.00, 0.20),
}
JARVIS_MARK = "Your name is Jarvis"   # from build_system_prompt(), stored in the history


def price_of(model):
    return next((p for key, p in PRICES.items() if key in (model or "")), None)


def call_cost(model, usage):
    p = price_of(model)
    if not p:
        return None
    cw = usage.get("cache_creation") or {}
    w5, w1 = cw.get("ephemeral_5m_input_tokens"), cw.get("ephemeral_1h_input_tokens")
    if w5 is None and w1 is None:
        w5, w1 = 0, usage.get("cache_creation_input_tokens", 0)
    return (usage.get("input_tokens", 0) * p[0] + usage.get("output_tokens", 0) * p[1]
            + (w5 or 0) * p[2] + (w1 or 0) * p[3]
            + usage.get("cache_read_input_tokens", 0) * p[4]) / 1e6


def jarvis_questions(since=""):
    """Every question asked through Jarvis, with the usage of all its API calls."""
    folder = os.path.expanduser("~/.claude/projects/" + os.path.expanduser("~").replace("/", "-"))
    questions = []
    for path in glob.glob(os.path.join(folder, "*.jsonl")):
        with open(path, errors="replace") as f:
            text = f.read()
        if JARVIS_MARK not in text:
            continue
        current, seen = None, set()
        for line in text.splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("type") == "user" and e.get("promptSource") == "sdk" \
                    and isinstance((e.get("message") or {}).get("content"), str):
                q = e["message"]["content"]
                current = {"q": q, "time": e.get("timestamp", ""), "calls": 0, "new": 0,
                           "write": 0, "read": 0, "out": 0, "cost": 0.0, "model": "",
                           "summary": q.startswith("Write private notes")}
                questions.append(current)
            elif e.get("type") == "assistant" and current and not e.get("isSidechain"):
                m = e.get("message") or {}
                if m.get("id") in seen:
                    continue   # one API reply is stored once per content block
                seen.add(m.get("id"))
                u = m.get("usage") or {}
                current["calls"] += 1
                current["model"] = m.get("model", "")
                current["new"] += u.get("input_tokens", 0)
                current["write"] += u.get("cache_creation_input_tokens", 0)
                current["read"] += u.get("cache_read_input_tokens", 0)
                current["out"] += u.get("output_tokens", 0)
                current["cost"] += call_cost(current["model"], u) or 0.0
    return [q for q in questions if q["calls"] and not q["summary"] and q["time"] >= since]


def token_table(rows):
    if not rows:
        print("   (nothing yet)")
        return
    for q in rows:
        q["total"] = q["new"] + q["write"] + q["read"] + q["out"]
    print(f"   {'':24} {'median':>9} {'average':>9} {'max':>10}")
    for label, key in (("total tokens", "total"), ("  read from cache (cheap)", "read"),
                       ("  written to cache", "write"), ("  Claude's answer (output)", "out"),
                       ("API calls", "calls")):
        vals = [q[key] for q in rows]
        print(f"   {label:24} {statistics.median(vals):>9,.0f} {statistics.mean(vals):>9,.0f} "
              f"{max(vals):>10,}")
    costs = [q["cost"] for q in rows]
    print(f"   {'cost (USD, API prices)':24} {statistics.median(costs):>9.4f} "
          f"{statistics.mean(costs):>9.4f} {max(costs):>10.4f}")


def tokens_history(since):
    rows = jarvis_questions(since)
    if not rows:
        print("No Jarvis questions found in Claude Code's history" + (f" since {since}." if since else "."))
        return
    first, last = min(q["time"] for q in rows), max(q["time"] for q in rows)
    print(f"{len(rows)} questions asked through Jarvis, {first[:10]} to {last[:10]} "
          f"(Claude Code's conversation history)\n")
    for model in sorted({q["model"] for q in rows}):
        group = [q for q in rows if q["model"] == model]
        for label, part in (("answered without tools", [q for q in group if q["calls"] == 1]),
                            ("ran commands / used tools", [q for q in group if q["calls"] > 1])):
            if part:
                print(f"== {model}: {label} ({len(part)} questions)")
                token_table(part)
    total = sum(q["cost"] for q in rows)
    print(f"\nAll {len(rows)} questions together: ${total:.2f} at API prices "
          f"(${total / len(rows):.4f} per question on average).")


def tokens_live(model=None):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import jarvis
    model = model or jarvis.CFG["claude"]["model"]
    print(f"Asking Claude ({model}) three questions the way Jarvis does, in one fresh conversation...\n")
    jarvis.CFG["memory"]["enabled"] = False   # do not touch Jarvis' real memory
    a = jarvis.Assistant.__new__(jarvis.Assistant)
    a.session, a.memory = None, {}
    a.end_requested = threading.Event()
    a.system_prompt = jarvis.build_system_prompt()
    samples = [("chat answer", "In one sentence, what is a good name for a pet turtle?"),
               ("one command", "How much free disk space do I have?"),
               ("a few commands", "Which three folders in my home use the most space, and how "
                                  "many files are in my Downloads folder?")]
    print(f"{'question':16} {'tokens':>8} {'cache read':>10} {'output':>7} {'turns':>5} "
          f"{'seconds':>7} {'cost USD':>9}")
    total = 0.0
    for label, question in samples:
        t = time.monotonic()
        data, status, _ = a._run_claude_stream(question, model, a.session,
                                               a.system_prompt, lambda *_: None)
        took = time.monotonic() - t
        if not data:
            print(f"{label:16} failed ({status})")
            continue
        a.session = data.get("session_id") or a.session
        u = data.get("usage") or {}
        tokens = sum(int(u.get(k) or 0) for k in ("input_tokens", "cache_creation_input_tokens",
                                                   "cache_read_input_tokens", "output_tokens"))
        cost = float(data.get("total_cost_usd") or 0)
        total += cost
        print(f"{label:16} {tokens:>8,} {int(u.get('cache_read_input_tokens') or 0):>10,} "
              f"{int(u.get('output_tokens') or 0):>7,} {int(data.get('num_turns') or 0):>5} "
              f"{took:>7.1f} {cost:>9.4f}")
    print(f"\nTotal: ${total:.4f} (Claude Code's own cost estimate, API prices). "
          f"The first question pays to fill the cache; later ones mostly read it.")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["monitor"]:
        monitor(int(args[1]) if len(args) > 1 else 60)
    elif args[:1] == ["components"]:
        components("--claude" in args)
    elif args[:1] == ["tokens"]:
        if "--live" in args:
            tokens_live(args[args.index("--model") + 1] if "--model" in args else None)
        else:
            tokens_history(args[args.index("--since") + 1] if "--since" in args else "")
    else:
        print(__doc__)
