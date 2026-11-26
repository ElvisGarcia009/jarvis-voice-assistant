"""
Scene definitions for the Jarvis architecture video (narration in Spanish).

Every fact here was checked against the source code (jarvis.py, jarvis_stt.py,
jarvis_ui.py, install.sh, jarvis.service, config.example.toml) in November 2026.
"""
from engine import (Scene, Node, Group, Edge, Panel, Code, Sequence, Table, Series, Lanes,
                    Bars, Orb, Terminal, Caption, BRASS, GLACIER, VIOLET, TEAL, ORANGE, ROSE,
                    RED, GREEN, TEXT, MUTED, hexrgb)

PANEL = (1300, 140, 560, 850)          # right-hand explanation panel
LEFT_W = 1240


def chapter_card(num, title, points, said):
    s = Scene(num, title, kind="card")
    s.legend = False
    s.add(Caption("num", f"{num:02d}" if isinstance(num, int) else str(num), (960, 300), size=110,
                  color=BRASS, anchor="tc", weight="Bold"))
    s.add(Caption("title", title, (960, 470), size=46, anchor="tc", weight="SemiBold",
                  width=1500, align="center"))
    y = 590
    for i, p in enumerate(points):
        s.add(Caption(f"p{i}", p, (960, y + i * 52), size=24, color=MUTED, anchor="tc", width=1400,
                      align="center"))
    s.beat(said, show=["num", "title"] + [f"p{i}" for i in range(len(points))], pause=0.6)
    return s


