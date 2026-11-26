# Jarvis — storyboard del video de arquitectura

Generado automáticamente desde `video/scenes.py` (la misma fuente que dibuja el video), así que el storyboard y el video no pueden diferir.

Duración total: **31 min 24 s** · 55 escenas · voz Kokoro `em_alex` (español).

## Tabla de contenidos

- `00:00` — **Intro** · Jarvis Voice Assistant
- `01:44` — **1** · Visión general de la arquitectura
- `04:57` — **2** · Inicio y ciclo de vida
- `08:13` — **3** · Detección de activación y captura de audio
- `10:30` — **4** · Speech-to-Text
- `12:54` — **5** · Orquestación e integración con Claude Code
- `17:33` — **6** · Ejecución de acciones y seguridad
- `19:56` — **7** · Text-to-Speech
- `21:44` — **8** · Interfaz visual y sincronización
- `22:59` — **9** · Interrupciones y concurrencia
- `24:50` — **10** · Gestión de conversaciones y memoria
- `25:53` — **11** · Funcionalidades adicionales
- `27:08` — **12** · Manejo de errores y escenarios de fallo
- `28:48` — **13** · Análisis arquitectónico y decisiones de ingeniería
- `30:45` — **Cierre** · Conclusiones


## Intro · Jarvis Voice Assistant

### Escena 1: Jarvis Voice Assistant  (`00:00`, 34 s)

1. *[muestra t, st, orb]* — Bienvenidos a esta revisión técnica de Jarvis Voice Assistant, un asistente de voz para Linux que escucha una palabra de activación, entiende lo que le pides y delega la ejecución en Claude Code, que actúa directamente sobre el sistema operativo.
2. *[muestra src]* — No vamos a leer código línea por línea. Vamos a recorrer la arquitectura como en una revisión de ingeniería: qué componentes existen, cómo se comunican, qué ocurre en paralelo, cómo se recupera de los fallos, y qué decisiones de diseño hay detrás. Todo lo que veremos fue contrastado con el código fuente, no solo con la documentación.

### Escena 2: 13 capítulos  (`00:34`, 29 s)

1. *[muestra c0, c1, c2, c3, c4, c5, c6]* — Este es el recorrido. Empezamos con la vista general y el ciclo de vida del servicio. Después seguimos el camino de una petición: la activación, la transcripción, la orquestación con Claude Code, la ejecución de comandos y la voz de respuesta.
2. *[muestra c7, c8, c9, c10, c11, c12]* — Luego vemos la interfaz, la concurrencia y las interrupciones, la memoria entre conversaciones, las funciones adicionales, el manejo de errores, y cerramos con un análisis crítico de la arquitectura, sus compromisos y sus alternativas.

### Escena 3: cómo leer los diagramas  (`01:02`, 41 s)

**Componentes:** JARVIS (PYTHON): Jarvis (Python), Origen; SUBPROCESO: Subproceso local, Destino; MODELO LOCAL: Modelo local; SERVICIO EXTERNO: Servicio externo; ARCHIVO: Persistencia; COMANDO / SO: Comandos / SO; AUDIO E/S: Audio E/S; INTERFAZ: Interfaz

1. *[muestra k0, k1, k2]* — Antes de empezar, el código visual. Cada tipo de componente tiene siempre el mismo color y la misma forma. Dorado es código de Jarvis en Python. Beige, procesos hijos locales. Verde, modelos de inteligencia artificial que corren en tu propio equipo.
2. *[muestra k3, k4, k5, k6, k7]* — Violeta con borde punteado son servicios externos en Internet. Turquesa con forma de cilindro es persistencia en disco. Naranja, comandos que se ejecutan en el sistema operativo. Azul claro, entrada y salida de audio. Y rosa, la interfaz visual.
3. *[muestra a, b, ab; flujo ab (datos)]* — Las flechas indican la dirección del flujo de información, y los puntos luminosos que viajan por ellas representan datos en movimiento en ese preciso momento.


## 1 · Visión general de la arquitectura

### Escena 4: Visión general de la arquitectura  (`01:44`, 4 s)

1. *[muestra num, title, p0, p1, p2]* — Capítulo uno: visión general de la arquitectura.

### Escena 5: el problema  (`01:47`, 46 s)

**Componentes:** AUDIO E/S: Tu voz, Voz de respuesta; MODELO LOCAL: Texto; SUBPROCESO: Claude Code; COMANDO / SO: Linux

1. *[muestra v, t, c, o, r, vt, tc, co, or; flujo vt, tc, co, or]* — ¿Qué problema resuelve Jarvis? Convertir una frase hablada en acciones reales sobre el ordenador. El usuario dice Hey Jarvis, formula una petición, y recibe una respuesta hablada después de que el sistema haya hecho el trabajo.
2. *[muestra why, why.0, why.1; resalta c]* — La idea clave es que Jarvis no implementa un agente propio. Es una capa de voz alrededor de Claude Code, que ya sabe ejecutar comandos, leer archivos y razonar sobre los resultados. Jarvis aporta todo lo que rodea a esa capacidad: oído, voz, interfaz, memoria y control del ciclo de vida.
3. *[muestra why.2, why.3]* — Dos requisitos no funcionales marcan muchas decisiones: privacidad, porque nada sale del equipo antes de la palabra de activación, y consumo de recursos, porque la máquina se comparte con juegos que necesitan toda la memoria de la tarjeta gráfica.

### Escena 6: diagrama de componentes  (`02:33`, 78 s)

**Visual:** Diagrama general: proceso jarvis.py con sus módulos internos, subprocesos y servicios.

**Componentes:** actor: Usuario; AUDIO E/S: pw-record, pw-play; MODELO LOCAL: openWakeWord, Silero VAD, Kokoro TTS; JARVIS (PYTHON): Assistant, ActivityConsole; INTERFAZ: Burbuja GTK; SUBPROCESO: jarvis_stt.py, claude -p, Terminal; SERVICIO EXTERNO: Groq Whisper API, API de Anthropic, Edge TTS; COMANDO / SO: Bash · archivos · web

