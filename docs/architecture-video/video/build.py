#!/usr/bin/env python3
"""
Builds the Jarvis architecture video.

  ~/.local/share/jarvis/venv/bin/python build.py [--only N] [--frames] [--storyboard]

Steps: narration audio per beat (Kokoro, Spanish voice, cached) -> timing ->
frames (Cairo, one process per scene) -> ffmpeg segments -> final MP4 with the
narration track and Spanish subtitles (.srt next to it). --storyboard only writes
storyboard.md from the scene definitions. --frames N writes preview PNGs.
"""
import hashlib
import json
import os
import subprocess
import sys
import wave
import multiprocessing

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import engine  # noqa: E402
import scenes  # noqa: E402

BUILD = os.path.join(HERE, "..", "build")
OUT_DIR = os.path.expanduser("~/Videos/Jarvis")
OUT = os.path.join(OUT_DIR, "jarvis-arquitectura.mp4")
VOICE, SPEED, LANG = "em_alex", 0.97, "es"
RATE = 24000
LEAD = 0.25        # silence before each beat's narration


def tts_path(text):
    h = hashlib.sha1(f"{VOICE}|{SPEED}|{engine.spoken(text)}".encode()).hexdigest()[:16]
    return os.path.join(BUILD, "tts", h + ".wav")


def synthesize(all_scenes):
    os.makedirs(os.path.join(BUILD, "tts"), exist_ok=True)
    todo = [b["say"] for s in all_scenes for b in s.beats
            if b["say"] and not os.path.exists(tts_path(b["say"]))]
    if not todo:
        return
    from kokoro_onnx import Kokoro
    d = os.path.expanduser("~/.local/share/jarvis/models")
    k = Kokoro(f"{d}/kokoro-v1.0.int8.onnx", f"{d}/voices-v1.0.bin")
    for i, text in enumerate(todo, 1):
        audio, sr = k.create(engine.spoken(text), voice=VOICE, speed=SPEED, lang=LANG)
        pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
        with wave.open(tts_path(text), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(pcm.tobytes())
        print(f"  voice {i}/{len(todo)}", flush=True)


def wav_seconds(path):
    with wave.open(path) as w:
        return w.getnframes() / w.getframerate()


def timed_scenes():
    """All scenes with beat timing from the narration audio."""
    all_scenes = scenes.build()
    synthesize(all_scenes)
    t = 0.0
    for s in all_scenes:
        durs = []
        for b in s.beats:
            speech = wav_seconds(tts_path(b["say"])) if b["say"] else 0.0
            durs.append(max(b["min_dur"], LEAD + speech + b["pause"]))
        s.schedule(durs)
        s.t0 = t
        t += s.duration
    return all_scenes, t


def toc_of(all_scenes):
    seen, toc = set(), []
    for s in all_scenes:
        if s.chapter not in seen:
            seen.add(s.chapter)
            toc.append((s.chapter, s.title, s.t0))
    return toc


def render_scene(args):
    idx, frames_only = args
    import cairo
    all_scenes, total = timed_scenes()
    s = all_scenes[idx]
    toc = toc_of(all_scenes)
    n = int(round(s.duration * engine.FPS))
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, engine.W, engine.H)
    cr = cairo.Context(surf)
    if frames_only:
        os.makedirs(os.path.join(BUILD, "frames"), exist_ok=True)
        for frac in (0.15, 0.55, 0.97):
            s.draw(cr, s.duration * frac, toc, total)
            surf.write_to_png(os.path.join(BUILD, "frames", f"s{idx:02d}_{int(frac * 100):02d}.png"))
        return idx
    seg = os.path.join(BUILD, "seg", f"{idx:03d}.mp4")
    os.makedirs(os.path.dirname(seg), exist_ok=True)
    ff = subprocess.Popen(
        ["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgra",
         "-s", f"{engine.W}x{engine.H}", "-r", str(engine.FPS), "-i", "-",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
         "-threads", "2", seg], stdin=subprocess.PIPE)
    for f in range(n):
        s.draw(cr, f / engine.FPS, toc, total)
        surf.flush()
        ff.stdin.write(surf.get_data())
    ff.stdin.close()
    ff.wait()
    return idx