def build():
    S = []

    # ================================================================== INTRO
    s = Scene("Intro", "Jarvis Voice Assistant", kind="title")
    s.add(Caption("t", "Jarvis Voice Assistant", (960, 330), size=78, anchor="tc", weight="SemiBold"))
    s.add(Caption("st", "Arquitectura, flujos de ejecución y decisiones de ingeniería", (960, 450),
                  size=32, color=BRASS, anchor="tc"))
    s.add(Caption("src", "Revisión técnica basada en el código fuente: jarvis.py · jarvis_stt.py · "
                  "jarvis_ui.py · install.sh · jarvis.service · config.example.toml",
                  (960, 560), size=21, color=MUTED, anchor="tc", width=1400, align="center"))
    s.add(Orb("orb", "speaking", (960, 760), scale=1.5))
    s.beat("Bienvenidos a esta revisión técnica de Jarvis Voice Assistant, un asistente de voz para "
           "Linux que escucha una palabra de activación, entiende lo que le pides y delega la ejecución "
           "en Claude Code, que actúa directamente sobre el sistema operativo.",
           show=["t", "st", "orb"])
    s.beat("No vamos a leer código línea por línea. Vamos a recorrer la arquitectura como en una "
           "revisión de ingeniería: qué componentes existen, cómo se comunican, qué ocurre en paralelo, "
           "cómo se recupera de los fallos, y qué decisiones de diseño hay detrás. Todo lo que veremos "
           "fue contrastado con el código fuente, no solo con la documentación.", show=["src"])
    S.append(s)

    s = Scene("Intro", "Tabla de contenidos", subtitle="13 capítulos")
    chapters = ["Visión general de la arquitectura", "Inicio y ciclo de vida",
                "Activación y captura de audio", "Speech-to-Text", "Orquestación con Claude Code",
                "Ejecución de acciones y seguridad", "Text-to-Speech", "Interfaz y sincronización",
                "Interrupciones y concurrencia", "Conversaciones y memoria",
                "Funcionalidades adicionales", "Errores y recuperación",
                "Análisis arquitectónico"]
    for i, c in enumerate(chapters):
        col, row = i // 7, i % 7
        s.add(Caption(f"c{i}", f"{i + 1:02d}   {c}", (180 + col * 820, 190 + row * 100), size=30,
                      color=TEXT if i != 4 else hexrgb("#FFF3D6"), weight="Medium"))
    s.beat("Este es el recorrido. Empezamos con la vista general y el ciclo de vida del servicio. "
           "Después seguimos el camino de una petición: la activación, la transcripción, la "
           "orquestación con Claude Code, la ejecución de comandos y la voz de respuesta.",
           show=[f"c{i}" for i in range(7)])
    s.beat("Luego vemos la interfaz, la concurrencia y las interrupciones, la memoria entre "
           "conversaciones, las funciones adicionales, el manejo de errores, y cerramos con un análisis "
           "crítico de la arquitectura, sus compromisos y sus alternativas.",
           show=[f"c{i}" for i in range(7, 13)])
    S.append(s)

    s = Scene("Intro", "Código visual del video", subtitle="cómo leer los diagramas")
    kinds = [("local", "Jarvis (Python)", "código del proceso principal"),
             ("process", "Subproceso local", "pw-record, Whisper, claude"),
             ("model", "Modelo local", "redes neuronales en tu PC"),
             ("external", "Servicio externo", "Internet: Anthropic, Groq, Edge"),
             ("storage", "Persistencia", "archivos en disco"),
             ("exec", "Comandos / SO", "lo que se ejecuta en Linux"),
             ("audio", "Audio E/S", "micrófono y altavoz"),
             ("ui", "Interfaz", "la burbuja flotante")]
    for i, (k, t, sub) in enumerate(kinds):
        s.node(f"k{i}", t, sub, kind=k, at=(300 + (i % 4) * 440, 330 + (i // 4) * 250), w=360, h=110)
    s.node("a", "Origen", kind="local", at=(560, 820), w=220, h=70, badge="")
    s.node("b", "Destino", kind="process", at=(1360, 820), w=220, h=70, badge="")
    s.edge("ab", "a", "b", "datos", color=BRASS)
    s.beat("Antes de empezar, el código visual. Cada tipo de componente tiene siempre el mismo color "
           "y la misma forma. Dorado es código de Jarvis en Python. Beige, procesos hijos locales. Verde, "
           "modelos de inteligencia artificial que corren en tu propio equipo.",
           show=["k0", "k1", "k2"])
    s.beat("Violeta con borde punteado son servicios externos en Internet. Turquesa con forma de "
           "cilindro es persistencia en disco. Naranja, comandos que se ejecutan en el sistema "
           "operativo. Azul claro, entrada y salida de audio. Y rosa, la interfaz visual.",
           show=["k3", "k4", "k5", "k6", "k7"])
    s.beat("Las flechas indican la dirección del flujo de información, y los puntos luminosos que "
           "viajan por ellas representan datos en movimiento en ese preciso momento.",
           show=["a", "b", "ab"], flow=[("ab", "datos")])
    S.append(s)

    # ================================================================== 1 OVERVIEW
    S.append(chapter_card(1, "Visión general de la arquitectura",
                          ["Qué problema resuelve", "Componentes y responsabilidades",
                           "Dependencias externas"],
                          "Capítulo uno: visión general de la arquitectura."))

    s = Scene(1, "Visión general de la arquitectura", subtitle="el problema")
    steps = [("v", "Tu voz", "audio", "“Hey Jarvis… ¿cuánto espacio libre tengo?”"),
             ("t", "Texto", "model", "transcripción"),
             ("c", "Claude Code", "process", "decide y actúa"),
             ("o", "Linux", "exec", "comandos reales"),
             ("r", "Voz de respuesta", "audio", "“Tienes unos 79 gigas libres”")]
    for i, (id, t, k, sub) in enumerate(steps):
        s.node(id, t, sub, kind=k, at=(210 + i * 375, 330), w=300, h=120)
    for a, b in zip("vtco", "tcor"):
        s.edge(a + b, a, b, color=BRASS)
    s.add(Panel("why", "Qué resuelve Jarvis", [
        "Controlar el PC con lenguaje natural, sin teclado ni ventana de chat.",
        "Un agente que actúa (abre apps, revisa discos, instala software), no solo conversa.",
        "Privacidad: la activación y, opcionalmente, la transcripción ocurren en local.",
        "Coste contenido: la GPU queda libre en reposo y Claude solo recibe lo necesario."],
        (160, 520, 1600, 420), size=24))
    s.beat("¿Qué problema resuelve Jarvis? Convertir una frase hablada en acciones reales sobre el "
           "ordenador. El usuario dice Hey Jarvis, formula una petición, y recibe una respuesta hablada "
           "después de que el sistema haya hecho el trabajo.", show=["v", "t", "c", "o", "r", "vt",
           "tc", "co", "or"], flow=["vt", "tc", "co", "or"])
    s.beat("La idea clave es que Jarvis no implementa un agente propio. Es una capa de voz alrededor de "
           "Claude Code, que ya sabe ejecutar comandos, leer archivos y razonar sobre los resultados. "
           "Jarvis aporta todo lo que rodea a esa capacidad: oído, voz, interfaz, memoria y control "
           "del ciclo de vida.", show=["why", "why.0", "why.1"], focus=["c"])
    s.beat("Dos requisitos no funcionales marcan muchas decisiones: privacidad, porque nada sale del "
           "equipo antes de la palabra de activación, y consumo de recursos, porque la máquina se "
           "comparte con juegos que necesitan toda la memoria de la tarjeta gráfica.",
           show=["why.2", "why.3"])
    S.append(s)

    s = Scene(1, "Visión general de la arquitectura", subtitle="diagrama de componentes")
    s.visual = "Diagrama general: proceso jarvis.py con sus módulos internos, subprocesos y servicios."
    s.add(Group("core", "jarvis.py · proceso principal (servicio systemd de usuario)",
                (450, 150, 640, 800)))
    s.node("user", "Usuario", kind="actor", at=(110, 560), w=150, h=130)
    s.node("rec", "pw-record", "micrófono · 16 kHz mono", kind="audio", at=(300, 400), w=220, h=86)
    s.node("play", "pw-play", "altavoz · PCM float", kind="audio", at=(300, 740), w=220, h=86)
    s.node("wake", "openWakeWord", "“hey_jarvis” · ONNX", kind="model", at=(590, 270), w=230, h=86)
    s.node("vad", "Silero VAD", "¿hay voz humana?", kind="model", at=(890, 270), w=230, h=86)
    s.node("orch", "Assistant", "orquestador · máquina de conversación", kind="local",
           at=(740, 470), w=330, h=100, size=24)
    s.node("tts", "Kokoro TTS", "voz local · ONNX", kind="model", at=(590, 690), w=230, h=86)
    s.node("ui", "Burbuja GTK", "Cairo + Pango", kind="ui", at=(890, 690), w=230, h=86)
    s.node("act", "ActivityConsole", "registro de comandos", kind="local", at=(740, 870), w=270, h=76)
    s.node("stt", "jarvis_stt.py", "faster-whisper · GPU/CPU", kind="process", at=(1320, 230),
           w=260, h=86)
    s.node("groq", "Groq Whisper API", "respaldo / alternativa", kind="external", at=(1700, 230),
           w=280, h=86)
    s.node("cc", "claude -p", "Claude Code CLI", kind="process", at=(1320, 470), w=260, h=100,
           size=24)
    s.node("anth", "API de Anthropic", "modelo Claude", kind="external", at=(1700, 400), w=280, h=86)
    s.node("bash", "Bash · archivos · web", "herramientas", kind="exec", at=(1700, 580), w=280, h=90)
    s.node("edge", "Edge TTS", "voz de respaldo", kind="external", at=(1320, 700), w=240, h=80)
    s.node("term", "Terminal", "cosmic-term + tail -F", kind="process", at=(1320, 880), w=260, h=80)
    E = [("e1", "user", "rec", "voz", GLACIER, 0), ("e2", "rec", "orch", "bloques de 80 ms", GLACIER, 0),
         ("e3", "orch", "wake", "", BRASS, 0), ("e4", "orch", "vad", "", BRASS, 0),
         ("e5", "orch", "stt", "audio por stdin", BRASS, 0),
         ("e6", "orch", "groq", "WAV · HTTPS (alternativa)", VIOLET, -70),
         ("e7", "orch", "cc", "subproceso por petición", BRASS, 0),
         ("e8", "cc", "anth", "", VIOLET, 0), ("e9", "cc", "bash", "", ORANGE, 0),
         ("e10", "orch", "tts", "oraciones", BRASS, 0), ("e11", "tts", "play", "audio", GLACIER, 0),
         ("e12", "play", "user", "voz", GLACIER, 0), ("e13", "orch", "ui", "estado", ROSE, 0),
         ("e14", "orch", "edge", "", VIOLET, 0), ("e15", "act", "term", "activity.log", ORANGE, 0),
         ("e16", "orch", "act", "", ORANGE, 0)]
    for id, a, b, label, col, bend in E:
        s.edge(id, a, b, label, color=col, bend=bend, dashed=id in ("e6", "e14"),
               lpos=0.72 if id == "e6" else 0.5)
    s.beat("Este es el sistema completo. En el centro está un único proceso de Python, jarvis.py, que "
           "corre como servicio de usuario de systemd. Dentro vive el orquestador, la clase Assistant, "
           "que actúa como una máquina de estados conversacional.",
           show=["core", "orch"], focus=["orch"])
    s.beat("El audio entra por pw-record, el cliente de PipeWire, que entrega bloques de ochenta "
           "milisegundos. Sobre ese flujo trabajan dos modelos locales pequeños: openWakeWord, que "
           "busca la palabra de activación, y Silero VAD, que distingue voz humana de ruido.",
           show=["user", "rec", "e1", "e2", "wake", "vad", "e3", "e4"],
           flow=[("e1", "voz"), ("e2", "PCM")], focus=["wake", "vad"])
    s.beat("La transcripción ocurre fuera del proceso principal: en un proceso hijo con faster-whisper, "
           "o en la API de Groq como alternativa. Y la inteligencia está en otro proceso hijo: el "
           "comando claude, que habla con la API de Anthropic y ejecuta herramientas como Bash.",
           show=["stt", "groq", "e5", "e6", "cc", "anth", "bash", "e7", "e8", "e9"],
           flow=[("e5", "audio"), ("e7", "texto"), ("e9", "cmd")], focus=["cc"])
    s.beat("La respuesta vuelve al orquestador, que la convierte en voz con Kokoro, también local, y "
           "la reproduce con pw-play. Edge TTS es un respaldo en línea. En paralelo, el orquestador "
           "actualiza la burbuja visual y registra los comandos que Claude ejecuta en una terminal "
           "de actividad.",
           show=["tts", "play", "ui", "act", "edge", "term", "e10", "e11", "e12", "e13", "e14",
                 "e15", "e16"], flow=[("e10", "texto"), ("e11", "voz"), ("e12", "voz"), ("e15", "log")])
    s.beat("Fíjate en el patrón: un proceso principal ligero que coordina, y trabajo pesado o "
           "privilegiado aislado en procesos hijos. Esa separación explica gran parte del "
           "comportamiento de recursos, de cancelación y de fallos que veremos después.",
           focus=["stt", "cc", "rec", "play"])
    S.append(s)

    s = Scene(1, "Visión general de la arquitectura", subtitle="persistencia y dependencias")
    files = [("cfg", "config.toml", "~/.config/jarvis · ajustes", 230),
             ("key", "groq_key", "permisos 600", 380),
             ("mem", "memory.json", "sesión + resumen · 600", 530),
             ("logs", "jarvis.log · activity.log", "~/.local/state/jarvis", 680),
             ("flags", "gaming_mode · activity_terminal", "interruptores por archivo", 830)]
    for id, t, sub, y in files:
        s.node(id, t, sub, kind="storage", at=(250, y), w=340, h=96)
    s.node("cct", "~/.claude/projects", "transcripciones (las escribe Claude Code)", kind="storage",
           at=(720, 530), w=360, h=110)
    s.node("models", "~/.local/share/jarvis/models", "Kokoro · Whisper (caché HF) · hey_jarvis",
           kind="storage", at=(720, 280), w=360, h=110)
    s.add(Panel("deps", "Dependencias", [
        "Python 3.11+, venv con --system-site-packages (para GTK).",
        "openwakeword 0.6.0 (instalado con --no-deps), onnxruntime, kokoro-onnx, numpy, requests.",
        "Opcionales: faster-whisper + cuBLAS/cuDNN por pip; edge-tts; gtk-layer-shell; playerctl.",
        "Sistema: PipeWire (pw-record, pw-play), systemd, GTK 3.",
        "Externos: CLI de Claude Code autenticado; Groq (clave gratis) si se elige; Edge TTS."],
        (1000, 160, 860, 800), size=21))
    s.beat("La persistencia es deliberadamente simple: archivos planos. La configuración en TOML, la "
           "clave de Groq con permisos seiscientos, y memory.json, que guarda solo el identificador de "
           "la sesión de Claude y un resumen, también con permisos restringidos.",
           show=["cfg", "key", "mem"], focus=["mem"])
    s.beat("Los registros y dos interruptores viven en el directorio de estado: el modo juego y la "
           "terminal de actividad son simplemente archivos cuya existencia o contenido cambia el "
           "comportamiento. Las transcripciones completas de cada conversación no las guarda Jarvis: "
           "las guarda Claude Code en su propio directorio.",
           show=["logs", "flags", "cct", "models"], focus=["cct"])
    s.beat("En dependencias destacan tres detalles. openWakeWord se instala sin dependencias, porque "
           "su metadato exige tflite, que no existe para Python reciente. Las librerías de CUDA llegan "
           "por pip, sin instalar CUDA en el sistema. Y el entorno virtual reutiliza los enlaces de GTK "
           "del sistema.", show=["deps", "deps.0", "deps.1", "deps.2"])
    s.beat("Del sistema se necesita PipeWire, systemd y GTK tres. Y como servicios externos: Claude "
           "Code autenticado con una suscripción o una API, Groq si se elige transcripción en línea, y "
           "Edge TTS como voz de respaldo.", show=["deps.3", "deps.4"])
    S.append(s)

    # ================================================================== 2 LIFECYCLE
    S.append(chapter_card(2, "Inicio y ciclo de vida",
                          ["Instalación", "Arranque del servicio", "Procesos en reposo y estados"],
                          "Capítulo dos: inicio y ciclo de vida de la aplicación."))

    s = Scene(2, "Inicio y ciclo de vida", subtitle="install.sh")
    st = [("i1", "Comprobaciones", "Python 3.11, venv, GTK, PipeWire, curl, systemd"),
          ("i2", "Copia de archivos", "~/.local/share/jarvis"),
          ("i3", "Entorno virtual", "--system-site-packages"),
          ("i4", "Paquetes pip", "requirements + openwakeword --no-deps"),
          ("i5", "Modelos", "hey_jarvis · Kokoro · Whisper"),
          ("i6", "Configuración", "config.toml · elección local o Groq"),
          ("i7", "Clave de Groq", "umask 077 · solo si se elige Groq"),
          ("i8", "Claude Code", "detecta el binario · aviso de login"),
          ("i9", "Servicio", "systemctl --user enable + restart")]
    for i, (id, t, sub) in enumerate(st):
        col, row = i % 3, i // 3
        s.node(id, t, sub, kind="storage" if id in ("i2", "i6", "i7") else
               ("process" if id in ("i8", "i9") else "local"),
               at=(330 + col * 620, 250 + row * 260), w=460, h=110, badge=f"PASO {i + 1}")
    for i in range(8):
        a, b = st[i][0], st[i + 1][0]
        s.edge(f"x{i}", a, b, color=MUTED, bend=0)
    s.beat("La instalación es por usuario y no necesita sudo para Jarvis. El script comprueba los "
           "requisitos del sistema y, si falta algo, imprime el comando exacto para Debian, Fedora o "
           "Arch. Solo la variante de Pop OS ha sido probada en la práctica; las demás están "
           "documentadas pero no verificadas.", show=["i1", "i2", "i3", "x0", "x1"], focus=["i1"])
    s.beat("Después crea el entorno virtual, instala los paquetes y descarga los modelos: la palabra "
           "de activación, la voz de Kokoro y, si se eligió transcripción local, los modelos de Whisper "
           "junto con las librerías de CUDA cuando detecta una tarjeta NVIDIA.",
           show=["i4", "i5", "x2", "x3"])
    s.beat("En una instalación nueva pregunta cómo transcribir: en local o con Groq. Si es Groq, pide "
           "la clave sin mostrarla y la guarda con una máscara de permisos restrictiva. Por último "
           "localiza el binario de Claude Code, instala la unidad de systemd y arranca el servicio.",
           show=["i6", "i7", "i8", "i9", "x4", "x5", "x6", "x7"], focus=["i9"])
    S.append(s)

    s = Scene(2, "Inicio y ciclo de vida", subtitle="arranque del servicio")
    s.add(Sequence("seq", [("sd", "systemd --user", "process"), ("main", "main()", "local"),
                           ("asst", "Assistant()", "local"), ("rec", "pw-record", "audio"),
                           ("gtk", "GTK main loop", "ui"), ("run", "hilo run()", "local")], [
        ("m1", "sd", "main", "graphical-session.target → ExecStart (venv/python -u)", ""),
        ("m2", "main", "main", "logging · flock jarvis.lock (instancia única)", ""),
        ("m3", "main", "asst", "crear Assistant (config TOML sobre DEFAULTS)", ""),
        ("m4", "asst", "asst", "carga openWakeWord + 2 × Silero VAD", ""),
        ("m5", "asst", "rec", "Popen pw-record + hilo lector", "dash"),
        ("m6", "asst", "asst", "Kokoro: carga y calentamiento “Ready.”", ""),
        ("m7", "main", "main", "SIGUSR1 → despertar manual", ""),
        ("m8", "main", "gtk", "crear Burbuja (oculta)", ""),
        ("m9", "main", "run", "lanzar hilo run() (daemon)", "dash"),
        ("m10", "main", "gtk", "Gtk.main() — bucle de eventos", ""),
        ("m11", "run", "run", "leer mic → openWakeWord cada 80 ms", "note")],
        (60, 130, 1800, 860), top=80))
    s.beat("Veamos el arranque. La unidad de systemd depende de la sesión gráfica y de PipeWire, "
           "define el PATH donde suele vivir el binario de Claude, y se reinicia sola si el proceso "
           "termina con error, tras cinco segundos.", show=["seq", "m1"], focus=["m1"])
    s.beat("main configura el registro y toma un candado de archivo para garantizar una sola instancia. "
           "La configuración se carga fusionando el TOML del usuario sobre los valores por defecto "
           "definidos en el propio código.", show=["m2", "m3"])
    s.beat("El constructor de Assistant hace el trabajo caro una sola vez: carga el modelo de "
           "activación, dos instancias independientes de Silero VAD, arranca pw-record con su hilo "
           "lector, y carga Kokoro sintetizando una palabra de prueba para que la primera respuesta "
           "real no pague ese coste.", show=["m4", "m5", "m6"], focus=["m6"])
    s.beat("Se registra la señal SIGUSR1 como despertador manual, se crea la burbuja oculta, se lanza "
           "el hilo run, que es el bucle de detección, y el hilo principal entra en el bucle de eventos "
           "de GTK. Desde aquí, Jarvis está esperando.", show=["m7", "m8", "m9", "m10", "m11"],
           focus=["m11"])
    S.append(s)

    s = Scene(2, "Inicio y ciclo de vida", subtitle="en reposo: procesos, hilos y recursos")
    s.add(Lanes("lanes", [("gtk", "Hilo principal GTK", "ui"), ("run", "Hilo run()", "local"),
                          ("rd", "Hilo lector del mic", "local"), ("mw", "Hilo MediaWatch", "local"),
                          ("rec", "Proceso pw-record", "audio")], [
        ("a1", "gtk", 0, 10, "bucle de eventos · dibuja solo si la burbuja es visible", None),
        ("a2", "run", 0, 10, "bloque → openWakeWord → decisión (cada 80 ms)", None),
        ("a3", "rd", 0, 10, "lee 2560 bytes → cola (máx. 500 ≈ 40 s)", None),
        ("a4", "mw", 0, 10, "playerctl status cada 1,5 s", None),
        ("a5", "rec", 0, 10, "16 kHz · s16 · mono · latencia 40 ms", None)],
        (60, 150, 1180, 540), label_w=280, tmax=10))
    s.add(Bars("res", "Medido en reposo (i5-12400F + RTX 4060)", [
        ("CPU (todo el procesador)", 1.0, 100, "≈ 1 %", BRASS),
        ("RAM (PSS)", 553, 4000, "≈ 553 MB", TEAL),
        ("VRAM", 0.0, 8000, "0 MB", GREEN)], (1320, 170, 520, 380)))
    s.add(Panel("why", "", [
        "El modelo de Whisper NO está cargado en reposo: la GPU queda libre para juegos.",
        "La cola descarta el bloque más antiguo si se llena: nunca bloquea al lector.",
        "Si pw-record muere, el lector termina el proceso y systemd lo reinicia."],
        (60, 740, 1800, 230), size=21))
    s.beat("En reposo hay pocos actores. El hilo principal de GTK atiende eventos. El hilo run toma "
           "cada bloque de audio y se lo pasa a openWakeWord. Un hilo lector separado vacía la tubería "
           "de pw-record hacia una cola acotada.", show=["lanes", "a1", "a2", "a3", "a5"])
    s.beat("Si está configurado el umbral para medios, un cuarto hilo consulta cada segundo y medio "
           "si algún reproductor está sonando. El resultado medido: alrededor de un uno por ciento de "
           "procesador, quinientos cincuenta megas de RAM, y cero de memoria de vídeo.",
           show=["a4", "res", "res.0", "res.1", "res.2"])
    s.beat("Ese cero no es casualidad: Whisper solo se carga al despertar. Y dos decisiones de "
           "robustez: la cola nunca bloquea al lector porque descarta lo más antiguo, y si el "
           "micrófono deja de enviar audio, el proceso termina a propósito para que systemd lo "
           "reinicie limpio.", show=["why", "why.0", "why.1", "why.2"])
    S.append(s)

    s = Scene(2, "Inicio y ciclo de vida", subtitle="estados del sistema")
    pos = {"sleep": (220, 560), "greet": (540, 290), "listen": (960, 290), "stt": (1420, 290),
           "claude": (1680, 600), "speak": (1220, 830), "end": (620, 830)}
    names = {"sleep": ("DORMIDO", "escucha la palabra"), "greet": ("SALUDO", "sonido + frase"),
             "listen": ("ESCUCHANDO", "Silero VAD"), "stt": ("TRANSCRIBIENDO", "Whisper / Groq"),
             "claude": ("CLAUDE TRABAJA", "streaming"), "speak": ("HABLANDO", "Kokoro + pw-play"),
             "end": ("CIERRE", "limpieza y compactación")}
    for k, (x, y) in pos.items():
        t, sub = names[k]
        s.node(k, t, sub, kind="local" if k not in ("speak",) else "audio", at=(x, y), w=270,
               h=96, badge="")
    T = [("t1", "sleep", "greet", "“Hey Jarvis” o SIGUSR1", 0, 0.5),
         ("t2", "greet", "listen", "", 0, 0.5), ("t3", "listen", "stt", "fin de frase", 45, 0.5),
         ("t4", "stt", "claude", "texto", 0, 0.5), ("t5", "claude", "speak", "1.ª oración", 0, 0.5),
         ("t6", "speak", "listen", "turno siguiente", 0, 0.62),
         ("t7", "listen", "end", "10 s de silencio · ✕", 0, 0.45),
         ("t8", "stt", "end", "“gracias” (despedida)", 0, 0.22), ("t9", "end", "sleep", "", 0, 0.5),
         ("t10", "stt", "listen", "frase inacabada", 45, 0.5)]
    for id, a, b, lab, bend, lpos in T:
        s.edge(id, a, b, lab, color=BRASS if id in ("t1", "t9") else MUTED, bend=bend, lpos=lpos,
               loff=(0, 22) if id == "t3" else (0, -16))
    s.beat("A nivel de sistema, Jarvis es una máquina de estados. Dormido, solo corre la detección. La "
           "palabra de activación, o la señal manual, lo llevan al saludo: un sonido y una frase.",
           show=["sleep", "greet", "t1"], focus=["sleep"], flow=["t1"])
    s.beat("Después escucha, transcribe, y si la frase parece inacabada vuelve a escuchar. Con el "
           "texto completo, Claude trabaja, y en cuanto existe la primera oración completa Jarvis "
           "empieza a hablar, mientras Claude todavía escribe el resto.",
           show=["listen", "stt", "claude", "speak", "t2", "t3", "t4", "t5", "t10"],
           flow=["t3", "t4", "t5"], focus=["claude"])
    s.beat("Al terminar de hablar vuelve a escuchar, sin necesidad de repetir la palabra de "
           "activación. La conversación termina con una despedida, con diez segundos de silencio o "
           "con el botón de cerrar, y pasa por una fase de cierre antes de volver a dormir.",
           show=["end", "t6", "t7", "t8", "t9"], flow=["t6", "t9"], focus=["end"])
    S.append(s)

    # ================================================================== 3 WAKE + CAPTURE
    S.append(chapter_card(3, "Detección de activación y captura de audio",
                          ["openWakeWord + patience", "Silero VAD y fin de frase",
                           "Cómo se evitan activaciones accidentales"],
                          "Capítulo tres: detección de activación y captura de audio."))

    s = Scene(3, "Detección de activación y captura de audio", subtitle="¿es realmente “Hey Jarvis”?")
    real = [0.02, 0.03, 0.05, 0.12, 0.71, 0.97, 0.99, 1.0, 1.0, 0.98, 0.4, 0.05, 0.02]
    tv = [0.03, 0.05, 0.04, 0.10, 0.90, 0.20, 0.05, 0.31, 0.12, 0.04, 0.03, 0.02, 0.02]
    s.add(Series("real", "“Hey Jarvis” real: el puntaje se mantiene", real, (110, 200, 700, 300),
                 lines=[(0.3, "registro de casi-activación 0,3", MUTED), (0.5, "umbral 0,5", BRASS)],
                 labels={4: "80 ms"}, xlabel="bloques de 80 ms"))
    s.add(Series("tv", "Voz de un vídeo: un pico aislado", tv, (1010, 200, 700, 300),
                 lines=[(0.3, "0,3", MUTED), (0.5, "0,5", BRASS)], xlabel="bloques de 80 ms"))
    s.add(Panel("rules", "Reglas de decisión (WakeDetector)", [
        "patience = 2: el puntaje debe superar el umbral en 2 bloques seguidos.",
        "Con medios sonando (playerctl / MPRIS) el umbral sube a 0,8.",
        "Picos ≥ 0,3 que no despiertan se registran como “Near miss” para calibrar.",
        "El patience propio de openWakeWord no se usa: guarda los puntajes anulados y nunca dispara."],
        (110, 620, 1700, 340), size=21))
    s.beat("openWakeWord devuelve un puntaje entre cero y uno por cada bloque de ochenta "
           "milisegundos. Un Hey Jarvis real produce una meseta: varios bloques seguidos por encima del "
           "umbral.", show=["real"])
    s.beat("Una voz parecida en una serie suele producir un pico aislado. Por eso la regla no es "
           "superar el umbral una vez, sino mantenerlo durante dos bloques consecutivos. A eso se le "
           "llama patience.", show=["tv", "rules", "rules.0"], focus=["rules.0"])
    s.beat("Además, si algún reproductor informa que está sonando, el umbral sube de cero coma cinco "
           "a cero coma ocho. Y todo pico por encima de cero coma tres que no despierta queda "
           "registrado como casi activación, para ajustar los umbrales con datos reales en lugar de "
           "adivinar.", show=["rules.1", "rules.2"])
    s.beat("Un detalle de ingeniería: la librería ofrece su propio parámetro patience, pero al "
           "probarlo con audio sintético nunca disparaba, porque guarda en su historial los puntajes "
           "ya anulados. Por eso Jarvis cuenta los bloques consecutivos por su cuenta.",
           show=["rules.3"], focus=["rules.3"])
    S.append(s)

    s = Scene(3, "Detección de activación y captura de audio", subtitle="escuchar hasta que termines")
    vad = [0.05, 0.1, 0.08, 0.05, 0.9, 0.95, 0.97, 0.92, 0.6, 0.93, 0.96, 0.9, 0.2, 0.1, 0.94,
           0.97, 0.9, 0.1, 0.05, 0.06, 0.04, 0.05, 0.03, 0.04, 0.05, 0.04, 0.03, 0.02]
    s.add(Series("vad", "Probabilidad de voz (Silero VAD) por bloque", vad, (110, 210, 1700, 280),
                 lines=[(0.5, "umbral 0,5", BRASS)], regions=[
                     ("r1", 0, 4, "esperando voz (hasta 10 s)", MUTED),
                     ("r2", 4, 17, "grabando · pausas cortas toleradas", GLACIER),
                     ("r3", 17, 28, "2 s de silencio → fin de frase", BRASS)]))
    s.add(Table("tbl", ["Parámetro", "Valor", "Para qué"], [
        ["inicio", "0,16 s de voz", "evita que un golpe o tos abra la grabación"],
        ["pre-roll", "6 bloques ≈ 0,48 s", "no se pierde la primera sílaba"],
        ["fin de frase", "end_silence = 2,0 s", "margen para pensar sin cortar"],
        ["mínimo", "0,3 s de voz", "si hubo menos, era ruido: se descarta"],
        ["máximo", "60 s", "límite de una petición"],
        ["frase inacabada", "espera 4 s más", "“abre la carpeta y…”, “because”, “um”"]],
        (110, 600, 1700, 380), widths=[2, 2.4, 5], size=19))
    s.beat("Tras el saludo, Silero VAD decide si cada bloque contiene voz humana. Mientras nadie "
           "habla, Jarvis espera hasta diez segundos. La grabación empieza tras dieciséis centésimas "
           "de segundo de voz, e incluye casi medio segundo de audio previo para no perder la primera "
           "sílaba.", show=["vad", "r1", "tbl", "tbl.0", "tbl.1"])
    s.beat("Durante la grabación se acumula el silencio. Dos segundos seguidos sin voz marcan el fin "
           "de la frase, y hay un tope de sesenta segundos. Si en total hubo menos de tres décimas de "
           "segundo de voz, se considera ruido y se sigue esperando.",
           show=["r2", "r3", "tbl.2", "tbl.3", "tbl.4"], focus=["r3"])
    s.beat("Las pausas para pensar tienen un tratamiento específico. Después de transcribir, si la "
           "frase termina en puntos suspensivos, en coma, o en palabras como y, porque, and, because o "
           "um, Jarvis escucha cuatro segundos más y concatena el resto antes de enviar nada a Claude.",
           show=["tbl.5"], focus=["tbl.5"])
    S.append(s)

    s = Scene(3, "Detección de activación y captura de audio", subtitle="defensa en capas contra falsas activaciones")
    s.node("mic", "Audio del entorno", "tu voz · TV · YouTube", kind="audio", at=(200, 470), w=270)
    layers = [("l1", "Umbral 0,5", "puntaje mínimo"), ("l2", "patience = 2", "meseta, no pico"),
              ("l3", "Umbral de medios 0,8", "si playerctl dice Playing"),
              ("l4", "Saludo + escucha", "sin petición no se llama a Claude")]
    for i, (id, t, sub) in enumerate(layers):
        s.node(id, t, sub, kind="model" if i < 2 else "local", at=(560 + i * 330, 470), w=280)
    s.edge("d0", "mic", "l1", color=GLACIER)
    for i in range(3):
        s.edge(f"d{i + 1}", layers[i][0], layers[i + 1][0], color=GLACIER)
    s.add(Panel("p", "Limitaciones honestas", [
        "El modelo hey_jarvis es solo en inglés y de licencia no comercial (CC BY-NC-SA).",
        "Durante una conversación no se detecta la palabra: solo se escucha la petición o una interrupción.",
        "Un altavoz cercano puede despertar a Jarvis: por eso se recomienda usar auriculares.",
        "Un verificador entrenado con la voz del usuario está planificado, no implementado."],
        (160, 640, 1600, 330), size=21))
    s.beat("Visto como sistema, la protección contra activaciones accidentales es una defensa en "
           "capas: umbral, persistencia del puntaje, umbral reforzado con medios activos, y finalmente "
           "el propio diálogo: una falsa activación solo produce un saludo, y si nadie habla, Jarvis "
           "vuelve a dormir sin llamar a Claude.",
           show=["mic", "l1", "l2", "l3", "l4", "d0", "d1", "d2", "d3"],
           flow=[("d0", "audio"), "d1", "d2", "d3"])
    s.beat("También hay límites. El modelo es solo en inglés y de licencia no comercial. Mientras "
           "dura una conversación la palabra no se busca. Y un verificador entrenado con la voz del "
           "usuario está en el plan, pero no implementado.", show=["p", "p.0", "p.1", "p.2", "p.3"])
    S.append(s)

    # ================================================================== 4 STT
    S.append(chapter_card(4, "Speech-to-Text",
                          ["faster-whisper local frente a Groq",
                           "Proceso hijo y ciclo de vida del modelo", "Liberación de memoria"],
                          "Capítulo cuatro: de audio a texto."))

    s = Scene(4, "Speech-to-Text", subtitle="dos mecanismos")
    s.add(Table("cmp", ["", "faster-whisper local", "Groq Whisper API"], [
        ["Dónde corre", "proceso hijo jarvis_stt.py, GPU o CPU", "servidores de Groq (HTTPS)"],
        ["Modelo", "large-v3-turbo int8_float16; “small” int8 en modo juego", "whisper-large-v3-turbo"],
        ["Privacidad", "el audio nunca sale del equipo", "el audio sale solo tras la activación"],
        ["Latencia medida", "≈ 0,25 s por frase (GPU) · ≈ 1 s (small, CPU)", "depende de la red"],
        ["Recursos", "≈ 1,3 GB VRAM + 1,9 GB RAM mientras está cargado", "casi nulos en local"],
        ["Dependencias", "faster-whisper + cuBLAS/cuDNN por pip", "requests + clave gratuita"],
        ["Si falla", "pasa a Groq si existe la clave", "mensaje hablado y nuevo intento"]],
        (100, 160, 1720, 760), widths=[2, 4.2, 3.8], size=21))
    s.beat("Jarvis tiene dos formas de transcribir. La local usa faster-whisper en un proceso hijo, "
           "sobre la tarjeta gráfica si existe. La alternativa en línea usa la API de Whisper de Groq. "
           "Se elige en la instalación, con el ajuste engine de la sección stt.",
           show=["cmp", "cmp.0", "cmp.1"])
    s.beat("La diferencia de privacidad es clara: en local el audio nunca sale del equipo. Con Groq, "
           "sale, pero solo después de la palabra de activación. En latencia, la versión local tarda "
           "un cuarto de segundo por frase en la gráfica, y alrededor de un segundo con el modelo "
           "pequeño en procesador.", show=["cmp.2", "cmp.3"], focus=["cmp.2"])
    s.beat("El coste local es memoria: alrededor de un giga y tres de VRAM y casi dos de RAM mientras "
           "el modelo está cargado. Y ambos caminos se combinan: si la transcripción local falla y "
           "existe una clave de Groq, se usa Groq como respaldo. El modo Groq, en este equipo, está "
           "implementado pero no fue verificado recientemente.",
           show=["cmp.4", "cmp.5", "cmp.6"], focus=["cmp.4"])
    S.append(s)

    s = Scene(4, "Speech-to-Text", subtitle="ciclo de vida del proceso de Whisper")
    s.add(Sequence("seq", [("conv", "Conversación", "local"), ("stt", "LocalSTT", "local"),
                           ("wk", "jarvis_stt.py", "process"), ("gpu", "GPU (CUDA)", "model")], [
        ("m1", "conv", "stt", "despertar → load() (mientras suena el saludo)", ""),
        ("m2", "stt", "wk", "Popen(modelo, dispositivo, cómputo)", ""),
        ("m3", "wk", "gpu", "precarga cuBLAS/cuDNN · carga int8 · calentamiento", "dash"),
        ("m4", "wk", "stt", "línea JSON {ready} → hilo de espera activa el Event", "dash"),
        ("m5", "conv", "stt", "transcribe(audio)", ""),
        ("m6", "stt", "wk", "stdin: cabecera JSON + muestras float32", ""),
        ("m7", "wk", "stt", "stdout: {text} (timeout de 60 s con select)", "dash"),
        ("m8", "conv", "stt", "fin de la conversación → unload_later(60 s)", ""),
        ("m9", "stt", "wk", "cerrar stdin → el proceso termina", "err"),
        ("m10", "gpu", "gpu", "contexto CUDA liberado: VRAM = 0", "note")],
        (60, 130, 1800, 860), top=80))
    s.beat("¿Por qué un proceso hijo? Porque la única forma de devolver toda la memoria de la "
           "gráfica, incluido el contexto de CUDA, es terminar el proceso que la usa. El proceso "
           "principal nunca importa CUDA.", show=["seq"])
    s.beat("Al despertar, Jarvis lanza el proceso de Whisper mientras suena el saludo, así que los "
           "tres a seis segundos de carga quedan ocultos detrás de la conversación. El hijo precarga "
           "las librerías de CUDA, carga el modelo en int8, lo calienta, y anuncia que está listo con "
           "una línea JSON.", show=["m1", "m2", "m3", "m4"], focus=["m3"])
    s.beat("El protocolo es mínimo: una cabecera JSON con el número de muestras, seguida de las "
           "muestras en float32 por la entrada estándar, y una línea JSON de respuesta por la salida "
           "estándar. Si no hay respuesta en sesenta segundos, el proceso se descarta.",
           show=["m5", "m6", "m7"])
    s.beat("Al terminar la conversación se programa la descarga a los sesenta segundos. Basta cerrar "
           "la entrada estándar: el hijo sale de su bucle y termina, y la memoria de vídeo vuelve a "
           "cero. Si se habla de nuevo antes, el temporizador se cancela y el modelo sigue cargado.",
           show=["m8", "m9", "m10"], focus=["m10"])
    S.append(s)

    s = Scene(4, "Speech-to-Text", subtitle="memoria de vídeo a lo largo del tiempo")
    vram = [0] * 4 + [300, 900, 1300, 1300, 1300, 1300, 1300, 1300, 1300, 1300, 1300, 1300, 1300,
                      1300, 0, 0, 0, 0]
    s.add(Series("v", "VRAM usada por Jarvis (MB)", vram, (110, 220, 1700, 380),
                 lines=[(1300, "≈ 1,3 GB", GREEN)], ymax=1600, color=GREEN, regions=[
                     ("g1", 0, 4, "dormido: 0 MB", MUTED),
                     ("g2", 4, 7, "carga durante el saludo", GLACIER),
                     ("g3", 7, 14, "conversación", BRASS),
                     ("g4", 14, 18, "60 s de gracia", MUTED),
                     ("g5", 18, 22, "liberado", GREEN)]))
    s.add(Panel("p", "", [
        "Filtro de alucinaciones: frases típicas de Whisper sobre ruido (“subtítulos de Amara.org”) se descartan.",
        "Groq: modelo whisper-large-v3-turbo, temperatura 0, timeout de 30 s.",
        "unload_after = -1 mantiene el modelo siempre cargado (sin espera, pero con la VRAM ocupada)."],
        (110, 700, 1700, 270), size=21))
    s.beat("El resultado, en el tiempo: cero megas mientras Jarvis duerme, carga durante el saludo, "
           "un giga y tres durante la conversación, sesenta segundos de gracia, y de nuevo cero. Es un "
           "compromiso explícito entre latencia del primer turno y memoria disponible para otras "
           "aplicaciones.", show=["v", "g1", "g2", "g3", "g4", "g5"])
    s.beat("Dos detalles más del texto resultante: se descartan frases que Whisper alucina sobre "
           "ruido, como créditos de subtítulos, y el camino de Groq usa temperatura cero y un tiempo "
           "límite de treinta segundos.", show=["p", "p.0", "p.1", "p.2"])
    S.append(s)

    S.extend(build_part2())
    return S


# Chapters 5-13 live in scenes2.py to keep files readable.
def build_part2():
    from scenes2 import build as b2
    return b2()
