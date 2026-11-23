#!/usr/bin/env python3
"""
Local speech-recognition worker for Jarvis (faster-whisper).

Jarvis starts this as a child process when it wakes up and stops it a while
after the conversation ends. Ending the process is the only way to give back
*all* the GPU memory, including the CUDA context, so while Jarvis waits for
"Hey Jarvis" it uses no VRAM at all.

Usage: jarvis_stt.py MODEL DEVICE COMPUTE_TYPE   (device/compute may be "auto")

Protocol on stdin/stdout:
  -> one JSON line when loaded: {"ready": true, ...} or {"error": "..."}
  <- request: a JSON line {"samples": N, "language": "en" | null},
     followed by N float32 samples (16 kHz mono)
  -> reply: a JSON line {"text": "..."} or {"error": "..."}
The worker exits when stdin closes (Jarvis stopped it or Jarvis itself ended).
"""

import ctypes
import glob
import importlib.util
import json
import os
import sys
import time

import numpy as np

RATE = 16000


def preload_cuda_libs():
    """faster-whisper needs cuBLAS and cuDNN. When they come from the pip
    packages nvidia-cublas-cu12 / nvidia-cudnn-cu12, load them by hand."""
    spec = importlib.util.find_spec("nvidia")
    if not spec or not spec.submodule_search_locations:
        return
    base = list(spec.submodule_search_locations)[0]
    for pattern in ("cublas/lib/libcublasLt.so.*", "cublas/lib/libcublas.so.*",
                    "cudnn/lib/libcudnn*.so.*"):
        for lib in sorted(glob.glob(os.path.join(base, pattern))):
            try:
                ctypes.CDLL(lib, mode=ctypes.RTLD_GLOBAL)
            except OSError:
                pass


def read_exact(stream, size):
    data = bytearray()
    while len(data) < size:
        chunk = stream.read(size - len(data))
        if not chunk:
            raise EOFError
        data += chunk
    return bytes(data)


def main():
    model_name, device, compute = sys.argv[1:4]
    # Keep stdout for the protocol only: anything a library prints goes to stderr (the log)
    out = os.fdopen(os.dup(1), "w", buffering=1)
    os.dup2(2, 1)
    inp = sys.stdin.buffer

    def send(msg):
        out.write(json.dumps(msg) + "\n")

    try:
        started = time.monotonic()
        if device != "cpu":
            preload_cuda_libs()
        import ctranslate2
        from faster_whisper import WhisperModel
        if device == "auto":
            device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
        if compute == "auto":
            # int8 weights: half the VRAM of float16, same accuracy and speed
            compute = "int8_float16" if device == "cuda" else "int8"
        model = WhisperModel(model_name, device=device, compute_type=compute)
        model.transcribe(np.zeros(RATE, np.float32))   # warm up
    except Exception as e:
        send({"error": f"{type(e).__name__}: {e}"})
        return
    send({"ready": True, "model": model_name, "device": device, "compute": compute,
          "seconds": round(time.monotonic() - started, 2)})

    while True:
        try:
            line = inp.readline()
            if not line:
                return
            request = json.loads(line)
            audio = np.frombuffer(read_exact(inp, 4 * int(request["samples"])), np.float32)
        except (EOFError, ValueError, KeyError):
            return
        try:
            segments, _info = model.transcribe(
                audio, beam_size=1, language=request.get("language") or None,
                condition_on_previous_text=False)
            send({"text": " ".join(s.text.strip() for s in segments).strip()})
        except Exception as e:
            send({"error": f"{type(e).__name__}: {e}"})


if __name__ == "__main__":
    main()
