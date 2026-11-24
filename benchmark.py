#!/usr/bin/env python3
"""
Measures how much CPU, RAM and GPU memory (VRAM) Jarvis uses.

  python3 benchmark.py monitor [SECONDS]
      Watches the running Jarvis service (everything it starts counts too:
      Whisper, Claude Code and the commands Claude runs) and prints one line per
      second, then a summary per activity: sleeping, listening, speaking,
      Claude working... Talk to Jarvis while it runs. Ctrl+C stops it early.

  ~/.local/share/jarvis/venv/bin/python benchmark.py components [--claude]
      Measures each piece on its own: the Kokoro voice, the Whisper models
      (gaming mode on the CPU and the normal one) and, with --claude, one real
      Claude request that runs a terminal command (uses a little of your plan).

RAM is PSS (shared libraries split between the processes that use them), the
fairest "how much does this cost" number. CPU % is of the whole processor.
"""
import json
import os
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


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["monitor"]:
        monitor(int(args[1]) if len(args) > 1 else 60)
    elif args[:1] == ["components"]:
        components("--claude" in args)
    else:
        print(__doc__)