1. *[muestra core, orch; resalta orch]* — Este es el sistema completo. En el centro está un único proceso de Python, jarvis.py, que corre como servicio de usuario de systemd. Dentro vive el orquestador, la clase Assistant, que actúa como una máquina de estados conversacional.
2. *[muestra user, rec, e1, e2, wake, vad, e3, e4; flujo e1 (voz), e2 (PCM); resalta wake, vad]* — El audio entra por pw-record, el cliente de PipeWire, que entrega bloques de ochenta milisegundos. Sobre ese flujo trabajan dos modelos locales pequeños: openWakeWord, que busca la palabra de activación, y Silero VAD, que distingue voz humana de ruido.
3. *[muestra stt, groq, e5, e6, cc, anth, bash, e7, e8, e9; flujo e5 (audio), e7 (texto), e9 (cmd); resalta cc]* — La transcripción ocurre fuera del proceso principal: en un proceso hijo con faster-whisper, o en la API de Groq como alternativa. Y la inteligencia está en otro proceso hijo: el comando claude, que habla con la API de Anthropic y ejecuta herramientas como Bash.
4. *[muestra tts, play, ui, act, edge, term, e10, e11, e12, e13, e14, e15, e16; flujo e10 (texto), e11 (voz), e12 (voz), e15 (log)]* — La respuesta vuelve al orquestador, que la convierte en voz con Kokoro, también local, y la reproduce con pw-play. Edge TTS es un respaldo en línea. En paralelo, el orquestador actualiza la burbuja visual y registra los comandos que Claude ejecuta en una terminal de actividad.
5. *[resalta stt, cc, rec, play]* — Fíjate en el patrón: un proceso principal ligero que coordina, y trabajo pesado o privilegiado aislado en procesos hijos. Esa separación explica gran parte del comportamiento de recursos, de cancelación y de fallos que veremos después.

### Escena 7: persistencia y dependencias  (`03:51`, 66 s)

**Componentes:** ARCHIVO: config.toml, groq_key, memory.json, jarvis.log · activity.log, gaming_mode · activity_terminal, ~/.claude/projects, ~/.local/share/jarvis/models

1. *[muestra cfg, key, mem; resalta mem]* — La persistencia es deliberadamente simple: archivos planos. La configuración en TOML, la clave de Groq con permisos seiscientos, y memory.json, que guarda solo el identificador de la sesión de Claude y un resumen, también con permisos restringidos.
2. *[muestra logs, flags, cct, models; resalta cct]* — Los registros y dos interruptores viven en el directorio de estado: el modo juego y la terminal de actividad son simplemente archivos cuya existencia o contenido cambia el comportamiento. Las transcripciones completas de cada conversación no las guarda Jarvis: las guarda Claude Code en su propio directorio.
3. *[muestra deps, deps.0, deps.1, deps.2]* — En dependencias destacan tres detalles. openWakeWord se instala sin dependencias, porque su metadato exige tflite, que no existe para Python reciente. Las librerías de CUDA llegan por pip, sin instalar CUDA en el sistema. Y el entorno virtual reutiliza los enlaces de GTK del sistema.
4. *[muestra deps.3, deps.4]* — Del sistema se necesita PipeWire, systemd y GTK tres. Y como servicios externos: Claude Code autenticado con una suscripción o una API, Groq si se elige transcripción en línea, y Edge TTS como voz de respaldo.


## 2 · Inicio y ciclo de vida

### Escena 8: Inicio y ciclo de vida  (`04:57`, 4 s)

1. *[muestra num, title, p0, p1, p2]* — Capítulo dos: inicio y ciclo de vida de la aplicación.

### Escena 9: install.sh  (`05:01`, 49 s)

**Componentes:** JARVIS (PYTHON): Comprobaciones, Entorno virtual, Paquetes pip, Modelos; ARCHIVO: Copia de archivos, Configuración, Clave de Groq; SUBPROCESO: Claude Code, Servicio

1. *[muestra i1, i2, i3, x0, x1; resalta i1]* — La instalación es por usuario y no necesita sudo para Jarvis. El script comprueba los requisitos del sistema y, si falta algo, imprime el comando exacto para Debian, Fedora o Arch. Solo la variante de Pop OS ha sido probada en la práctica; las demás están documentadas pero no verificadas.
2. *[muestra i4, i5, x2, x3]* — Después crea el entorno virtual, instala los paquetes y descarga los modelos: la palabra de activación, la voz de Kokoro y, si se eligió transcripción local, los modelos de Whisper junto con las librerías de CUDA cuando detecta una tarjeta NVIDIA.
3. *[muestra i6, i7, i8, i9, x4, x5, x6, x7; resalta i9]* — En una instalación nueva pregunta cómo transcribir: en local o con Groq. Si es Groq, pide la clave sin mostrarla y la guarda con una máscara de permisos restrictiva. Por último localiza el binario de Claude Code, instala la unidad de systemd y arranca el servicio.

### Escena 10: arranque del servicio  (`05:50`, 58 s)

1. *[muestra seq, m1; resalta m1]* — Veamos el arranque. La unidad de systemd depende de la sesión gráfica y de PipeWire, define el PATH donde suele vivir el binario de Claude, y se reinicia sola si el proceso termina con error, tras cinco segundos.
2. *[muestra m2, m3]* — main configura el registro y toma un candado de archivo para garantizar una sola instancia. La configuración se carga fusionando el TOML del usuario sobre los valores por defecto definidos en el propio código.
3. *[muestra m4, m5, m6; resalta m6]* — El constructor de Assistant hace el trabajo caro una sola vez: carga el modelo de activación, dos instancias independientes de Silero VAD, arranca pw-record con su hilo lector, y carga Kokoro sintetizando una palabra de prueba para que la primera respuesta real no pague ese coste.
4. *[muestra m7, m8, m9, m10, m11; resalta m11]* — Se registra la señal SIGUSR1 como despertador manual, se crea la burbuja oculta, se lanza el hilo run, que es el bucle de detección, y el hilo principal entra en el bucle de eventos de GTK. Desde aquí, Jarvis está esperando.

### Escena 11: en reposo: procesos, hilos y recursos  (`06:47`, 46 s)

