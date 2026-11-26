# Jarvis — diagramas de arquitectura (Mermaid)

Diagramas del video en formato Mermaid, verificados contra el código (`jarvis.py`, `jarvis_stt.py`, `jarvis_ui.py`, `install.sh`, `jarvis.service`). GitHub los dibuja directamente.

## 1. Componentes

```mermaid
flowchart LR
    U([Usuario]) -- voz --> REC[pw-record<br/>16 kHz mono]
    subgraph CORE["jarvis.py · proceso principal (systemd --user)"]
        ORCH[Assistant<br/>orquestador]
        WAKE[openWakeWord<br/>hey_jarvis]
        VAD[Silero VAD ×2]
        TTS[Kokoro TTS]
        UI[Burbuja GTK]
        ACT[ActivityConsole]
        MW[MediaWatch]
    end
    REC -- bloques de 80 ms --> ORCH
    ORCH <--> WAKE
    ORCH <--> VAD
    MW -. playerctl cada 1,5 s .-> WAKE
    ORCH -- "audio por stdin (JSON + float32)" --> STT[jarvis_stt.py<br/>faster-whisper]
    ORCH -. "WAV por HTTPS (alternativa / respaldo)" .-> GROQ{{Groq Whisper API}}
    ORCH -- "claude -p … (un proceso por petición)" --> CC[claude CLI]
    CC --> API{{API de Anthropic}}
    CC --> BASH[[Bash · archivos · web]]
    CC -- stream-json --> ORCH
    ORCH -- oraciones --> TTS -- PCM f32 --> PLAY[pw-play] -- voz --> U
    ORCH -. respaldo .-> EDGE{{Edge TTS}}
    ORCH -- GLib.idle_add --> UI
    ACT -- activity.log --> TERM[Terminal<br/>tail -F]
    ORCH --- MEM[(memory.json)]
    CC --- TR[(~/.claude/projects)]
```

## 2. Estados del sistema

```mermaid
stateDiagram-v2
    [*] --> Dormido
    Dormido --> Saludo: "Hey Jarvis" (patience 2) o SIGUSR1 / clic
    Saludo --> Escuchando
    Escuchando --> Transcribiendo: 2 s de silencio
    Escuchando --> Cierre: 10 s sin voz / ✕
    Transcribiendo --> Escuchando: frase inacabada (espera 4 s)
    Transcribiendo --> Escuchando: interruptor de terminal (local)
    Transcribiendo --> Cierre: despedida (local)
    Transcribiendo --> ClaudeTrabaja: texto
    ClaudeTrabaja --> Hablando: primera oración
    Hablando --> Escuchando: fin o interrupción por voz
    ClaudeTrabaja --> Cierre: ✕ (mata el grupo de procesos)
    Cierre --> Dormido: limpieza · descarga de Whisper en 60 s · compactación si > 60k tokens
```

## 3. Estados de la burbuja (`jarvis_ui.py`)

```mermaid
stateDiagram-v2
    sleeping: Dormido (oculta)
    listening: Escuchando
    thinking: Pensando
    speaking: Hablando
    [*] --> sleeping
    sleeping --> listening: set_state("listening")
    listening --> thinking: transcribir
    thinking --> speaking: primer fragmento con audio
    speaking --> listening: fin del turno o interrupción
    listening --> sleeping: sleep_and_hide()
    speaking --> sleeping: sleep_and_hide()
    note right of speaking: No existe un estado "Interrumpido"
```

## 4. Arranque del servicio

```mermaid
sequenceDiagram
    participant SD as systemd --user
    participant M as main()
    participant A as Assistant()
    participant R as pw-record
    participant G as GTK
    participant T as hilo run()
    SD->>M: graphical-session.target → ExecStart (venv/python -u)
    M->>M: logging · flock jarvis.lock
    M->>A: crear (TOML sobre DEFAULTS)
    A->>A: openWakeWord + 2 × Silero VAD
    A-->>R: Popen + hilo lector (cola de 500)
    A->>A: Kokoro: carga + "Ready."
    M->>M: SIGUSR1 → despertar manual
    M->>G: Burbuja (oculta)
    M-->>T: hilo run() (daemon)
    M->>G: Gtk.main()
    T->>T: bloque → openWakeWord cada 80 ms
```

## 5. Una petición a Claude Code

```mermaid
sequenceDiagram
    participant C as Hilo de conversación
    participant W as Hilo worker
    participant CC as claude -p
    participant API as API Anthropic
    participant SH as Bash
    C->>W: ask_and_speak()
    W->>CC: Popen(start_new_session, stdin=DEVNULL)
    CC-->>W: system/init (session_id)
    CC->>API: petición
    CC-->>W: text_delta… → SentenceStream → cola de oraciones
    CC-->>W: content_block_start tool_use → "One moment…" (si no se dijo nada)
    CC->>SH: comando
    SH-->>CC: salida
    CC-->>W: assistant/user tool_use + tool_result → ActivityConsole
    CC-->>W: result (session_id, usage, total_cost_usd)
    W->>C: None en la cola · memory.json · "Claude usage: …"
    Note over C,CC: ✕ → SIGTERM al grupo, 3 s, SIGKILL, wait (sin zombis)
```

## 6. Ciclo de vida de Whisper local

```mermaid
sequenceDiagram
    participant C as Conversación
    participant L as LocalSTT
    participant P as jarvis_stt.py
    participant G as GPU
    C->>L: despertar → load()
    L->>P: Popen(modelo, dispositivo, cómputo)
    P->>G: precarga cuBLAS/cuDNN · int8_float16 · calentamiento
    P-->>L: {"ready": true} (hilo de espera → Event)
    C->>L: transcribe(audio)
    L->>P: JSON {"samples": N} + float32
    P-->>L: {"text": "…"} (select con 60 s)
    C->>L: fin → unload_later(60)
    L->>P: cerrar stdin
    P-->>G: el proceso termina → VRAM = 0
```

## 7. Interrupción por voz (barge-in)

```mermaid
sequenceDiagram
    participant U as Usuario
    participant B as Monitor de interrupción
    participant S as pw-play
    participant W as Worker de Claude
    participant C as Conversación
    B->>B: ignora 0,3 s
    U->>B: voz (VAD > 0,5 durante ≥ 0,3 s)
    B->>B: guarda ≈ 0,8 s previos
    B->>S: speak_cancel + kill
    W->>W: sigue hasta terminar (no se cancela)
    C->>C: estado "escuchando"; la cola del mic sigue llenándose
    C->>C: listen(prefill) sin vaciar la cola
```

## 8. Memoria entre conversaciones

```mermaid
flowchart LR
    A[Activación] --> R{memory.json<br/>last_used < 12 h?}
    R -- sí --> RES[claude --resume session_id]
    R -- no / sin id --> NEW[sesión nueva<br/>prompt + resumen]
    RES --> TURN[turnos] --> SAVE[(memory.json<br/>context_tokens, atómico, 600)]
    NEW --> TURN
    SAVE --> END{fin de conversación<br/>context_tokens > 60 000?}
    END -- sí --> SUM[resumen con summary_model<br/>no streaming, ≤ 10 líneas]
    SUM --> CLR[(summary nuevo<br/>session_id = null)]
    END -- no --> SLEEP[dormir]
    CLR --> SLEEP
```
