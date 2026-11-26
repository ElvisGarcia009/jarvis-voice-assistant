"""Chapters 5-13 and the closing of the Jarvis architecture video (narration in Spanish)."""
from engine import (Scene, Group, Panel, Code, Sequence, Table, Series, Lanes, Bars, Orb,
                    Terminal, Caption, BRASS, GLACIER, VIOLET, TEAL, ORANGE, ROSE, RED, GREEN,
                    TEXT, MUTED, hexrgb)
from scenes import chapter_card


def build():
    S = []

    # ================================================================== 5 CLAUDE
    S.append(chapter_card(5, "Orquestación e integración con Claude Code",
                          ["Quién hace qué", "Un subproceso por petición, con streaming",
                           "Sesión, contexto y memory.json"],
                          "Capítulo cinco, el corazón del sistema: la orquestación con Claude Code."))

    s = Scene(5, "Orquestación con Claude Code", subtitle="división de responsabilidades")
    s.add(Panel("j", "Jarvis (orquestador)", [
        "Oído: activación, VAD, transcripción.",
        "Voz: dividir en oraciones, sintetizar y reproducir.",
        "Ciclo de vida: lanzar, leer y cancelar el proceso claude.",
        "Sesión: qué conversación reanudar y cuándo compactar.",
        "Interfaz, terminal de actividad, interrupciones."],
        (80, 160, 860, 640), size=23, color=BRASS))
    s.add(Panel("c", "Claude Code (motor de ejecución)", [
        "Razonar sobre la petición con el modelo de Anthropic.",
        "Elegir y ejecutar herramientas: Bash, leer, escribir, editar, buscar, web.",
        "Aplicar el modo de permisos “auto” (clasificador de seguridad).",
        "Guardar la transcripción de la sesión y reanudarla con --resume.",
        "Informar tokens, coste y resultado final."],
        (980, 160, 860, 640), size=23, color=hexrgb("#D9C9A3")))
    s.add(Caption("k", "Jarvis nunca ejecuta comandos por sí mismo: todo lo que toca el sistema operativo "
                  "pasa por Claude Code.", (960, 850), size=24, color=ORANGE, anchor="tc", width=1600,
                  align="center", box=True))
    s.beat("Conviene separar responsabilidades con precisión. Jarvis es el orquestador: oye, habla, "
           "gestiona el ciclo de vida del proceso de Claude, decide qué sesión reanudar, y coordina la "
           "interfaz y las interrupciones.", show=["j", "j.0", "j.1", "j.2", "j.3", "j.4"])
    s.beat("Claude Code es el motor de ejecución: razona con el modelo, elige herramientas, las "
           "ejecuta bajo su sistema de permisos, y guarda la transcripción de la sesión. La "
           "consecuencia importante es que Jarvis nunca ejecuta comandos por sí mismo.",
           show=["c", "c.0", "c.1", "c.2", "c.3", "c.4", "k"], focus=["k"])
    S.append(s)

    s = Scene(5, "Orquestación con Claude Code", subtitle="anatomía de la llamada")
    s.add(Code("cmd", "_claude_cmd() + Popen  (una ejecución por petición)", [
        "claude -p \"<transcripción>\"",
        "  --output-format stream-json --verbose",
        "  --include-partial-messages",
        "  --model sonnet                # haiku en el equipo del autor",
        "  --permission-mode auto",
        "  --append-system-prompt \"<reglas de voz y seguridad + memoria>\"",
        "  --tools Bash,Read,Write,Edit,Glob,Grep,WebFetch,WebSearch",
        "  --strict-mcp-config --disable-slash-commands",
        "  --resume <session_id>         # si la sesión es reciente",
        "",
        "Popen(cwd=HOME, stdin=DEVNULL, start_new_session=True)"],
        (70, 170, 1120, 690), size=19, notes={
            1: ("n1", "eventos JSON línea a línea"),
            2: ("n2", "texto token a token"),
            4: ("n3", "clasificador de seguridad"),
            5: ("n4", "estilo hablado, confirmar lo irreversible"),
            6: ("n5", "8 herramientas: ~11k tokens en vez de ~36k"),
            7: ("n6", "sin MCP ni skills del usuario"),
            8: ("n7", "continuidad conversacional"),
            10: ("n8", "grupo de procesos propio")}))
    s.beat("Así se invoca a Claude. Cada petición lanza un proceso nuevo del binario claude en modo no "
           "interactivo. Con stream-json y mensajes parciales, la salida llega como una línea JSON por "
           "evento, incluyendo el texto a medida que el modelo lo genera.",
           show=["cmd", "n1", "n2"])
    s.beat("El modo de permisos auto delega en el clasificador de seguridad de Claude Code qué acciones "
           "se permiten. El prompt de sistema añadido impone el estilo hablado, prohíbe listas y "
           "bloques de código, y exige pedir un sí antes de cualquier acción irreversible.",
           show=["n3", "n4"])
    s.beat("Una decisión de coste: se limitan las herramientas a ocho. Cada descripción de herramienta "
           "viaja en cada petición, y el conjunto por defecto ocupaba unos veinticinco mil tokens. Con "
           "esta lista, más la desactivación de servidores MCP y skills, el contexto base baja de unos "
           "treinta y seis mil a unos once mil tokens.", show=["n5", "n6"], focus=["n5"])
    s.beat("Con resume se continúa la sesión anterior. Y el proceso se lanza en su propio grupo de "
           "procesos, sin entrada estándar, que si fuera una tubería le haría esperar tres segundos. El "
           "grupo propio es lo que después permite cancelarlo por completo.", show=["n7", "n8"])
    S.append(s)

    s = Scene(5, "Orquestación con Claude Code", subtitle="una petición, evento por evento")
    s.add(Sequence("seq", [("conv", "Hilo de conversación", "local"), ("wk", "Hilo worker", "local"),
                           ("cc", "claude -p", "process"), ("api", "API Anthropic", "external"),
                           ("sh", "Bash", "exec")], [
        ("m1", "conv", "wk", "ask_and_speak(): lanzar worker", ""),
        ("m2", "wk", "cc", "Popen (línea de comandos anterior)", ""),
        ("m3", "cc", "wk", "system/init → session_id", "dash"),
        ("m4", "cc", "api", "petición al modelo", ""),
        ("m5", "cc", "wk", "text_delta “Voy a revisarlo…”", "dash"),
        ("m6", "cc", "wk", "content_block_start: tool_use → “One moment…”", "dash"),
        ("m7", "cc", "sh", "df -h /home", "exec"),
        ("m8", "sh", "cc", "salida del comando", "exec"),
        ("m9", "cc", "wk", "assistant/user: tool_use + tool_result → terminal", "dash"),
        ("m10", "cc", "wk", "text_delta… (respuesta final)", "dash"),
        ("m11", "cc", "wk", "result: session_id · usage · coste", "dash"),
        ("m12", "wk", "conv", "oraciones en cola → voz · memoria actualizada", "")],
        (60, 130, 1800, 860), top=80))
    s.beat("Sigamos una petición evento por evento. El hilo de conversación lanza un hilo trabajador, "
           "y ese hilo lanza el proceso claude y lee su salida línea a línea. Otro hilo pequeño vacía "
           "el error estándar para que la tubería nunca se bloquee.", show=["seq", "m1", "m2"])
    s.beat("El primer evento, init, ya trae el identificador de sesión. Luego llegan fragmentos de "
           "texto. Cuando empieza un bloque de uso de herramienta, si Jarvis todavía no ha dicho nada, "
           "dice una frase corta como one moment, I'm checking that, para no dejar un silencio largo.",
           show=["m3", "m4", "m5", "m6"], focus=["m6"])
    s.beat("Claude ejecuta el comando con su herramienta Bash y recibe la salida. Esos mismos eventos, "
           "el uso de herramienta con su entrada completa y su resultado, alimentan la terminal de "
           "actividad que el usuario puede ver en pantalla.",
           show=["m7", "m8", "m9"], focus=["m9"])
    s.beat("Después llega el texto final y el evento result, con el identificador de sesión, el uso de "
           "tokens y el coste estimado. Jarvis actualiza la memoria, registra el consumo, y espera como "
           "máximo diez segundos a que el proceso termine.", show=["m10", "m11", "m12"],
           focus=["m11"])
    S.append(s)

    s = Scene(5, "Orquestación con Claude Code", subtitle="streaming: de fragmentos a oraciones")
    s.node("cc", "claude stdout", "una línea JSON por evento", kind="process", at=(220, 330), w=280)
    s.node("parse", "Parser de eventos", "_run_claude_stream", kind="local", at=(620, 330), w=300)
    s.node("split", "SentenceStream", "corta en . ! ? … : ;", kind="local", at=(1040, 330), w=300)
    s.node("q", "Cola de oraciones", "None = fin", kind="local", at=(1460, 330), w=280)
    s.node("tts", "Voz", "Kokoro + pw-play", kind="audio", at=(1460, 600), w=280)
    s.node("ui", "Burbuja", "texto acumulado", kind="ui", at=(1040, 600), w=280)
    s.node("con", "ActivityConsole", "tool_use / tool_result", kind="local", at=(620, 600), w=300)
    for id, a, b, lab, col in [("a", "cc", "parse", "líneas", MUTED), ("b", "parse", "split", "text_delta", BRASS),
                               ("c", "split", "q", "oración", BRASS), ("d", "q", "tts", "", GLACIER),
                               ("e", "split", "ui", "", ROSE), ("f", "parse", "con", "herramientas", ORANGE)]:
        s.edge(id, a, b, lab, color=col)
    s.add(Code("ex", "Ejemplo real de fragmentos", [
        "'Hel'                 → —",
        "'lo there. How'       → 'Hello there.'",
        "' are you?\\n\\nFi'     → 'How are you?'",
        "'ne'  + fin de bloque  → 'Fine'"], (160, 760, 1000, 210), size=18))
    s.add(Panel("p", "", ["Se ignoran eventos de subagentes (parent_tool_use_id).",
                          "Si nada llegó por streaming, se habla el campo result."],
                (1200, 760, 660, 210), size=19))
    s.beat("El streaming es lo que hace que Jarvis parezca rápido. El parser clasifica cada evento: "
           "los fragmentos de texto van a un divisor de oraciones, y los eventos de herramientas van a "
           "la consola de actividad.", show=["cc", "parse", "split", "con", "a", "b", "f"],
           flow=[("a", "JSON"), ("b", "texto"), ("f", "tool")])
    s.beat("El divisor acumula texto y entrega una oración en cuanto aparece un signo de puntuación "
           "seguido de espacio. Cada oración completa entra en una cola, y el hilo de conversación la "
           "consume y la convierte en voz mientras Claude sigue escribiendo la siguiente.",
           show=["q", "tts", "ui", "c", "d", "e", "ex"], flow=[("c", "oración"), ("d", "voz")],
           focus=["split"])
    s.beat("Dos salvaguardas: los eventos de subagentes se descartan, para no leer en voz alta "
           "trabajo intermedio, y si por algún motivo no llegó texto por streaming, se habla el campo "
           "result del evento final.", show=["p", "p.0", "p.1"])
    S.append(s)

    s = Scene(5, "Orquestación con Claude Code", subtitle="sesión, contexto y memory.json")
    s.node("mem", "memory.json", "session_id · last_used · context_tokens · summary", kind="storage",
           at=(300, 330), w=420, h=120)
    s.node("cc", "Claude Code", "--resume <session_id>", kind="process", at=(960, 330), w=320, h=110)
    s.node("tr", "~/.claude/projects/*.jsonl", "transcripción completa de la sesión", kind="storage",
           at=(1560, 330), w=420, h=120)
    s.edge("r1", "mem", "cc", "¿usada hace < 12 h? → reanudar", color=TEAL)
    s.edge("r2", "cc", "tr", "escribe cada turno", color=TEAL)
    s.add(Code("json", "memory.json (escritura atómica: .tmp + rename, permisos 600)", [
        "{",
        "  \"session_id\": \"a754d6d7-…\",",
        "  \"last_used\": 1764029837.2,",
        "  \"context_tokens\": 33226,",
        "  \"summary\": \"- Disk: about 90 GB free …\"",
        "}"], (110, 520, 800, 300), size=19))
    s.add(Panel("p", "Cómo se mide el contexto", [
        "Una respuesta con herramientas hace varias llamadas a la API y usage las suma.",
        "Jarvis usa la ÚLTIMA iteración: su entrada es la conversación completa.",
        "Claude Code congela el prompt de sistema en el primer turno: los cambios llegan a sesiones nuevas."],
        (960, 500, 900, 470), size=21))
    s.beat("La continuidad conversacional tiene dos capas. Jarvis guarda en memory.json solo un "
           "puntero: el identificador de sesión, cuándo se usó, cuántos tokens tiene el contexto, y un "
           "resumen opcional. Si la sesión se usó hace menos de doce horas, se reanuda con resume.",
           show=["mem", "cc", "r1", "json"], flow=[("r1", "session_id")], focus=["mem"])
    s.beat("El historial real lo guarda Claude Code en su propio directorio, turno a turno. Es decir, "
           "la memoria a corto plazo es la transcripción de Claude, y Jarvis solo decide cuál "
           "continuar.", show=["tr", "r2"], flow=["r2"])
    s.beat("Para saber cuándo compactar hay que medir bien el tamaño. Una respuesta con herramientas "
           "hace varias llamadas, y el uso total las suma; por eso Jarvis toma la última iteración, cuya "
           "entrada es la conversación completa. Un matiz: Claude Code congela el prompt de sistema en "
           "el primer turno de cada sesión.", show=["p", "p.0", "p.1", "p.2"], focus=["p.1"])
    S.append(s)

    s = Scene(5, "Orquestación con Claude Code", subtitle="compactación de memoria")
    s.add(Lanes("ln", [("ses", "Sesión de Claude", "process"), ("ctx", "Tamaño del contexto", "local"),
                       ("mem", "memory.json", "storage")], [
        ("s1", "ses", 0, 6.2, "sesión A: se reanuda en cada activación (< 12 h)", None),
        ("s2", "ctx", 0, 6.2, "crece turno a turno: 33k → 45k → 61k", None),
        ("s3", "ses", 6.2, 7.6, "resumen (haiku)", BRASS),
        ("s4", "mem", 6.2, 7.6, "summary nuevo · session_id = null", None),
        ("s5", "ses", 7.6, 10, "sesión B: prompt + resumen", GREEN),
        ("s6", "ctx", 7.6, 10, "vuelve a ~11k", GREEN)],
        (60, 170, 1800, 420), label_w=300, tmax=10, axis="tiempo (varias conversaciones)"))
    s.add(Panel("p", "Reglas de compactación", [
        "Solo DESPUÉS de una conversación, para no retrasar ninguna respuesta.",
        "Si context_tokens > max_context_tokens (60 000 por defecto).",
        "Petición no streaming con summary_model: “notas privadas, máx. 10 líneas, sin herramientas”.",
        "Si el resumen falla, la sesión se conserva tal cual; si dice “(nothing)”, se mantiene el anterior.",
        "Ocurrió 6 veces en los primeros 3 días de uso real."],
        (60, 650, 1800, 330), size=21))
    s.beat("Una sesión que crece sin límite encarece y ralentiza cada respuesta. La solución es la "
           "compactación: cuando una conversación termina y el contexto supera sesenta mil tokens, "
           "Jarvis pide a un modelo barato que resuma lo aprendido.",
           show=["ln", "s1", "s2", "p", "p.0", "p.1"])
    s.beat("El resumen se guarda en memory.json y el identificador de sesión se borra. La próxima "
           "activación empieza una sesión nueva, con el resumen añadido al prompt de sistema, y el "
           "contexto vuelve a unos once mil tokens.",
           show=["s3", "s4", "s5", "s6", "p.2"], focus=["s3"])
    s.beat("La compactación es tolerante a fallos: si no se puede resumir, la sesión se conserva. Y "
           "como ocurre después de la despedida, el usuario nunca espera por ella.",
           show=["p.3", "p.4"])
    S.append(s)

    # ================================================================== 6 SCENARIO + SECURITY
    S.append(chapter_card(6, "Ejecución de acciones y seguridad",
                          ["Escenario: “¿Cuánto espacio libre tengo?”", "La terminal de actividad",
                           "Modelo de permisos y riesgos"],
                          "Capítulo seis: ejecución de acciones y seguridad, con un escenario real."))

    s = Scene(6, "Ejecución de acciones y seguridad", subtitle="de la voz al comando (registro real)")
    s.add(Lanes("ln", [("u", "Usuario", "audio"), ("j", "Jarvis", "local"), ("w", "Whisper", "process"),
                       ("c", "Claude Code", "process"), ("b", "Bash", "exec"), ("v", "Voz", "audio")], [
        ("a1", "u", 0, 0.9, "“Hey Jarvis”", None),
        ("a2", "j", 0.9, 1.6, "saludo", None),
        ("a3", "w", 0.9, 3.2, "carga (oculta)", None),
        ("a4", "u", 1.8, 4.4, "“¿cuánto espacio libre…?”", None),
        ("a5", "j", 4.4, 6.4, "2 s de silencio", MUTED),
        ("a6", "w", 6.4, 6.8, "0,4 s", None),
        ("a7", "c", 6.9, 8.2, "decide", None),
        ("a8", "v", 8.2, 9.6, "“One moment…”", None),
        ("a9", "b", 8.3, 8.8, "df -h", None),
        ("a10", "c", 8.8, 11.0, "redacta", None),
        ("a11", "v", 10.2, 14.0, "“Tienes unos 79 GB libres…”", None)],
        (60, 160, 1800, 600), label_w=220, tmax=14, axis="segundos (aprox., Haiku)"))
    s.add(Caption("n", "El silencio de fin de frase (2 s) es la mayor espera fija: una decisión de "
                  "confort, no un límite técnico.", (960, 830), size=22, color=BRASS, anchor="tc",
                  width=1500, align="center", box=True))
    s.beat("Ahora el escenario completo, con tiempos aproximados tomados de los registros. El usuario "
           "dice Hey Jarvis; mientras suena el saludo, Whisper se carga en segundo plano.",
           show=["ln", "a1", "a2", "a3"])
    s.beat("El usuario pregunta cuánto espacio libre tiene. Jarvis espera dos segundos de silencio "
           "para estar seguro de que terminó, y Whisper transcribe la frase en unas cuatro décimas de "
           "segundo.", show=["a4", "a5", "a6"], focus=["a5"])
    s.beat("Claude decide que necesita un comando. En cuanto aparece el bloque de herramienta, Jarvis "
           "dice one moment. Claude ejecuta df, lee la salida y redacta la respuesta, que empieza a "
           "sonar en cuanto existe la primera oración.",
           show=["a7", "a8", "a9", "a10", "a11"], focus=["a9"])
    s.beat("Observa dónde está la mayor espera fija: no en el modelo, sino en los dos segundos de "
           "silencio que marcan el fin de la frase. Es una decisión de comodidad para quien hace "
           "pausas al hablar, y se puede ajustar.", show=["n"], focus=["n"])
    S.append(s)

    s = Scene(6, "Ejecución de acciones y seguridad", subtitle="la terminal de actividad")
    s.add(Terminal("term", "Jarvis activity", [
        ("What Jarvis does on your computer. You can close this window.", MUTED),
        ("", TEXT),
        ("━━ 19:55  How much free disk space do I have?", hexrgb("#FFF3D6")),
        ("# Show free disk space for home and total", MUTED),
        ("$ df -h /home/elvis", GREEN),
        ("  Filesystem      Size  Used Avail Use% Mounted on", TEXT),
        ("  /dev/nvme0n1p7  195G   96G   90G  52% /", TEXT),
        ("", TEXT),
        ("━━ 19:55  And how much RAM is free right now?", hexrgb("#FFF3D6")),
        ("$ free -h", GREEN),
        ("  Mem:   15Gi   9.3Gi   2.3Gi   …   6.2Gi", TEXT)], (70, 160, 1020, 600), size=19))
    s.add(Panel("p", "Cómo funciona", [
        "Cada tool_use se escribe en activity.log: “$ comando” para Bash, “▸ Herramienta ruta” para el resto.",
        "La salida de Bash se muestra (cortada a 30 líneas); la de lecturas, solo como resumen.",
        "Una terminal (cosmic-term -e …) sigue el archivo con tail -F desde el byte justo anterior.",
        "Una ventana por conversación: se reutiliza y se cierra al volver a dormir.",
        "“activate / deactivate terminal” la enciende o apaga (archivo activity_terminal)."],
        (1130, 160, 730, 810), size=20))
    s.beat("Para que el usuario sepa en todo momento qué hace el agente, cada uso de herramienta se "
           "escribe en un archivo de actividad, con el formato de una terminal: un comentario con la "
           "intención, el comando con el signo de dólar, y su salida.",
           show=["term", "term.*", "p", "p.0", "p.1"])
    s.beat("La primera vez que Claude usa una herramienta en una conversación, Jarvis abre una "
           "terminal que sigue ese archivo desde el byte anterior al primer comando, así solo muestra "
           "lo nuevo. Se reutiliza para las siguientes peticiones y se cierra al volver a dormir. Con "
           "terminales distintas de COSMIC, el comportamiento está implementado pero no verificado.",
           show=["p.2", "p.3", "p.4"], focus=["term"])
    S.append(s)

    s = Scene(6, "Ejecución de acciones y seguridad", subtitle="modelo de permisos y riesgos")
    s.add(Table("t", ["Capa", "Qué hace", "Tipo de control"], [
        ["Activación", "patience, umbrales, auriculares recomendados", "probabilístico"],
        ["permission-mode auto", "el clasificador de Claude Code bloquea acciones de riesgo", "técnico, externo"],
        ["Prompt de sistema", "pedir un “sí” antes de borrar, desinstalar o cambiar ajustes", "blando: depende del modelo"],
        ["8 herramientas", "reduce superficie… pero Bash ya lo puede todo como el usuario", "parcial"],
        ["sudo", "no funciona: requiere contraseña y no hay terminal", "técnico"],
        ["Visibilidad", "terminal de actividad + activity.log + jarvis.log", "auditoría"],
        ["Datos", "groq_key y memory.json con permisos 600; audio a Groq solo tras activar", "técnico"]],
        (70, 160, 1780, 560), widths=[2.2, 5.4, 2.4], size=20))
    s.add(Panel("r", "Riesgos que permanecen", [
        "Cualquier voz o vídeo cercano puede hablarle al agente.",
        "Inyección de instrucciones desde páginas web o archivos que Claude lee.",
        "Sin sandbox: corre con todos los permisos del usuario. bypassPermissions está desaconsejado."],
        (70, 750, 1780, 220), size=20, color=RED))
    s.beat("La seguridad se apoya en capas de naturaleza distinta. La primera es la activación misma. "
           "La segunda, técnica pero externa a Jarvis, es el modo de permisos auto: el clasificador de "
           "Claude Code decide qué acciones bloquear.", show=["t", "t.0", "t.1"], focus=["t.1"])
    s.beat("La tercera es blanda: el prompt de sistema pide confirmar con un sí antes de borrar, "
           "desinstalar o cambiar ajustes, pero depende de que el modelo obedezca. Restringir a ocho "
           "herramientas reduce superficie, aunque Bash por sí solo ya puede hacer todo lo que el "
           "usuario puede hacer.", show=["t.2", "t.3"], focus=["t.2"])
    s.beat("sudo no funciona, porque pediría una contraseña sin terminal. Todo queda visible y "
           "registrado, y los datos sensibles se guardan con permisos restringidos.",
           show=["t.4", "t.5", "t.6"])
    s.beat("Los riesgos que permanecen son reales: cualquier voz cercana puede dar órdenes, el "
           "contenido que Claude lee puede contener instrucciones maliciosas, y no hay sandbox: el "
           "agente corre con los permisos del usuario. Por eso el proyecto desaconseja expresamente "
           "el modo que salta los permisos.", show=["r", "r.0", "r.1", "r.2"])
    S.append(s)

    # ================================================================== 7 TTS
    S.append(chapter_card(7, "Text-to-Speech",
                          ["Kokoro local en streaming", "Hablar mientras Claude escribe",
                           "Respaldo con Edge TTS"],
                          "Capítulo siete: de texto a voz."))

    s = Scene(7, "Text-to-Speech", subtitle="Kokoro: del texto al altavoz")
    s.node("q", "Oraciones", "cola o lista", kind="local", at=(200, 330), w=230)
    s.node("pc", "_kokoro_pieces", "1.ª oración > 50 car. → corta en la coma", kind="local",
           at=(560, 330), w=320)
    s.node("k", "Kokoro ONNX", "CPU · 24 kHz · int8", kind="model", at=(960, 330), w=280)
    s.node("pp", "pw-play --raw f32", "stdin abierto toda la respuesta", kind="audio",
           at=(1380, 330), w=320)
    s.node("sp", "Altavoz", "", kind="audio", at=(1730, 330), w=180)
    s.node("tl", "Línea de tiempo", "inicio, fin, texto y envolvente (30 fps)", kind="local",
           at=(960, 600), w=360)
    s.node("ui", "Burbuja", "subtítulo y nivel del orbe", kind="ui", at=(1380, 600), w=300)
    for id, a, b, lab, col in [("a", "q", "pc", "", BRASS), ("b", "pc", "k", "fragmento", BRASS),
                               ("c", "k", "pp", "PCM float32", GLACIER), ("d", "pp", "sp", "", GLACIER),
                               ("e", "k", "tl", "", MUTED), ("f", "tl", "ui", "", ROSE)]:
        s.edge(id, a, b, lab, color=col)
    s.add(Panel("p", "Detalles", [
        "Mezcla de voces: “am_onyx+am_michael” promedia los vectores de estilo.",
        "Voz más grave: se sintetiza más rápido y se reproduce a 24000 × (1 − 0,08) = 22 080 Hz.",
        "Se genera más rápido que tiempo real (≈ 6×), así que nunca se queda sin audio por cálculo."],
        (110, 740, 1700, 230), size=20))
    s.beat("Kokoro es un modelo de voz pequeño que corre en el procesador con ONNX. Recibe oraciones, y "
           "la primera, si es larga, se corta en la primera coma para que el sonido empiece antes.",
           show=["q", "pc", "k", "a", "b"], flow=[("b", "texto")])
    s.beat("El audio generado se escribe directamente en la entrada estándar de un único pw-play, que "
           "permanece abierto durante toda la respuesta. En paralelo se registra una línea de tiempo con "
           "el texto y la envolvente de volumen de cada fragmento, que la burbuja usa para los "
           "subtítulos y la animación.", show=["pp", "sp", "c", "d", "tl", "ui", "e", "f"],
           flow=[("c", "PCM"), ("d", "voz"), ("f", "nivel")])
    s.beat("Dos trucos de configuración: se pueden mezclar voces promediando sus vectores de estilo, "
           "y la voz grave se consigue sintetizando más rápido y reproduciendo a una frecuencia de "
           "muestreo menor. Como la síntesis es unas seis veces más rápida que el habla, el cálculo "
           "nunca deja al altavoz sin audio.", show=["p", "p.0", "p.1", "p.2"])
    S.append(s)

    s = Scene(7, "Text-to-Speech", subtitle="hablar mientras Claude todavía escribe")
    s.add(Lanes("ln", [("c", "Claude (texto)", "process"), ("s", "SentenceStream", "local"),
                       ("k", "Kokoro (síntesis)", "model"), ("p", "pw-play (audio)", "audio")], [
        ("c1", "c", 0, 2.2, "oración 1", None), ("c2", "c", 2.2, 4.6, "oración 2", None),
        ("c3", "c", 4.6, 7.0, "oración 3", None),
        ("s1", "s", 2.2, 2.5, "", None), ("s2", "s", 4.6, 4.9, "", None), ("s3", "s", 7.0, 7.3, "", None),
        ("k1", "k", 2.5, 3.0, "", None), ("k2", "k", 4.9, 5.4, "", None), ("k3", "k", 7.3, 7.8, "", None),
        ("p1", "p", 3.1, 6.0, "suena la oración 1", None), ("p2", "p", 6.0, 8.6, "oración 2", None),
        ("p3", "p", 8.6, 11.0, "oración 3", None)],
        (60, 170, 1800, 470), label_w=300, tmax=11, axis="tiempo"))
    s.add(Panel("p", "", [
        "Antes: se esperaba la respuesta completa (--output-format json) y luego se hablaba.",
        "Ahora: la latencia percibida es la de la PRIMERA oración, no la de toda la respuesta.",
        "Entre oraciones, pw-play simplemente espera más datos: no hay cortes ni reaperturas."],
        (60, 700, 1800, 270), size=21))
    s.beat("Este diagrama muestra la concurrencia del habla. Claude genera la oración uno; en cuanto "
           "termina, el divisor la entrega, Kokoro la sintetiza en medio segundo, y empieza a sonar "
           "mientras Claude ya está escribiendo la oración dos.",
           show=["ln", "c1", "s1", "k1", "p1", "c2"])
    s.beat("El proceso se repite como una cadena de montaje. La latencia percibida deja de ser la de "
           "la respuesta completa y pasa a ser la de la primera oración. Antes del streaming, Jarvis "
           "esperaba a que Claude terminara todo antes de decir una palabra.",
           show=["s2", "k2", "p2", "c3", "s3", "k3", "p3", "p", "p.0", "p.1", "p.2"])
    S.append(s)

    s = Scene(7, "Text-to-Speech", subtitle="respaldo con Edge TTS")
    s.node("k", "Kokoro", "falla en un fragmento", kind="model", at=(260, 330), w=280)
    s.node("rest", "Oraciones restantes", "chain(fragmento, resto)", kind="local", at=(700, 330), w=320)
    s.node("prod", "Hilo productor", "sintetiza la siguiente mientras suena una", kind="local",
           at=(1150, 330), w=330)
    s.node("edge", "Edge TTS", "MP3 por oración · 2 intentos", kind="external", at=(1150, 600), w=300)
    s.node("play", "pw-play archivo.mp3", "orbe con pulso simulado", kind="audio", at=(1600, 330),
           w=300)
    for id, a, b, lab, col in [("a", "k", "rest", "excepción", RED), ("b", "rest", "prod", "", BRASS),
                               ("c", "prod", "edge", "HTTPS", VIOLET), ("d", "edge", "prod", "", VIOLET),
                               ("e", "prod", "play", "mp3", GLACIER)]:
        s.edge(id, a, b, lab, color=col, bend=40 if id in ("c", "d") else 0)
    s.add(Panel("p", "", [
        "No se repite lo ya dicho: el respaldo continúa desde el fragmento que falló.",
        "Si Edge falla dos veces en una oración, esa oración se omite.",
        "Implementado; no verificado en el equipo de pruebas (Kokoro no ha fallado)."],
        (110, 760, 1700, 210), size=20))
    s.beat("Si Kokoro lanza una excepción en mitad de una respuesta, el generador devuelve las "
           "oraciones que faltan, empezando por la que falló, para no repetir lo ya dicho. Edge TTS, el "
           "servicio de voz en línea de Microsoft, continúa desde ahí.",
           show=["k", "rest", "a", "b", "prod"], flow=[("a", "error")])
    s.beat("Edge funciona por oraciones completas en MP3, con un hilo productor que prepara la "
           "siguiente mientras suena la actual, y dos intentos por oración. Al no tener muestras, el "
           "orbe usa un pulso simulado. Este camino está implementado, pero no se ha verificado en el "
           "equipo de pruebas.", show=["edge", "play", "c", "d", "e", "p", "p.0", "p.1", "p.2"],
           flow=["c", "e"])
    S.append(s)

    # ================================================================== 8 UI
    S.append(chapter_card(8, "Interfaz visual y sincronización",
                          ["Estados del orbe", "Hilos y bucle de GTK", "Subtítulos sincronizados"],
                          "Capítulo ocho: la interfaz visual y su sincronización."))

    s = Scene(8, "Interfaz visual y sincronización", subtitle="los cuatro estados de la burbuja")
    orbs = [("o1", "sleeping", "Dormido", "brasa que respira · burbuja oculta"),
            ("o2", "listening", "Escuchando", "núcleo glaciar que crece con tu voz"),
            ("o3", "thinking", "Pensando", "tres cuentas que orbitan"),
            ("o4", "speaking", "Hablando", "ondas al ritmo de su voz")]
    for i, (id, st, lab, sub) in enumerate(orbs):
        s.add(Orb(id, st, (260 + i * 460, 380), label=lab, sub=sub, scale=1.7))
    s.add(Panel("p", "", [
        "No existe un estado “Interrumpido”: una interrupción es la transición Hablando → Escuchando.",
        "Botones: ■ solo al hablar; ✕ al escuchar, pensar o hablar.",
        "Clic en el orbe: al hablar → callar; al pensar → cancelar la petición; dormido → despertar."],
        (110, 700, 1700, 270), size=21))
    s.beat("La burbuja tiene exactamente cuatro estados. Dormido, oculta, con una brasa que respira. "
           "Escuchando, con un núcleo que crece con el volumen de tu voz. Pensando, con tres cuentas "
           "que orbitan como un reloj. Y hablando, con ondas que salen al ritmo de la voz de Jarvis.",
           show=["o1", "o2", "o3", "o4"], focus=["o1", "o2", "o3", "o4"])
    s.beat("Es importante decirlo con precisión: no existe un estado interrumpido. Una interrupción "
           "se ve como la transición de hablando a escuchando. Los controles dependen del estado: "
           "detener solo al hablar, cerrar en cualquier estado activo, y el orbe cambia de función "
           "según lo que esté pasando.", show=["p", "p.0", "p.1", "p.2"], focus=["o4", "o2"])
    S.append(s)

    s = Scene(8, "Interfaz visual y sincronización", subtitle="sincronización entre hilos")
    s.node("w", "Hilos de trabajo", "conversación · worker de Claude", kind="local", at=(260, 300),
           w=320)
    s.node("idle", "GLib.idle_add", "set_state · add_message · sleep_and_hide", kind="local",
           at=(700, 300), w=340)
    s.node("gtk", "Hilo principal GTK", "único que toca la ventana", kind="ui", at=(1160, 300), w=320)
    s.node("tick", "Temporizador 16 ms", "≈ 60 fps mientras es visible", kind="ui", at=(1600, 300),
           w=300)
    s.node("ml", "mic_level", "dB del micrófono, suavizado", kind="local", at=(700, 560), w=320)
    s.node("vl", "voice_level()", "envolvente del fragmento actual", kind="local", at=(1160, 560),
           w=320)
    s.node("cap", "current_caption()", "fragmento que suena ahora", kind="local", at=(1600, 560),
           w=320)
    for id, a, b, lab, col in [("a", "w", "idle", "eventos", BRASS), ("b", "idle", "gtk", "", ROSE),
                               ("c", "tick", "gtk", "", ROSE), ("d", "gtk", "ml", "lee", MUTED),
                               ("e", "gtk", "vl", "lee", MUTED), ("f", "gtk", "cap", "lee", MUTED)]:
        s.edge(id, a, b, lab, color=col)
    s.add(Panel("p", "", [
        "GTK no es seguro entre hilos: todo cambio de estado se encola con GLib.idle_add.",
        "Los subtítulos se calculan con el reloj: cada fragmento sabe cuándo empieza a oírse (latencia 0,15 s).",
        "Cambio de subtítulo con fundido: 0,18 s de salida y 0,30 s de entrada; respeta “reducir movimiento”.",
        "gtk-layer-shell la fija sobre todas las ventanas en Wayland, sin robar el teclado."],
        (110, 700, 1700, 270), size=20))
    s.beat("GTK no es seguro entre hilos, así que ningún hilo de trabajo toca la ventana. Los cambios "
           "de estado y de texto se encolan con idle add y los ejecuta el hilo principal.",
           show=["w", "idle", "gtk", "a", "b"], flow=[("a", "estado"), "b"])
    s.beat("La animación, en cambio, no recibe eventos: un temporizador de dieciséis milisegundos "
           "dibuja la burbuja y consulta tres valores. El nivel del micrófono, el nivel de la voz según "
           "la envolvente del fragmento que suena, y el subtítulo correspondiente a ese instante.",
           show=["tick", "c", "ml", "vl", "cap", "d", "e", "f"], focus=["vl", "cap"])
    s.beat("Así, voz y subtítulos quedan sincronizados por reloj y no por mensajes. La capa de "
           "superposición de Wayland mantiene la burbuja encima de todo sin capturar el teclado.",
           show=["p", "p.0", "p.1", "p.2", "p.3"])
    S.append(s)

    # ================================================================== 9 INTERRUPTIONS
    S.append(chapter_card(9, "Interrupciones y concurrencia",
                          ["Barge-in por voz", "Qué se cancela y qué no", "Mapa de hilos y procesos"],
                          "Capítulo nueve: interrupciones y concurrencia."))

    s = Scene(9, "Interrupciones y concurrencia", subtitle="hablar encima de Jarvis")
    s.add(Sequence("seq", [("u", "Usuario", "audio"), ("bm", "Monitor de interrupción", "local"),
                           ("sp", "Habla (Kokoro + pw-play)", "audio"), ("wk", "Worker de Claude", "process"),
                           ("cv", "Conversación", "local")], [
        ("m1", "sp", "sp", "Jarvis habla; el monitor lee el mic en otro hilo", "note"),
        ("m2", "bm", "bm", "ignora los primeros 0,3 s (clic, respiración)", ""),
        ("m3", "u", "bm", "voz: VAD > 0,5 durante ≥ 0,3 s", ""),
        ("m4", "bm", "bm", "guarda los últimos ≈ 0,8 s de audio", ""),
        ("m5", "bm", "sp", "stop_speaking(): evento + kill de pw-play", "err"),
        ("m6", "wk", "wk", "Claude NO se cancela: termina en silencio", ""),
        ("m7", "cv", "cv", "estado: escuchando · la cola del mic sigue llenándose", ""),
        ("m8", "cv", "cv", "listen(prefill): continúa sin vaciar la cola", "note")],
        (60, 130, 1800, 620), top=80))
    s.add(Panel("p", "", [
        "Modo “wakeword”: solo interrumpe “Hey Jarvis” (útil con altavoces).  Modo “off”: solo el orbe o ■.",
        "✕ es distinto: end_requested cancela también a Claude (SIGTERM al grupo, 3 s, SIGKILL)."],
        (60, 780, 1800, 190), size=20))
    s.beat("Mientras Jarvis habla, un hilo monitor escucha el micrófono con una segunda instancia de "
           "Silero VAD. Ignora las primeras tres décimas de segundo, para no reaccionar al clic del "
           "altavoz ni a la propia respiración.", show=["seq", "m1", "m2"])
    s.beat("Si detecta voz durante al menos tres décimas de segundo, guarda los últimos ochenta "
           "centésimos de audio, activa la señal de cancelación del habla y mata el proceso pw-play. La "
           "voz se corta de inmediato.", show=["m3", "m4", "m5"], focus=["m5"])
    s.beat("Aquí hay una decisión de diseño importante: la petición de Claude no se cancela. Una "
           "interrupción accidental, una tos, no debe abortar una instalación a medias. Claude termina "
           "en silencio, mientras la cola del micrófono sigue guardando tus palabras.",
           show=["m6", "m7"], focus=["m6"])
    s.beat("Cuando Claude termina, Jarvis retoma la escucha con el audio guardado y sin vaciar la "
           "cola, así que no se pierde ni una palabra. En modo wakeword solo interrumpe la palabra de "
           "activación. Y el botón cerrar es distinto: ese sí cancela a Claude y todo lo que lanzó.",
           show=["m8", "p", "p.0", "p.1"])
    S.append(s)

    s = Scene(9, "Interrupciones y concurrencia", subtitle="mapa de concurrencia")
    s.add(Table("t", ["Actor", "Tipo", "Rol"], [
        ["Hilo principal", "hilo", "bucle GTK: dibuja y atiende clics"],
        ["run / conversación", "hilo", "detección, escucha, turnos; un único consumidor del mic a la vez"],
        ["Lector del mic", "hilo", "pw-record → cola de 500 bloques (descarta el más antiguo)"],
        ["Monitor de interrupción", "hilo", "solo mientras Jarvis habla"],
        ["Worker de Claude + 2 lectores", "hilos", "stdout línea a línea, stderr acotado"],
        ["Productor Edge · espera de Whisper · Timer · MediaWatch", "hilos", "auxiliares de vida corta o periódicos"],
        ["pw-record · pw-play · jarvis_stt · claude · terminal", "procesos", "aislamiento y cancelación"]],
        (60, 150, 1180, 600), widths=[3.6, 1.2, 5], size=18))
    s.add(Panel("p", "Primitivas y riesgos", [
        "Event: end_requested, speak_cancel, manual_wake, ready.",
        "Lock: player_lock (kill frente a Popen), voice_lock (línea de tiempo), RLock de LocalSTT.",
        "Queue: micrófono y oraciones; los generadores sondean cada 0,1 s para poder cancelar.",
        "Riesgo: estado compartido (self.session) entre hilos; se mitiga esperando al worker antes del siguiente turno.",
        "Riesgo: si Jarvis muere a lo bruto, systemd limpia el cgroup entero."],
        (1270, 150, 590, 820), size=19))
    s.beat("Este es el mapa completo de concurrencia. Hay un hilo principal para GTK, un hilo de "
           "conversación que es el único consumidor del micrófono en cada momento, el lector del "
           "micrófono, el monitor de interrupción, y el trabajador de Claude con dos lectores.",
           show=["t", "t.0", "t.1", "t.2", "t.3", "t.4"])
    s.beat("A eso se suman hilos auxiliares y cinco tipos de procesos hijos. La coordinación usa "
           "primitivas sencillas: eventos para cancelar, candados para proteger el reproductor y la "
           "línea de tiempo, y colas. Los generadores consultan la cola cada décima de segundo para "
           "poder abandonar a tiempo.", show=["t.5", "t.6", "p", "p.0", "p.1", "p.2"])
    s.beat("Los riesgos están acotados, pero existen: hay estado compartido, como el identificador de "
           "sesión, que escribe el trabajador; se mitiga esperando a que termine antes del siguiente "
           "turno. Y si el proceso principal muere de forma abrupta, systemd termina todo el grupo de "
           "control, incluidos los hijos.", show=["p.3", "p.4"], focus=["p.3"])
    S.append(s)

    # ================================================================== 10 MEMORY
    S.append(chapter_card(10, "Gestión de conversaciones y memoria",
                          ["Inicio y fin de una conversación", "Reanudación y datos guardados"],
                          "Capítulo diez: gestión de conversaciones y memoria."))

    s = Scene(10, "Gestión de conversaciones y memoria", subtitle="fin de conversación y limpieza")
    s.add(Panel("end", "Una conversación termina cuando…", [
        "…dices una despedida corta: “thank you”, “that's all”, “gracias”, “eso es todo”…",
        "  (≤ 12 palabras y sin verbos de petición: “thanks, now open Steam” NO es despedida)",
        "…pasan 10 s sin voz tras la última respuesta (frase de tiempo agotado).",
        "…pulsas ✕ (también cancela a Claude si estaba trabajando)."],
        (60, 150, 900, 520), size=21))
    s.add(Panel("clean", "_run_conversation(): limpieza", [
        "Reinicia el detector y vacía la cola del micrófono.",
        "Oculta la burbuja y cierra la terminal de actividad.",
        "Programa la descarga de Whisper (60 s).",
        "Si el contexto supera 60 000 tokens: compacta la memoria.",
        "Vuelve a esperar “Hey Jarvis”."],
        (1000, 150, 860, 520), size=21, color=TEAL))
    s.add(Caption("n", "Las despedidas se detectan en local, sin llamar a Claude: rápido y gratis.",
                  (960, 760), size=24, color=BRASS, anchor="tc", width=1600, align="center", box=True))
    s.beat("Una conversación termina de tres formas. Con una despedida corta, que se detecta en local "
           "sin llamar a Claude: debe contener una frase de cierre, tener como máximo doce palabras y "
           "no incluir verbos de petición, para que gracias, ahora abre Steam, no se tome como despedida.",
           show=["end", "end.0", "end.1", "n"])
    s.beat("También termina tras diez segundos sin voz, o con el botón cerrar. Al terminar, una única "
           "rutina hace la limpieza: reinicia el detector, vacía el micrófono, oculta la burbuja, cierra "
           "la terminal, programa la descarga de Whisper, y compacta la memoria si hace falta.",
           show=["end.2", "end.3", "clean", "clean.*"], focus=["clean"])
    S.append(s)

    s = Scene(10, "Gestión de conversaciones y memoria", subtitle="reanudar una conversación")
    s.add(Sequence("seq", [("w", "Activación", "local"), ("m", "memory.json", "storage"),
                           ("cc", "claude -p", "process"), ("t", "Transcripción", "storage")], [
        ("m1", "w", "m", "_resume_session(): leer", ""),
        ("m2", "m", "w", "last_used hace 2 h → session_id", "dash"),
        ("m3", "w", "cc", "--resume <id> + prompt + resumen", ""),
        ("m4", "cc", "t", "carga el historial", ""),
        ("m5", "cc", "w", "result: nuevo tamaño del contexto", "dash"),
        ("m6", "w", "m", "guardar (atómico, 600)", ""),
        ("m7", "w", "w", "> 12 h o sin id → sesión nueva (solo resumen)", "note")],
        (60, 130, 1800, 840), top=90))
    s.beat("Cada activación empieza leyendo memory.json. Si la última sesión se usó hace menos de doce "
           "horas, se reanuda: Claude carga su transcripción y responde con todo el contexto previo.",
           show=["seq", "m1", "m2", "m3", "m4"])
    s.beat("Tras cada petición se guarda el nuevo tamaño del contexto, con escritura atómica mediante "
           "un archivo temporal y un renombrado. Si pasaron más de doce horas, o la sesión fue "
           "compactada, empieza una conversación nueva que solo conoce el resumen.",
           show=["m5", "m6", "m7"], focus=["m7"])
    S.append(s)

    # ================================================================== 11 EXTRAS
    S.append(chapter_card(11, "Funcionalidades adicionales",
                          ["Modo juego", "Terminal por voz", "Idiomas, voces y servicio"],
                          "Capítulo once: funcionalidades adicionales."))

    s = Scene(11, "Funcionalidades adicionales", subtitle="modo juego")
    s.node("u", "“turn on gaming mode”", "petición normal", kind="audio", at=(240, 300), w=320)
    s.node("cc", "Claude Code", "el prompt explica cómo", kind="process", at=(700, 300), w=300)
    s.node("f", "gaming_mode", "touch / rm del archivo", kind="storage", at=(1150, 300), w=300)
    s.node("stt", "LocalSTT.wanted()", "compara la especificación", kind="local", at=(1150, 580), w=320)
    s.node("cpu", "Whisper small · CPU · int8", "≈ 0,7 GB RAM · ≈ 1 s por frase", kind="process",
           at=(1650, 470), w=360)
    s.node("gpu", "Whisper large-v3-turbo · GPU", "se detiene en cuanto termina la conversación",
           kind="process", at=(1650, 700), w=360)
    for id, a, b, lab, col in [("a", "u", "cc", "", GLACIER), ("b", "cc", "f", "Bash", ORANGE),
                               ("c", "f", "stt", "existe", TEAL), ("d", "stt", "cpu", "", BRASS),
                               ("e", "stt", "gpu", "", MUTED)]:
        s.edge(id, a, b, lab, color=col)
    s.add(Panel("p", "", [
        "El interruptor es un archivo: lo entienden Jarvis, Claude y el propio usuario (touch / rm).",
        "Si cambia la especificación, el proceso de Whisper se reinicia con la nueva."],
        (110, 800, 1700, 170), size=20))
    s.beat("El modo juego deja la tarjeta gráfica entera a los juegos. El usuario lo pide en lenguaje "
           "natural; el prompt de sistema le explica a Claude que basta con crear o borrar un archivo.",
           show=["u", "cc", "f", "a", "b"], flow=[("a", "voz"), ("b", "touch")])
    s.beat("Cuando el archivo existe, la transcripción usa el modelo pequeño en el procesador. Si la "
           "especificación cambia, el proceso de Whisper se reinicia, y si quedaba un modelo en la "
           "gráfica, se descarga inmediatamente al terminar la conversación.",
           show=["stt", "cpu", "gpu", "c", "d", "e", "p", "p.0", "p.1"], flow=["c", "d"])
    S.append(s)

    s = Scene(11, "Funcionalidades adicionales", subtitle="terminal por voz, idiomas, voces y servicio")
    s.add(Table("t", ["Función", "Cómo funciona"], [
        ["“deactivate / activate terminal”", "se quitan muletillas (okay, wait, can you, please…); si quedan ≤ 4 palabras y "
         "coincide el patrón, se escribe on/off en activity_terminal sin llamar a Claude"],
        ["Otras formas de decirlo", "llegan a Claude, cuyo prompt explica el archivo; Jarvis cierra la ventana al terminar"],
        ["Idioma de respuesta", "“auto” = el del usuario, o fijo (p. ej. English)"],
        ["Modo tutor", "si hablas en el idioma tutor, primero te dice cómo se diría en el idioma de respuesta"],
        ["Voces", "Kokoro: voz o mezcla con “+”, velocidad, tono (deepen), idioma; Edge: voz de respaldo"],
        ["Despedidas", "listas en inglés y español; ver capítulo 10"],
        ["Servicio", "systemctl --user restart | stop jarvis · journalctl · despertar con SIGUSR1 (--kill-whom=main)"]],
        (60, 160, 1800, 800), widths=[2.6, 7], size=20))
    s.beat("El interruptor de la terminal se resuelve en local: se eliminan muletillas, y si lo que "
           "queda es una orden corta que coincide con el patrón, se escribe encendido o apagado en un "
           "archivo, sin llamar a Claude. Cualquier otra forma de decirlo la entiende Claude gracias "
           "al prompt.", show=["t", "t.0", "t.1"], focus=["t.0"])
    s.beat("En idiomas, Jarvis puede responder en el idioma del usuario o en uno fijo, y tiene un modo "
           "tutor para practicar: si hablas en tu idioma nativo, primero te dice cómo se diría en el "
           "idioma que estás aprendiendo.", show=["t.2", "t.3"])
    s.beat("Las voces se configuran por archivo, incluida la mezcla, la velocidad y el tono. Y el "
           "servicio se controla con systemctl. Para despertarlo con un atajo de teclado se envía la "
           "señal SIGUSR1 solo al proceso principal; sin esa precaución, la señal también mataría a "
           "pw-record.", show=["t.4", "t.5", "t.6"], focus=["t.6"])
    S.append(s)

    # ================================================================== 12 FAILURES
    S.append(chapter_card(12, "Manejo de errores y escenarios de fallo",
                          ["Entrada: activación, micrófono, transcripción",
                           "Salida: Claude, voz, comandos"],
                          "Capítulo doce: errores y escenarios de fallo. Solo mecanismos que existen "
                          "en el código."))

    s = Scene(12, "Manejo de errores", subtitle="lado de entrada")
    s.add(Table("t", ["Fallo", "Detección", "Recuperación real"], [
        ["No se detecta la palabra", "nada (o “Near miss” en el registro)", "ajustar umbral / patience; despertar con clic o SIGUSR1"],
        ["Falsa activación", "saludo sin petición", "10 s de silencio → vuelve a dormir; no se llama a Claude"],
        ["Micrófono muerto", "pw-record cierra la tubería", "os._exit(1) → systemd reinicia en 5 s"],
        ["Whisper local no carga", "línea {error} o 120 s sin “ready”", "Groq si hay clave; si no, mensaje hablado"],
        ["Whisper no responde", "60 s sin respuesta (select)", "se mata el proceso; respaldo o mensaje; se relanza en el próximo uso"],
        ["Groq falla", "error HTTP o 30 s", "“Sorry, I couldn't hear you well” y se vuelve a escuchar (sin reintento)"],
        ["Alucinación de Whisper", "lista de frases típicas", "se descarta: “Can you repeat it?”"]],
        (60, 160, 1800, 800), widths=[2.4, 3, 4.6], size=19))
    s.beat("Empecemos por la entrada. Si la palabra no se detecta, el registro de casi activaciones "
           "permite calibrar, y siempre se puede despertar con un clic o con la señal manual. Una falsa "
           "activación se agota sola tras diez segundos de silencio.", show=["t", "t.0", "t.1"])
    s.beat("Si el micrófono deja de enviar audio, el proceso termina a propósito y systemd lo reinicia. "
           "Es una estrategia de dejar que falle y reiniciar limpio, en lugar de intentar reparar el "
           "estado interno.", show=["t.2"], focus=["t.2"])
    s.beat("Si Whisper local no carga, o no responde en sesenta segundos, se descarta el proceso y se "
           "recurre a Groq si hay una clave. Si Groq falla, Jarvis pide repetir y vuelve a escuchar, sin "
           "reintentos automáticos. Y las alucinaciones típicas sobre ruido se descartan.",
           show=["t.3", "t.4", "t.5", "t.6"])
    S.append(s)

    s = Scene(12, "Manejo de errores", subtitle="lado de salida")
    s.add(Table("t", ["Fallo", "Detección", "Recuperación real"], [
        ["Claude sin sesión iniciada", "salida no JSON que menciona “login”", "dice: “run claude auth login in a terminal”"],
        ["Salida inesperada", "no llega evento result", "“I had a problem talking to Claude”"],
        ["Claude tarda > 300 s", "plazo vencido", "SIGTERM al grupo → 3 s → SIGKILL; aviso hablado"],
        ["El usuario cancela (✕)", "end_requested", "mismo cierre del grupo; sin procesos zombi (waitid + wait)"],
        ["Kokoro falla", "excepción en la síntesis", "Edge TTS para las oraciones restantes"],
        ["Edge falla", "2 intentos por oración", "se omite esa oración"],
        ["Un comando falla", "tool_result con is_error", "en rojo en la terminal; Claude decide y lo explica"],
        ["Excepción inesperada", "try/except del turno", "“Something went wrong. I'll wait for you.” → dormir"],
        ["La compactación falla", "resultado vacío o error", "se conserva la sesión tal cual"]],
        (60, 160, 1800, 810), widths=[2.4, 2.8, 4.8], size=18))
    s.beat("En la salida, si Claude no tiene sesión iniciada, la salida no es JSON y menciona el login; "
           "Jarvis lo detecta y dice qué comando ejecutar. Cualquier otra salida inesperada produce un "
           "mensaje genérico, sin quedarse colgado.", show=["t", "t.0", "t.1"])
    s.beat("Si Claude supera los trescientos segundos, o el usuario cancela, se envía una señal de "
           "terminación a todo el grupo de procesos, se esperan tres segundos y se fuerza el cierre. "
           "Se usa una espera que no recoge el proceso hasta matar el grupo, para que su identificador "
           "no pueda reutilizarse, y después se recoge para no dejar zombis.",
           show=["t.2", "t.3"], focus=["t.3"])
    s.beat("En la voz, Kokoro tiene a Edge como respaldo. Si un comando falla, el error aparece en rojo "
           "en la terminal y Claude decide cómo informarlo. Y cualquier excepción no prevista en un "
           "turno se captura: Jarvis se disculpa y vuelve a dormir, en lugar de dejar el servicio en un "
           "estado inconsistente.", show=["t.4", "t.5", "t.6", "t.7", "t.8"])
    S.append(s)

    # ================================================================== 13 ANALYSIS
    S.append(chapter_card(13, "Análisis arquitectónico y decisiones de ingeniería",
                          ["Fortalezas", "Compromisos y alternativas", "Límites y deuda técnica"],
                          "Capítulo trece: análisis arquitectónico. Las decisiones actuales no son "
                          "necesariamente las correctas; veamos sus compromisos."))

    s = Scene(13, "Análisis arquitectónico", subtitle="fortalezas")
    s.add(Panel("p", "Lo que la arquitectura hace bien", [
        "Reutiliza un agente maduro (Claude Code) en lugar de reimplementar herramientas y permisos.",
        "Aislamiento por procesos: VRAM liberable, cancelación limpia por grupo, fallos contenidos.",
        "Latencia percibida baja: carga de Whisper oculta tras el saludo, streaming por oraciones.",
        "Recursos medidos, no supuestos: ≈ 1 % de CPU y 0 MB de VRAM en reposo; ~11k tokens de base.",
        "Transparencia: terminal de actividad, registros de casi activaciones, consumo por petición.",
        "Degradación elegante: Groq, Edge, reinicio por systemd, mensajes hablados ante cada error."],
        (110, 160, 1700, 800), size=24))
    s.beat("Como fortalezas, primero: no reinventa el agente. Reutilizar Claude Code aporta "
           "herramientas, permisos, sesiones y transcripciones probadas. Segundo, el aislamiento por "
           "procesos, que hace posible liberar la memoria de vídeo y cancelar de forma limpia.",
           show=["p", "p.0", "p.1"])
    s.beat("Tercero, una latencia percibida baja gracias a ocultar la carga del modelo y al streaming. "
           "Cuarto, decisiones basadas en mediciones. Y quinto, transparencia y degradación elegante: "
           "casi todos los fallos tienen un respaldo o, al menos, un mensaje hablado.",
           show=["p.2", "p.3", "p.4", "p.5"])
    S.append(s)

    s = Scene(13, "Análisis arquitectónico", subtitle="compromisos y alternativas")
    s.add(Table("t", ["Decisión", "Ventaja", "Coste", "Alternativa"], [
        ["CLI de Claude Code por petición", "agente completo y permisos", "arranque de proceso; acoplado al formato stream-json", "Agent SDK con sesión persistente"],
        ["Whisper en proceso hijo", "VRAM a cero en reposo", "3-6 s de carga (oculta) en cada activación", "servidor STT persistente"],
        ["Hilos + Event", "simple y legible", "estado compartido, sondeo cada 0,1 s", "asyncio o actores"],
        ["Un archivo jarvis.py (~1 700 líneas)", "fácil de desplegar", "mantenibilidad y pruebas", "módulos: audio, stt, claude, tts"],
        ["Sondeo de playerctl", "trivial", "proceso cada 1,5 s", "señales D-Bus de MPRIS"],
        ["Seguridad por clasificador + prompt", "sin fricción", "sin aislamiento real", "sandbox (bubblewrap) o lista blanca"]],
        (40, 160, 1840, 800), widths=[2.6, 2.2, 3, 2.6], size=18))
    s.beat("Ahora los compromisos. Usar el binario de Claude Code por petición da un agente completo, "
           "pero cuesta un arranque de proceso en cada turno y acopla Jarvis al formato de eventos de la "
           "CLI. Una alternativa sería el Agent SDK con una sesión persistente.",
           show=["t", "t.0"], focus=["t.0"])
    s.beat("Whisper en proceso hijo libera la gráfica, a cambio de una carga en cada activación que "
           "hoy se oculta tras el saludo. Los hilos con eventos son simples, pero dejan estado "
           "compartido; asyncio o un modelo de actores lo harían más explícito.",
           show=["t.1", "t.2"])
    s.beat("Un único archivo de unas mil setecientas líneas es fácil de desplegar, pero es la "
           "principal deuda de mantenibilidad. El sondeo de playerctl podría sustituirse por señales de "
           "D-Bus. Y la seguridad sin aislamiento real podría reforzarse con un sandbox o una lista "
           "blanca de comandos, a costa de fricción.", show=["t.3", "t.4", "t.5"], focus=["t.5"])
    S.append(s)

    s = Scene(13, "Análisis arquitectónico", subtitle="límites, escalabilidad y deuda técnica")
    s.add(Panel("lim", "Límites y escalabilidad", [
        "Diseñado para un usuario y una máquina: no hay concurrencia entre conversaciones.",
        "Dependencias de plataforma: Linux con PipeWire y systemd; probado en Pop!_OS + COSMIC.",
        "Palabra de activación solo en inglés, modelo no comercial.",
        "La continuidad depende del formato de sesiones de Claude Code (--resume, prompt congelado)."],
        (60, 160, 900, 700), size=21, color=VIOLET))
    s.add(Panel("debt", "Deuda técnica visible", [
        "Archivo principal monolítico; configuración duplicada (DEFAULTS y config.example.toml).",
        "Pruebas automáticas solo para funciones puras (59 pruebas); los flujos de audio se prueban a mano.",
        "Precios por token codificados en el benchmark.",
        "Caminos de respaldo (Groq, Edge, otras terminales) sin verificación reciente."],
        (1000, 160, 860, 700), size=21, color=RED))
    s.beat("En límites: es un sistema para un usuario y una máquina, dependiente de PipeWire y "
           "systemd, con la activación solo en inglés, y cuya continuidad depende del formato de "
           "sesiones de Claude Code.", show=["lim", "lim.*"])
    s.beat("En deuda técnica: el archivo monolítico, la configuración duplicada entre código y "
           "ejemplo, pruebas automáticas que cubren solo funciones puras, y caminos de respaldo que "
           "existen pero no se han verificado recientemente. Ninguno es crítico, pero conviene "
           "conocerlos antes de crecer.", show=["debt", "debt.*"])
    S.append(s)

    s = Scene("Cierre", "Conclusiones", kind="card")
    s.legend = False
    s.add(Orb("orb", "speaking", (960, 280), scale=1.4))
    pts = ["Jarvis = capa de voz + ciclo de vida alrededor de un agente existente.",
           "Procesos para aislar recursos y cancelar; hilos y colas para coordinar.",
           "Streaming de extremo a extremo: la primera oración marca la latencia.",
           "Memoria en dos capas: transcripción de Claude + puntero y resumen propios.",
           "Seguridad por capas útil, pero sin aislamiento real del sistema."]
    for i, p in enumerate(pts):
        s.add(Caption(f"c{i}", p, (960, 470 + i * 70), size=27, anchor="tc", width=1600,
                      align="center", color=TEXT if i % 2 == 0 else hexrgb("#FFF3D6")))
    s.beat("Para cerrar. Jarvis es, en esencia, una capa de voz y de gestión del ciclo de vida "
           "alrededor de un agente existente. Usa procesos para aislar recursos y poder cancelar, e "
           "hilos con colas para coordinar.", show=["orb", "c0", "c1"])
    s.beat("El streaming de extremo a extremo hace que la latencia percibida sea la de la primera "
           "oración. La memoria combina la transcripción de Claude Code con un puntero y un resumen "
           "propios. Y la seguridad funciona por capas, aunque sin aislamiento real del sistema.",
           show=["c2", "c3", "c4"])
    s.beat("Con esto deberías poder imaginar el recorrido completo: de una palabra en el aire, a un "
           "comando en tu sistema, y de vuelta a una voz. Gracias por acompañar esta revisión.",
           pause=1.5)
    S.append(s)
    return S