1. *[muestra lanes, a1, a2, a3, a5]* — En reposo hay pocos actores. El hilo principal de GTK atiende eventos. El hilo run toma cada bloque de audio y se lo pasa a openWakeWord. Un hilo lector separado vacía la tubería de pw-record hacia una cola acotada.
2. *[muestra a4, res, res.0, res.1, res.2]* — Si está configurado el umbral para medios, un cuarto hilo consulta cada segundo y medio si algún reproductor está sonando. El resultado medido: alrededor de un uno por ciento de procesador, quinientos cincuenta megas de RAM, y cero de memoria de vídeo.
3. *[muestra why, why.0, why.1, why.2]* — Ese cero no es casualidad: Whisper solo se carga al despertar. Y dos decisiones de robustez: la cola nunca bloquea al lector porque descarta lo más antiguo, y si el micrófono deja de enviar audio, el proceso termina a propósito para que systemd lo reinicie limpio.

### Escena 12: estados del sistema  (`07:33`, 40 s)

**Componentes:** JARVIS (PYTHON): DORMIDO, SALUDO, ESCUCHANDO, TRANSCRIBIENDO, CLAUDE TRABAJA, CIERRE; AUDIO E/S: HABLANDO

1. *[muestra sleep, greet, t1; flujo t1; resalta sleep]* — A nivel de sistema, Jarvis es una máquina de estados. Dormido, solo corre la detección. La palabra de activación, o la señal manual, lo llevan al saludo: un sonido y una frase.
2. *[muestra listen, stt, claude, speak, t2, t3, t4, t5, t10; flujo t3, t4, t5; resalta claude]* — Después escucha, transcribe, y si la frase parece inacabada vuelve a escuchar. Con el texto completo, Claude trabaja, y en cuanto existe la primera oración completa Jarvis empieza a hablar, mientras Claude todavía escribe el resto.
3. *[muestra end, t6, t7, t8, t9; flujo t6, t9; resalta end]* — Al terminar de hablar vuelve a escuchar, sin necesidad de repetir la palabra de activación. La conversación termina con una despedida, con diez segundos de silencio o con el botón de cerrar, y pasa por una fase de cierre antes de volver a dormir.


## 3 · Detección de activación y captura de audio

### Escena 13: Detección de activación y captura de audio  (`08:13`, 4 s)

1. *[muestra num, title, p0, p1, p2]* — Capítulo tres: detección de activación y captura de audio.

### Escena 14: ¿es realmente “Hey Jarvis”?  (`08:17`, 54 s)

1. *[muestra real]* — openWakeWord devuelve un puntaje entre cero y uno por cada bloque de ochenta milisegundos. Un Hey Jarvis real produce una meseta: varios bloques seguidos por encima del umbral.
2. *[muestra tv, rules, rules.0; resalta rules.0]* — Una voz parecida en una serie suele producir un pico aislado. Por eso la regla no es superar el umbral una vez, sino mantenerlo durante dos bloques consecutivos. A eso se le llama patience.
3. *[muestra rules.1, rules.2]* — Además, si algún reproductor informa que está sonando, el umbral sube de cero coma cinco a cero coma ocho. Y todo pico por encima de cero coma tres que no despierta queda registrado como casi activación, para ajustar los umbrales con datos reales en lugar de adivinar.
4. *[muestra rules.3; resalta rules.3]* — Un detalle de ingeniería: la librería ofrece su propio parámetro patience, pero al probarlo con audio sintético nunca disparaba, porque guarda en su historial los puntajes ya anulados. Por eso Jarvis cuenta los bloques consecutivos por su cuenta.

### Escena 15: escuchar hasta que termines  (`09:11`, 47 s)

1. *[muestra vad, r1, tbl, tbl.0, tbl.1]* — Tras el saludo, Silero VAD decide si cada bloque contiene voz humana. Mientras nadie habla, Jarvis espera hasta diez segundos. La grabación empieza tras dieciséis centésimas de segundo de voz, e incluye casi medio segundo de audio previo para no perder la primera sílaba.
2. *[muestra r2, r3, tbl.2, tbl.3, tbl.4; resalta r3]* — Durante la grabación se acumula el silencio. Dos segundos seguidos sin voz marcan el fin de la frase, y hay un tope de sesenta segundos. Si en total hubo menos de tres décimas de segundo de voz, se considera ruido y se sigue esperando.
3. *[muestra tbl.5; resalta tbl.5]* — Las pausas para pensar tienen un tratamiento específico. Después de transcribir, si la frase termina en puntos suspensivos, en coma, o en palabras como y, porque, and, because o um, Jarvis escucha cuatro segundos más y concatena el resto antes de enviar nada a Claude.

### Escena 16: defensa en capas contra falsas activaciones  (`09:58`, 31 s)

**Componentes:** AUDIO E/S: Audio del entorno; MODELO LOCAL: Umbral 0,5, patience = 2; JARVIS (PYTHON): Umbral de medios 0,8, Saludo + escucha

1. *[muestra mic, l1, l2, l3, l4, d0, d1, d2, d3; flujo d0 (audio), d1, d2, d3]* — Visto como sistema, la protección contra activaciones accidentales es una defensa en capas: umbral, persistencia del puntaje, umbral reforzado con medios activos, y finalmente el propio diálogo: una falsa activación solo produce un saludo, y si nadie habla, Jarvis vuelve a dormir sin llamar a Claude.
2. *[muestra p, p.0, p.1, p.2, p.3]* — También hay límites. El modelo es solo en inglés y de licencia no comercial. Mientras dura una conversación la palabra no se busca. Y un verificador entrenado con la voz del usuario está en el plan, pero no implementado.


## 4 · Speech-to-Text

### Escena 17: Speech-to-Text  (`10:30`, 3 s)

1. *[muestra num, title, p0, p1, p2]* — Capítulo cuatro: de audio a texto.

### Escena 18: dos mecanismos  (`10:33`, 51 s)

