# Video de arquitectura de Jarvis

Video técnico narrado en español (~31 min) que recorre la arquitectura, los flujos y las decisiones de ingeniería de Jarvis, pensado para un desarrollador backend.

| Archivo | Contenido |
|---|---|
| [`storyboard.md`](storyboard.md) | Storyboard completo: capítulos, escenas, componentes, acciones visuales y narración, con marcas de tiempo. Se genera desde `video/scenes*.py`, así que coincide con el video. |
| [`diagrams.md`](diagrams.md) | Los diagramas principales en Mermaid (componentes, estados, secuencias, memoria). |
| `video/engine.py` | Motor de animación (Cairo + Pango): nodos, flechas con datos en movimiento, diagramas de secuencia, tablas, gráficas, carriles de concurrencia, orbes. |
| `video/scenes.py`, `video/scenes2.py` | Las 55 escenas: diagramas y narración. |
| `video/build.py` | Narración con Kokoro (voz `em_alex`), sincronización, render en paralelo, ffmpeg, subtítulos `.srt`. |

El video y los subtítulos se guardan fuera del repositorio, en `~/Videos/Jarvis/` (`jarvis-arquitectura.mp4` y `.srt`). Los archivos intermedios quedan en `build/`, que git ignora.

## Volver a generarlo

```bash
cd docs/architecture-video
~/.local/share/jarvis/venv/bin/python video/build.py                 # todo (≈ 6 min de render en 12 hilos + voz la primera vez)
~/.local/share/jarvis/venv/bin/python video/build.py --storyboard    # solo storyboard.md
~/.local/share/jarvis/venv/bin/python video/build.py --frames --only 5,23   # PNG de muestra
```

Necesita el entorno de Jarvis (Kokoro, numpy, PyGObject con Pango) y `ffmpeg`. La narración se guarda en caché por texto: cambiar una frase solo vuelve a sintetizar esa frase.

## Cómo se verificó

Cada flujo se contrastó con el código fuente, no solo con el README. El video distingue:

- **Implementado y probado en el equipo de desarrollo** (Pop!_OS 24.04, COSMIC, RTX 4060): activación con patience y umbral de medios, Silero VAD, Whisper local en proceso hijo con liberación de VRAM, modo juego, streaming de Claude Code, terminal de actividad (cosmic-term), interruptor de terminal por voz, cancelación con ✕, compactación de memoria, Kokoro.
- **Configurable**: umbrales, tiempos de escucha, modelo de Claude, herramientas (`[claude] tools`), extensiones, idiomas, voces, modo de interrupción.
- **Opcional**: Groq, Edge TTS, gtk-layer-shell, playerctl.
- **Implementado pero no verificado recientemente**: transcripción con Groq, respaldo con Edge TTS, terminales distintas de COSMIC (`gnome-terminal --wait`, konsole…), instrucciones de instalación para Fedora y Arch, modo de interrupción `wakeword`.
- **Planificado, no implementado**: verificador de voz del usuario para la palabra de activación.

Las cifras (CPU, RAM, VRAM, tokens, latencias) vienen de `benchmark.py` y de los registros reales de `jarvis.log`.