def build_audio(all_scenes, total):
    out = np.zeros(int((total + 1) * RATE), np.int16)
    for s in all_scenes:
        for b in s.beats:
            if not b["say"]:
                continue
            with wave.open(tts_path(b["say"])) as w:
                pcm = np.frombuffer(w.readframes(w.getnframes()), np.int16)
            start = int((s.t0 + b["t"] + LEAD) * RATE)
            out[start:start + len(pcm)] = pcm[:len(out) - start]
    path = os.path.join(BUILD, "narration.wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(out[:int(total * RATE)].tobytes())
    return path


def stamp(sec):
    ms = int(round(sec * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def build_srt(all_scenes, path):
    lines, n = [], 1
    for s in all_scenes:
        for b in s.beats:
            if not b["say"]:
                continue
            start = s.t0 + b["t"] + LEAD
            speech = wav_seconds(tts_path(b["say"]))
            # split long narration into ~2-line chunks spread over the speech time
            words = b["say"].split()
            chunks, cur = [], []
            for wd in words:
                cur.append(wd)
                if len(" ".join(cur)) > 84 or (wd.endswith((".", "?", ":")) and len(" ".join(cur)) > 40):
                    chunks.append(" ".join(cur))
                    cur = []
            if cur:
                chunks.append(" ".join(cur))
            total_chars = sum(len(c) for c in chunks) or 1
            t = start
            for c in chunks:
                d = speech * len(c) / total_chars
                lines.append(f"{n}\n{stamp(t)} --> {stamp(t + d)}\n{c}\n")
                n += 1
                t += d
    with open(path, "w") as f:
        f.write("\n".join(lines))


def write_storyboard(all_scenes, total):
    md = ["# Jarvis — storyboard del video de arquitectura", "",
          "Generado automáticamente desde `video/scenes.py` (la misma fuente que dibuja el video), "
          "así que el storyboard y el video no pueden diferir.", "",
          f"Duración total: **{int(total // 60)} min {int(total % 60)} s** · {len(all_scenes)} escenas · "
          f"voz Kokoro `{VOICE}` (español).", "", "## Tabla de contenidos", ""]
    for ch, title, t0 in toc_of(all_scenes):
        md.append(f"- `{int(t0 // 60):02d}:{int(t0 % 60):02d}` — **{ch}** · {title}")
    md.append("")
    cur = None
    for i, s in enumerate(all_scenes):
        if s.chapter != cur:
            cur = s.chapter
            md += ["", f"## {s.chapter} · {s.title}", ""]
        md += [f"### Escena {i + 1}: {s.subtitle or s.title}  "
               f"(`{int(s.t0 // 60):02d}:{int(s.t0 % 60):02d}`, {s.duration:.0f} s)", ""]
        if getattr(s, "visual", ""):
            md += [f"**Visual:** {s.visual}", ""]
        kinds = {}
        for el in s.elements:
            if isinstance(el, engine.Node):
                kinds.setdefault(el.kind, []).append(el.title.replace("\n", " "))
        if kinds:
            md.append("**Componentes:** " + "; ".join(
                f"{engine.KINDS[k]['badge'] or 'actor'}: {', '.join(v)}" for k, v in kinds.items()))
            md.append("")
        for j, b in enumerate(s.beats, 1):
            acts = []
            if b["show"]:
                acts.append("muestra " + ", ".join(b["show"]))
            if b["flow"]:
                acts.append("flujo " + ", ".join(f if isinstance(f, str) else f"{f[0]} ({f[1]})"
                                                 for f in b["flow"]))
            if b["focus"]:
                acts.append("resalta " + ", ".join(b["focus"]))
            md.append(f"{j}. *[{'; '.join(acts) or 'sin cambios'}]* — {b['say']}")
        md.append("")
    path = os.path.join(HERE, "..", "storyboard.md")
    with open(path, "w") as f:
        f.write("\n".join(md) + "\n")
    return path


def main():
    args = sys.argv[1:]
    all_scenes, total = timed_scenes()
    print(f"{len(all_scenes)} scenes, {total / 60:.1f} min", flush=True)
    print("storyboard:", write_storyboard(all_scenes, total))
    if "--storyboard" in args:
        return
    only = [int(a) for a in args[args.index("--only") + 1].split(",")] if "--only" in args else None
    idxs = only or list(range(len(all_scenes)))
    frames = "--frames" in args
    # spawn, not fork: the parent already initialized Pango/fontconfig (node sizing),
    # and forking after that deadlocks the children
    with multiprocessing.get_context("spawn").Pool(min(10, os.cpu_count() or 4)) as pool:
        for i in pool.imap_unordered(render_scene, [(i, frames) for i in idxs]):
            print(f"  scene {i} done", flush=True)
    if frames or only:
        return
    lst = os.path.join(BUILD, "segments.txt")
    with open(lst, "w") as f:
        for i in range(len(all_scenes)):
            f.write(f"file 'seg/{i:03d}.mp4'\n")
    video = os.path.join(BUILD, "video.mp4")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst,
                    "-c", "copy", video], check=True, cwd=BUILD)
    audio = build_audio(all_scenes, total)
    os.makedirs(OUT_DIR, exist_ok=True)
    srt = OUT.replace(".mp4", ".srt")
    build_srt(all_scenes, srt)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", video, "-i", audio, "-i", srt,
                    "-map", "0:v", "-map", "1:a", "-map", "2:s", "-c:v", "copy",
                    "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "24000", "-c:a", "aac",
                    "-b:a", "160k", "-c:s", "mov_text", "-metadata:s:s:0", "language=spa",
                    "-metadata:s:a:0", "language=spa", "-shortest", OUT], check=True)
    print("video:", OUT)
    print("subtitles:", srt)


if __name__ == "__main__":
    main()