1. *[muestra cmp, cmp.0, cmp.1]* — Jarvis tiene dos formas de transcribir. La local usa faster-whisper en un proceso hijo, sobre la tarjeta gráfica si existe. La alternativa en línea usa la API de Whisper de Groq. Se elige en la instalación, con el ajuste engine de la sección stt.
2. *[muestra cmp.2, cmp.3; resalta cmp.2]* — La diferencia de privacidad es clara: en local el audio nunca sale del equipo. Con Groq, sale, pero solo después de la palabra de activación. En latencia, la versión local tarda un cuarto de segundo por frase en la gráfica, y alrededor de un segundo con el modelo pequeño en procesador.
3. *[muestra cmp.4, cmp.5, cmp.6; resalta cmp.4]* — El coste local es memoria: alrededor de un giga y tres de VRAM y casi dos de RAM mientras el modelo está cargado. Y ambos caminos se combinan: si la transcripción local falla y existe una clave de Groq, se usa Groq como respaldo. El modo Groq, en este equipo, está implementado pero no fue verificado recientemente.

### Escena 19: ciclo de vida del proceso de Whisper  (`11:24`, 61 s)

1. *[muestra seq]* — ¿Por qué un proceso hijo? Porque la única forma de devolver toda la memoria de la gráfica, incluido el contexto de CUDA, es terminar el proceso que la usa. El proceso principal nunca importa CUDA.
2. *[muestra m1, m2, m3, m4; resalta m3]* — Al despertar, Jarvis lanza el proceso de Whisper mientras suena el saludo, así que los tres a seis segundos de carga quedan ocultos detrás de la conversación. El hijo precarga las librerías de CUDA, carga el modelo en int8, lo calienta, y anuncia que está listo con una línea JSON.
3. *[muestra m5, m6, m7]* — El protocolo es mínimo: una cabecera JSON con el número de muestras, seguida de las muestras en float32 por la entrada estándar, y una línea JSON de respuesta por la salida estándar. Si no hay respuesta en sesenta segundos, el proceso se descarta.
4. *[muestra m8, m9, m10; resalta m10]* — Al terminar la conversación se programa la descarga a los sesenta segundos. Basta cerrar la entrada estándar: el hijo sale de su bucle y termina, y la memoria de vídeo vuelve a cero. Si se habla de nuevo antes, el temporizador se cancela y el modelo sigue cargado.

### Escena 20: memoria de vídeo a lo largo del tiempo  (`12:24`, 30 s)

1. *[muestra v, g1, g2, g3, g4, g5]* — El resultado, en el tiempo: cero megas mientras Jarvis duerme, carga durante el saludo, un giga y tres durante la conversación, sesenta segundos de gracia, y de nuevo cero. Es un compromiso explícito entre latencia del primer turno y memoria disponible para otras aplicaciones.
2. *[muestra p, p.0, p.1, p.2]* — Dos detalles más del texto resultante: se descartan frases que Whisper alucina sobre ruido, como créditos de subtítulos, y el camino de Groq usa temperatura cero y un tiempo límite de treinta segundos.


## 5 · Orquestación e integración con Claude Code

### Escena 21: Orquestación e integración con Claude Code  (`12:54`, 5 s)

1. *[muestra num, title, p0, p1, p2]* — Capítulo cinco, el corazón del sistema: la orquestación con Claude Code.

### Escena 22: división de responsabilidades  (`12:59`, 28 s)

1. *[muestra j, j.0, j.1, j.2, j.3, j.4]* — Conviene separar responsabilidades con precisión. Jarvis es el orquestador: oye, habla, gestiona el ciclo de vida del proceso de Claude, decide qué sesión reanudar, y coordina la interfaz y las interrupciones.
2. *[muestra c, c.0, c.1, c.2, c.3, c.4, k; resalta k]* — Claude Code es el motor de ejecución: razona con el modelo, elige herramientas, las ejecuta bajo su sistema de permisos, y guarda la transcripción de la sesión. La consecuencia importante es que Jarvis nunca ejecuta comandos por sí mismo.

### Escena 23: anatomía de la llamada  (`13:27`, 64 s)

1. *[muestra cmd, n1, n2]* — Así se invoca a Claude. Cada petición lanza un proceso nuevo del binario claude en modo no interactivo. Con stream-json y mensajes parciales, la salida llega como una línea JSON por evento, incluyendo el texto a medida que el modelo lo genera.
2. *[muestra n3, n4]* — El modo de permisos auto delega en el clasificador de seguridad de Claude Code qué acciones se permiten. El prompt de sistema añadido impone el estilo hablado, prohíbe listas y bloques de código, y exige pedir un sí antes de cualquier acción irreversible.
3. *[muestra n5, n6; resalta n5]* — Una decisión de coste: se limitan las herramientas a ocho. Cada descripción de herramienta viaja en cada petición, y el conjunto por defecto ocupaba unos veinticinco mil tokens. Con esta lista, más la desactivación de servidores MCP y skills, el contexto base baja de unos treinta y seis mil a unos once mil tokens.
4. *[muestra n7, n8]* — Con resume se continúa la sesión anterior. Y el proceso se lanza en su propio grupo de procesos, sin entrada estándar, que si fuera una tubería le haría esperar tres segundos. El grupo propio es lo que después permite cancelarlo por completo.

### Escena 24: una petición, evento por evento  (`14:31`, 58 s)

1. *[muestra seq, m1, m2]* — Sigamos una petición evento por evento. El hilo de conversación lanza un hilo trabajador, y ese hilo lanza el proceso claude y lee su salida línea a línea. Otro hilo pequeño vacía el error estándar para que la tubería nunca se bloquee.
2. *[muestra m3, m4, m5, m6; resalta m6]* — El primer evento, init, ya trae el identificador de sesión. Luego llegan fragmentos de texto. Cuando empieza un bloque de uso de herramienta, si Jarvis todavía no ha dicho nada, dice una frase corta como one moment, I'm checking that, para no dejar un silencio largo.
3. *[muestra m7, m8, m9; resalta m9]* — Claude ejecuta el comando con su herramienta Bash y recibe la salida. Esos mismos eventos, el uso de herramienta con su entrada completa y su resultado, alimentan la terminal de actividad que el usuario puede ver en pantalla.
4. *[muestra m10, m11, m12; resalta m11]* — Después llega el texto final y el evento result, con el identificador de sesión, el uso de tokens y el coste estimado. Jarvis actualiza la memoria, registra el consumo, y espera como máximo diez segundos a que el proceso termine.

### Escena 25: streaming: de fragmentos a oraciones  (`15:29`, 40 s)

**Componentes:** SUBPROCESO: claude stdout; JARVIS (PYTHON): Parser de eventos, SentenceStream, Cola de oraciones, ActivityConsole; AUDIO E/S: Voz; INTERFAZ: Burbuja

1. *[muestra cc, parse, split, con, a, b, f; flujo a (JSON), b (texto), f (tool)]* — El streaming es lo que hace que Jarvis parezca rápido. El parser clasifica cada evento: los fragmentos de texto van a un divisor de oraciones, y los eventos de herramientas van a la consola de actividad.
2. *[muestra q, tts, ui, c, d, e, ex; flujo c (oración), d (voz); resalta split]* — El divisor acumula texto y entrega una oración en cuanto aparece un signo de puntuación seguido de espacio. Cada oración completa entra en una cola, y el hilo de conversación la consume y la convierte en voz mientras Claude sigue escribiendo la siguiente.
3. *[muestra p, p.0, p.1]* — Dos salvaguardas: los eventos de subagentes se descartan, para no leer en voz alta trabajo intermedio, y si por algún motivo no llegó texto por streaming, se habla el campo result del evento final.

### Escena 26: sesión, contexto y memory.json  (`16:09`, 45 s)

**Componentes:** ARCHIVO: memory.json, ~/.claude/projects/*.jsonl; SUBPROCESO: Claude Code

1. *[muestra mem, cc, r1, json; flujo r1 (session_id); resalta mem]* — La continuidad conversacional tiene dos capas. Jarvis guarda en memory.json solo un puntero: el identificador de sesión, cuándo se usó, cuántos tokens tiene el contexto, y un resumen opcional. Si la sesión se usó hace menos de doce horas, se reanuda con resume.
2. *[muestra tr, r2; flujo r2]* — El historial real lo guarda Claude Code en su propio directorio, turno a turno. Es decir, la memoria a corto plazo es la transcripción de Claude, y Jarvis solo decide cuál continuar.
3. *[muestra p, p.0, p.1, p.2; resalta p.1]* — Para saber cuándo compactar hay que medir bien el tamaño. Una respuesta con herramientas hace varias llamadas, y el uso total las suma; por eso Jarvis toma la última iteración, cuya entrada es la conversación completa. Un matiz: Claude Code congela el prompt de sistema en el primer turno de cada sesión.

### Escena 27: compactación de memoria  (`16:54`, 38 s)

1. *[muestra ln, s1, s2, p, p.0, p.1]* — Una sesión que crece sin límite encarece y ralentiza cada respuesta. La solución es la compactación: cuando una conversación termina y el contexto supera sesenta mil tokens, Jarvis pide a un modelo barato que resuma lo aprendido.
2. *[muestra s3, s4, s5, s6, p.2; resalta s3]* — El resumen se guarda en memory.json y el identificador de sesión se borra. La próxima activación empieza una sesión nueva, con el resumen añadido al prompt de sistema, y el contexto vuelve a unos once mil tokens.
3. *[muestra p.3, p.4]* — La compactación es tolerante a fallos: si no se puede resumir, la sesión se conserva. Y como ocurre después de la despedida, el usuario nunca espera por ella.


## 6 · Ejecución de acciones y seguridad

### Escena 28: Ejecución de acciones y seguridad  (`17:33`, 5 s)

1. *[muestra num, title, p0, p1, p2]* — Capítulo seis: ejecución de acciones y seguridad, con un escenario real.

### Escena 29: de la voz al comando (registro real)  (`17:38`, 48 s)

1. *[muestra ln, a1, a2, a3]* — Ahora el escenario completo, con tiempos aproximados tomados de los registros. El usuario dice Hey Jarvis; mientras suena el saludo, Whisper se carga en segundo plano.
2. *[muestra a4, a5, a6; resalta a5]* — El usuario pregunta cuánto espacio libre tiene. Jarvis espera dos segundos de silencio para estar seguro de que terminó, y Whisper transcribe la frase en unas cuatro décimas de segundo.
3. *[muestra a7, a8, a9, a10, a11; resalta a9]* — Claude decide que necesita un comando. En cuanto aparece el bloque de herramienta, Jarvis dice one moment. Claude ejecuta df, lee la salida y redacta la respuesta, que empieza a sonar en cuanto existe la primera oración.
4. *[muestra n; resalta n]* — Observa dónde está la mayor espera fija: no en el modelo, sino en los dos segundos de silencio que marcan el fin de la frase. Es una decisión de comodidad para quien hace pausas al hablar, y se puede ajustar.

### Escena 30: la terminal de actividad  (`18:25`, 33 s)

1. *[muestra term, term.*, p, p.0, p.1]* — Para que el usuario sepa en todo momento qué hace el agente, cada uso de herramienta se escribe en un archivo de actividad, con el formato de una terminal: un comentario con la intención, el comando con el signo de dólar, y su salida.
2. *[muestra p.2, p.3, p.4; resalta term]* — La primera vez que Claude usa una herramienta en una conversación, Jarvis abre una terminal que sigue ese archivo desde el byte anterior al primer comando, así solo muestra lo nuevo. Se reutiliza para las siguientes peticiones y se cierra al volver a dormir. Con terminales distintas de COSMIC, el comportamiento está implementado pero no verificado.

### Escena 31: modelo de permisos y riesgos  (`18:59`, 57 s)

1. *[muestra t, t.0, t.1; resalta t.1]* — La seguridad se apoya en capas de naturaleza distinta. La primera es la activación misma. La segunda, técnica pero externa a Jarvis, es el modo de permisos auto: el clasificador de Claude Code decide qué acciones bloquear.
2. *[muestra t.2, t.3; resalta t.2]* — La tercera es blanda: el prompt de sistema pide confirmar con un sí antes de borrar, desinstalar o cambiar ajustes, pero depende de que el modelo obedezca. Restringir a ocho herramientas reduce superficie, aunque Bash por sí solo ya puede hacer todo lo que el usuario puede hacer.
3. *[muestra t.4, t.5, t.6]* — sudo no funciona, porque pediría una contraseña sin terminal. Todo queda visible y registrado, y los datos sensibles se guardan con permisos restringidos.
4. *[muestra r, r.0, r.1, r.2]* — Los riesgos que permanecen son reales: cualquier voz cercana puede dar órdenes, el contenido que Claude lee puede contener instrucciones maliciosas, y no hay sandbox: el agente corre con los permisos del usuario. Por eso el proyecto desaconseja expresamente el modo que salta los permisos.


## 7 · Text-to-Speech

### Escena 32: Text-to-Speech  (`19:56`, 3 s)

1. *[muestra num, title, p0, p1, p2]* — Capítulo siete: de texto a voz.

### Escena 33: Kokoro: del texto al altavoz  (`19:59`, 46 s)

**Componentes:** JARVIS (PYTHON): Oraciones, _kokoro_pieces, Línea de tiempo; MODELO LOCAL: Kokoro ONNX; AUDIO E/S: pw-play --raw f32, Altavoz; INTERFAZ: Burbuja

1. *[muestra q, pc, k, a, b; flujo b (texto)]* — Kokoro es un modelo de voz pequeño que corre en el procesador con ONNX. Recibe oraciones, y la primera, si es larga, se corta en la primera coma para que el sonido empiece antes.
2. *[muestra pp, sp, c, d, tl, ui, e, f; flujo c (PCM), d (voz), f (nivel)]* — El audio generado se escribe directamente en la entrada estándar de un único pw-play, que permanece abierto durante toda la respuesta. En paralelo se registra una línea de tiempo con el texto y la envolvente de volumen de cada fragmento, que la burbuja usa para los subtítulos y la animación.
3. *[muestra p, p.0, p.1, p.2]* — Dos trucos de configuración: se pueden mezclar voces promediando sus vectores de estilo, y la voz grave se consigue sintetizando más rápido y reproduciendo a una frecuencia de muestreo menor. Como la síntesis es unas seis veces más rápida que el habla, el cálculo nunca deja al altavoz sin audio.

### Escena 34: hablar mientras Claude todavía escribe  (`20:45`, 28 s)

1. *[muestra ln, c1, s1, k1, p1, c2]* — Este diagrama muestra la concurrencia del habla. Claude genera la oración uno; en cuanto termina, el divisor la entrega, Kokoro la sintetiza en medio segundo, y empieza a sonar mientras Claude ya está escribiendo la oración dos.
2. *[muestra s2, k2, p2, c3, s3, k3, p3, p, p.0, p.1, p.2]* — El proceso se repite como una cadena de montaje. La latencia percibida deja de ser la de la respuesta completa y pasa a ser la de la primera oración. Antes del streaming, Jarvis esperaba a que Claude terminara todo antes de decir una palabra.

### Escena 35: respaldo con Edge TTS  (`21:13`, 31 s)

**Componentes:** MODELO LOCAL: Kokoro; JARVIS (PYTHON): Oraciones restantes, Hilo productor; SERVICIO EXTERNO: Edge TTS; AUDIO E/S: pw-play archivo.mp3

1. *[muestra k, rest, a, b, prod; flujo a (error)]* — Si Kokoro lanza una excepción en mitad de una respuesta, el generador devuelve las oraciones que faltan, empezando por la que falló, para no repetir lo ya dicho. Edge TTS, el servicio de voz en línea de Microsoft, continúa desde ahí.
2. *[muestra edge, play, c, d, e, p, p.0, p.1, p.2; flujo c, e]* — Edge funciona por oraciones completas en MP3, con un hilo productor que prepara la siguiente mientras suena la actual, y dos intentos por oración. Al no tener muestras, el orbe usa un pulso simulado. Este camino está implementado, pero no se ha verificado en el equipo de pruebas.


## 8 · Interfaz visual y sincronización

### Escena 36: Interfaz visual y sincronización  (`21:44`, 4 s)

1. *[muestra num, title, p0, p1, p2]* — Capítulo ocho: la interfaz visual y su sincronización.

### Escena 37: los cuatro estados de la burbuja  (`21:49`, 33 s)

1. *[muestra o1, o2, o3, o4; resalta o1, o2, o3, o4]* — La burbuja tiene exactamente cuatro estados. Dormido, oculta, con una brasa que respira. Escuchando, con un núcleo que crece con el volumen de tu voz. Pensando, con tres cuentas que orbitan como un reloj. Y hablando, con ondas que salen al ritmo de la voz de Jarvis.
2. *[muestra p, p.0, p.1, p.2; resalta o4, o2]* — Es importante decirlo con precisión: no existe un estado interrumpido. Una interrupción se ve como la transición de hablando a escuchando. Los controles dependen del estado: detener solo al hablar, cerrar en cualquier estado activo, y el orbe cambia de función según lo que esté pasando.

### Escena 38: sincronización entre hilos  (`22:22`, 38 s)

**Componentes:** JARVIS (PYTHON): Hilos de trabajo, GLib.idle_add, mic_level, voice_level(), current_caption(); INTERFAZ: Hilo principal GTK, Temporizador 16 ms

1. *[muestra w, idle, gtk, a, b; flujo a (estado), b]* — GTK no es seguro entre hilos, así que ningún hilo de trabajo toca la ventana. Los cambios de estado y de texto se encolan con idle add y los ejecuta el hilo principal.
2. *[muestra tick, c, ml, vl, cap, d, e, f; resalta vl, cap]* — La animación, en cambio, no recibe eventos: un temporizador de dieciséis milisegundos dibuja la burbuja y consulta tres valores. El nivel del micrófono, el nivel de la voz según la envolvente del fragmento que suena, y el subtítulo correspondiente a ese instante.
3. *[muestra p, p.0, p.1, p.2, p.3]* — Así, voz y subtítulos quedan sincronizados por reloj y no por mensajes. La capa de superposición de Wayland mantiene la burbuja encima de todo sin capturar el teclado.


## 9 · Interrupciones y concurrencia

### Escena 39: Interrupciones y concurrencia  (`22:59`, 4 s)

1. *[muestra num, title, p0, p1, p2]* — Capítulo nueve: interrupciones y concurrencia.

### Escena 40: hablar encima de Jarvis  (`23:03`, 56 s)

1. *[muestra seq, m1, m2]* — Mientras Jarvis habla, un hilo monitor escucha el micrófono con una segunda instancia de Silero VAD. Ignora las primeras tres décimas de segundo, para no reaccionar al clic del altavoz ni a la propia respiración.
2. *[muestra m3, m4, m5; resalta m5]* — Si detecta voz durante al menos tres décimas de segundo, guarda los últimos ochenta centésimos de audio, activa la señal de cancelación del habla y mata el proceso pw-play. La voz se corta de inmediato.
3. *[muestra m6, m7; resalta m6]* — Aquí hay una decisión de diseño importante: la petición de Claude no se cancela. Una interrupción accidental, una tos, no debe abortar una instalación a medias. Claude termina en silencio, mientras la cola del micrófono sigue guardando tus palabras.
4. *[muestra m8, p, p.0, p.1]* — Cuando Claude termina, Jarvis retoma la escucha con el audio guardado y sin vaciar la cola, así que no se pierde ni una palabra. En modo wakeword solo interrumpe la palabra de activación. Y el botón cerrar es distinto: ese sí cancela a Claude y todo lo que lanzó.

### Escena 41: mapa de concurrencia  (`23:59`, 50 s)

1. *[muestra t, t.0, t.1, t.2, t.3, t.4]* — Este es el mapa completo de concurrencia. Hay un hilo principal para GTK, un hilo de conversación que es el único consumidor del micrófono en cada momento, el lector del micrófono, el monitor de interrupción, y el trabajador de Claude con dos lectores.
2. *[muestra t.5, t.6, p, p.0, p.1, p.2]* — A eso se suman hilos auxiliares y cinco tipos de procesos hijos. La coordinación usa primitivas sencillas: eventos para cancelar, candados para proteger el reproductor y la línea de tiempo, y colas. Los generadores consultan la cola cada décima de segundo para poder abandonar a tiempo.
3. *[muestra p.3, p.4; resalta p.3]* — Los riesgos están acotados, pero existen: hay estado compartido, como el identificador de sesión, que escribe el trabajador; se mitiga esperando a que termine antes del siguiente turno. Y si el proceso principal muere de forma abrupta, systemd termina todo el grupo de control, incluidos los hijos.


## 10 · Gestión de conversaciones y memoria

### Escena 42: Gestión de conversaciones y memoria  (`24:50`, 4 s)

1. *[muestra num, title, p0, p1]* — Capítulo diez: gestión de conversaciones y memoria.

### Escena 43: fin de conversación y limpieza  (`24:54`, 32 s)

1. *[muestra end, end.0, end.1, n]* — Una conversación termina de tres formas. Con una despedida corta, que se detecta en local sin llamar a Claude: debe contener una frase de cierre, tener como máximo doce palabras y no incluir verbos de petición, para que gracias, ahora abre Steam, no se tome como despedida.
2. *[muestra end.2, end.3, clean, clean.*; resalta clean]* — También termina tras diez segundos sin voz, o con el botón cerrar. Al terminar, una única rutina hace la limpieza: reinicia el detector, vacía el micrófono, oculta la burbuja, cierra la terminal, programa la descarga de Whisper, y compacta la memoria si hace falta.

### Escena 44: reanudar una conversación  (`25:26`, 27 s)

1. *[muestra seq, m1, m2, m3, m4]* — Cada activación empieza leyendo memory.json. Si la última sesión se usó hace menos de doce horas, se reanuda: Claude carga su transcripción y responde con todo el contexto previo.
2. *[muestra m5, m6, m7; resalta m7]* — Tras cada petición se guarda el nuevo tamaño del contexto, con escritura atómica mediante un archivo temporal y un renombrado. Si pasaron más de doce horas, o la sesión fue compactada, empieza una conversación nueva que solo conoce el resumen.


## 11 · Funcionalidades adicionales

### Escena 45: Funcionalidades adicionales  (`25:53`, 4 s)

1. *[muestra num, title, p0, p1, p2]* — Capítulo once: funcionalidades adicionales.

### Escena 46: modo juego  (`25:56`, 26 s)

**Componentes:** AUDIO E/S: “turn on gaming mode”; SUBPROCESO: Claude Code, Whisper small · CPU · int8, Whisper large-v3-turbo · GPU; ARCHIVO: gaming_mode; JARVIS (PYTHON): LocalSTT.wanted()

1. *[muestra u, cc, f, a, b; flujo a (voz), b (touch)]* — El modo juego deja la tarjeta gráfica entera a los juegos. El usuario lo pide en lenguaje natural; el prompt de sistema le explica a Claude que basta con crear o borrar un archivo.
2. *[muestra stt, cpu, gpu, c, d, e, p, p.0, p.1; flujo c, d]* — Cuando el archivo existe, la transcripción usa el modelo pequeño en el procesador. Si la especificación cambia, el proceso de Whisper se reinicia, y si quedaba un modelo en la gráfica, se descarga inmediatamente al terminar la conversación.

### Escena 47: terminal por voz, idiomas, voces y servicio  (`26:22`, 46 s)

1. *[muestra t, t.0, t.1; resalta t.0]* — El interruptor de la terminal se resuelve en local: se eliminan muletillas, y si lo que queda es una orden corta que coincide con el patrón, se escribe encendido o apagado en un archivo, sin llamar a Claude. Cualquier otra forma de decirlo la entiende Claude gracias al prompt.
2. *[muestra t.2, t.3]* — En idiomas, Jarvis puede responder en el idioma del usuario o en uno fijo, y tiene un modo tutor para practicar: si hablas en tu idioma nativo, primero te dice cómo se diría en el idioma que estás aprendiendo.
3. *[muestra t.4, t.5, t.6; resalta t.6]* — Las voces se configuran por archivo, incluida la mezcla, la velocidad y el tono. Y el servicio se controla con systemctl. Para despertarlo con un atajo de teclado se envía la señal SIGUSR1 solo al proceso principal; sin esa precaución, la señal también mataría a pw-record.


## 12 · Manejo de errores y escenarios de fallo

### Escena 48: Manejo de errores y escenarios de fallo  (`27:08`, 6 s)

1. *[muestra num, title, p0, p1]* — Capítulo doce: errores y escenarios de fallo. Solo mecanismos que existen en el código.

### Escena 49: lado de entrada  (`27:15`, 43 s)

1. *[muestra t, t.0, t.1]* — Empecemos por la entrada. Si la palabra no se detecta, el registro de casi activaciones permite calibrar, y siempre se puede despertar con un clic o con la señal manual. Una falsa activación se agota sola tras diez segundos de silencio.
2. *[muestra t.2; resalta t.2]* — Si el micrófono deja de enviar audio, el proceso termina a propósito y systemd lo reinicia. Es una estrategia de dejar que falle y reiniciar limpio, en lugar de intentar reparar el estado interno.
3. *[muestra t.3, t.4, t.5, t.6]* — Si Whisper local no carga, o no responde en sesenta segundos, se descarta el proceso y se recurre a Groq si hay una clave. Si Groq falla, Jarvis pide repetir y vuelve a escuchar, sin reintentos automáticos. Y las alucinaciones típicas sobre ruido se descartan.

### Escena 50: lado de salida  (`27:57`, 50 s)

1. *[muestra t, t.0, t.1]* — En la salida, si Claude no tiene sesión iniciada, la salida no es JSON y menciona el login; Jarvis lo detecta y dice qué comando ejecutar. Cualquier otra salida inesperada produce un mensaje genérico, sin quedarse colgado.
2. *[muestra t.2, t.3; resalta t.3]* — Si Claude supera los trescientos segundos, o el usuario cancela, se envía una señal de terminación a todo el grupo de procesos, se esperan tres segundos y se fuerza el cierre. Se usa una espera que no recoge el proceso hasta matar el grupo, para que su identificador no pueda reutilizarse, y después se recoge para no dejar zombis.
3. *[muestra t.4, t.5, t.6, t.7, t.8]* — En la voz, Kokoro tiene a Edge como respaldo. Si un comando falla, el error aparece en rojo en la terminal y Claude decide cómo informarlo. Y cualquier excepción no prevista en un turno se captura: Jarvis se disculpa y vuelve a dormir, en lugar de dejar el servicio en un estado inconsistente.


## 13 · Análisis arquitectónico y decisiones de ingeniería

### Escena 51: Análisis arquitectónico y decisiones de ingeniería  (`28:48`, 9 s)

1. *[muestra num, title, p0, p1, p2]* — Capítulo trece: análisis arquitectónico. Las decisiones actuales no son necesariamente las correctas; veamos sus compromisos.

### Escena 52: fortalezas  (`28:56`, 31 s)

1. *[muestra p, p.0, p.1]* — Como fortalezas, primero: no reinventa el agente. Reutilizar Claude Code aporta herramientas, permisos, sesiones y transcripciones probadas. Segundo, el aislamiento por procesos, que hace posible liberar la memoria de vídeo y cancelar de forma limpia.
2. *[muestra p.2, p.3, p.4, p.5]* — Tercero, una latencia percibida baja gracias a ocultar la carga del modelo y al streaming. Cuarto, decisiones basadas en mediciones. Y quinto, transparencia y degradación elegante: casi todos los fallos tienen un respaldo o, al menos, un mensaje hablado.

### Escena 53: compromisos y alternativas  (`29:27`, 49 s)

1. *[muestra t, t.0; resalta t.0]* — Ahora los compromisos. Usar el binario de Claude Code por petición da un agente completo, pero cuesta un arranque de proceso en cada turno y acopla Jarvis al formato de eventos de la CLI. Una alternativa sería el Agent SDK con una sesión persistente.
2. *[muestra t.1, t.2]* — Whisper en proceso hijo libera la gráfica, a cambio de una carga en cada activación que hoy se oculta tras el saludo. Los hilos con eventos son simples, pero dejan estado compartido; asyncio o un modelo de actores lo harían más explícito.
3. *[muestra t.3, t.4, t.5; resalta t.5]* — Un único archivo de unas mil setecientas líneas es fácil de desplegar, pero es la principal deuda de mantenibilidad. El sondeo de playerctl podría sustituirse por señales de D-Bus. Y la seguridad sin aislamiento real podría reforzarse con un sandbox o una lista blanca de comandos, a costa de fricción.

### Escena 54: límites, escalabilidad y deuda técnica  (`30:16`, 29 s)

1. *[muestra lim, lim.*]* — En límites: es un sistema para un usuario y una máquina, dependiente de PipeWire y systemd, con la activación solo en inglés, y cuya continuidad depende del formato de sesiones de Claude Code.
2. *[muestra debt, debt.*]* — En deuda técnica: el archivo monolítico, la configuración duplicada entre código y ejemplo, pruebas automáticas que cubren solo funciones puras, y caminos de respaldo que existen pero no se han verificado recientemente. Ninguno es crítico, pero conviene conocerlos antes de crecer.


## Cierre · Conclusiones

### Escena 55: Conclusiones  (`30:45`, 39 s)

1. *[muestra orb, c0, c1]* — Para cerrar. Jarvis es, en esencia, una capa de voz y de gestión del ciclo de vida alrededor de un agente existente. Usa procesos para aislar recursos y poder cancelar, e hilos con colas para coordinar.
2. *[muestra c2, c3, c4]* — El streaming de extremo a extremo hace que la latencia percibida sea la de la primera oración. La memoria combina la transcripción de Claude Code con un puntero y un resumen propios. Y la seguridad funciona por capas, aunque sin aislamiento real del sistema.
3. *[sin cambios]* — Con esto deberías poder imaginar el recorrido completo: de una palabra en el aire, a un comando en tu sistema, y de vuelta a una voz. Gracias por acompañar esta revisión.

