# Sincro

> *Subtítulos y traducción en vivo, abiertos y a escala.*

Subtítulos en vivo **open source** para conferencias: transcripción en el idioma
original y traducción en tiempo real (inglés → español y más), pensado para correr
**muchas sesiones en paralelo** (5, 10, 30 escenarios) con un costo bajo.

> **English overview** — *Sincro* is open source real-time transcription &
> translation for conferences. It ingests live audio (microphone, file or stream),
> transcribes the original language and translates it (EN→ES) in real time, renders
> captions in a web audience view / OBS overlay, and runs **multiple simultaneous
> sessions**. Built for the **Nerdearla Vibeathon 2026**. Powered by Gemini Live
> audio (default) with a 100% local fallback (faster-whisper + argostranslate).

- **Licencia:** MIT (OSI).
- **Motor por defecto:** Gemini Live API (`gemini-live-2.5-flash-preview`).
- **Modo sin credenciales:** `mock` (demo instantánea) y `local` (offline).

---

## ¿Qué resuelve?

En Nerdearla hay 30+ charlas en inglés, muchas en simultáneo. Las herramientas
comerciales actuales son caras, requieren operación manual y no se replican.
Este proyecto procesa **N sesiones concurrentes** desde un solo servicio, con una
vista para la audiencia (elige sesión e idioma), un overlay para OBS y exportación
de la transcripción.

### Requisitos del desafío cubiertos

| Requisito | Dónde |
|---|---|
| Audio en vivo: micrófono / archivo / stream | `src/captions/audio/` (ffmpeg + sounddevice) |
| Transcripción en tiempo real del idioma original | `input_audio_transcription` (Gemini) |
| Traducción EN→ES en tiempo real | intérprete Gemini / `gemini_chunk` / `argostranslate` |
| Subtítulos visibles | UI web, overlay OBS y página de monitoreo |
| ≥2 sesiones simultáneas | `sessions.yaml` trae 2; escala a N (ver más abajo) |
| Audio de prueba en el repo | `samples/demo_en.mp3`, `samples/demo_es.mp3` |

### Funciones extra (opcionales del desafío)

- Integración con **OBS/vMix** vía *Browser Source* (`/overlay`).
- **Glosario** de términos técnicos y nombres propios (`glossary` en `sessions.yaml`).
- **Exportación** de la transcripción a **SRT / VTT / TXT / JSON**.
- **Panel de producción** (`/monitor`) con estado, latencia y errores por sesión.
- Salida configurable a **otros idiomas** (pt, fr, …): solo cambia `target_language`.

---

## Arquitectura

```
                 ┌──────────────────────────────────────────────────────────┐
 Fuentes         │  Sesión (una por escenario)                              │
 ┌──────────┐    │                                                          │
 │ archivo  │    │  AudioSource ─► PCM 16 kHz mono ─► Engine.run()          │
 │ stream   │───►│       (ffmpeg)                    │                      │
 │ micrófono│    │       (sounddevice)               │  Gemini Live /        │
 └──────────┘    │                                   │  Gemini REST /        │
                 │                                   │  Whisper local / mock │
                 │                                   ▼                       │
                 │                          CaptionEvent (original+traducción)
                 │                                   │                       │
                 └───────────────────────────────────┼───────────────────────┘
                                                     ▼
                              SessionManager (N sesiones asyncio)  ─►  EventBus
                                                                        │
                        ┌───────────────────────────────────────────────┤
                        ▼                        ▼                       ▼
                 WebSocket /ws            REST /api/*              Overlay OBS
                 (vista audiencia)     (crear/exportar/estado)      /overlay
```

- **Un proceso** maneja todas las sesiones como tareas `asyncio`.
- El **engine** es compartido; cada sesión mantiene su estado y su cola.
- Los eventos se publican en un **EventBus** en proceso y se difunden por WebSocket.

---

## Inicio rápido

### Opción A — con `uv` (recomendado)

```bash
git clone <repo> nerdearla-captions && cd nerdearla-captions
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt

cp .env.example .env      # opcional: completá GEMINI_API_KEY
./scripts/run.sh
```

### Opción B — con `venv`/`pip`

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn captions.main:app --app-dir src --port 8000
```

Abrí **http://localhost:8000**. Por defecto arranca en modo `mock` con dos sesiones
de ejemplo, así que **funciona sin ninguna credencial**.

Las sesiones **no arrancan solas** (`autostart: false`). La audiencia elige el
escenario, presiona **▶ Ejecutar** y ve el **video con los subtítulos en vivo**
al costado. Podés pausar/detener y cambiar el idioma mostrado (original / traducción / ambos).

- Vista audiencia: `/`
- Panel de producción: `/monitor`
- Overlay para OBS: `/overlay?session=escenario-1&lang=translation`

### Usar el motor real (Gemini)

1. Obtené una API key en <https://aistudio.google.com/apikey>.
2. Completá `.env`:

   ```bash
   CAPTIONS_ENGINE=gemini_live
   GEMINI_API_KEY=tu_api_key
   ```

3. Reiniciá `./scripts/run.sh`.

### Probar con los audios del repo

Los archivos `samples/demo_en.mp3` (charla en inglés) y `samples/demo_es.mp3`
(charla en español) ya están configurados en `sessions.yaml`. Reinician en loop,
así que sirven para una demo continua. También podés importarlos desde la UI con
el botón **+ Sesión** (autocompleta desde `/api/samples`), o apuntar a cualquier
video/stream:

```yaml
source:
  type: stream
  url: "https://youtube.com/live/…"   # o rtsp://… o un archivo .mp4
```

Para regenerar los audios de prueba: `pip install edge-tts && ./scripts/make_samples.sh`.

---

## Motores disponibles

Se elige con `CAPTIONS_ENGINE` (o `engine:` en `sessions.yaml`).

| Motor | Qué hace | Latencia | Requisitos |
|---|---|---|---|
| `gemini_live` **(default real)** | Gemini Live API en streaming; transcripción de entrada + interpretación | la más baja (~1–2 s) | `GEMINI_API_KEY` |
| `gemini_chunk` | Corta el audio en ventanas solapadas y pide JSON `{original, translation}` por REST | ~2–4 s | `GEMINI_API_KEY` |
| `local` | `faster-whisper` (int8, CPU) + `argostranslate` | ~2–5 s | `requirements-local.txt` |
| `mock` | Subtítulos de ejemplo, sin red ni modelos | instantánea | — |

Modelos y parámetros configurables en `.env` y `sessions.yaml`
(`model`, `rest_model`, `chunk_seconds`, `overlap_seconds`, `native_translation`).

### Motor 100% local

```bash
uv pip install --python .venv/bin/python -r requirements-local.txt
# descarga del paquete en→es de argostranslate
python -c "import argostranslate.package as p; p.update_package_index(); \
  [p.install_from_path(p.download_package(x)) for x in p.get_available_packages() \
   if x.from_code=='en' and x.to_code=='es']"
CAPTIONS_ENGINE=local WHISPER_MODEL=small ./scripts/run.sh
```

---

## Multi-sesión y escalado

**Simultáneo hoy:** todas las sesiones de `sessions.yaml` se lanzan al iniciar;
también se crean en caliente desde la UI o por API:

```bash
curl -X POST localhost:8000/api/sessions -H 'Content-Type: application/json' -d '{
  "id": "escenario-3",
  "name": "Escenario 3",
  "source": {"type": "stream", "url": "https://…", "realtime": true},
  "source_language": "en", "target_language": "es"
}'
```

### Cómo escalar a 5, 10 o 30 sesiones

1. **Vertical (un host).** Con Gemini Live, cada sesión es una conexión de
   streaming: el cuello de botella es la red/API, no la CPU. Subí
   `max_inflight` (REST) y listo. Para el motor `local`, en cambio, cada sesión
   compite por CPU: usá `WHISPER_MODEL=tiny|base` y un pool de workers.
2. **Elegir el motor según escala.**
   - `gemini_live` → menor latencia, ideal 10–30 sesiones en un solo servicio.
   - `gemini_chunk` → más robusto y fácil de paralelizar (peticiones sin estado).
   - `local` → sin costo de API, pero necesita GPU o varias instancias para 10+.
3. **Horizontal (varios hosts).** La capa web es sin estado. Escalá el servicio
   con un balanceador y mové el `EventBus` a **Redis Pub/Sub o NATS** para que
   cualquier réplica reciba y difunda subtítulos (hoy el bus es en proceso;
   `src/captions/events.py` es el único punto a cambiar). Cada sesión puede
   asignarse a una réplica por *
   sharding* de `session_id`.
4. **Kubernetes + HPA.** Desplegá la imagen con `replicas: N` y autoescalado por
   uso de CPU/red; nodos GPU opcionales para el motor local.
5. **Costo.** Gemini cobra por token de audio; usar `gemini-live-2.5-flash-preview`
   o `flash` mantiene el costo bajo por hora de charla frente a las herramientas
   comerciales actuales.

> Regla práctica: **1 servicio ≈ 10–30 sesiones** con `gemini_live`. Para pasar de
> ahí, agregá réplicas y un bus compartido; no hace falta cambiar el pipeline.

---

## API

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/health` | Estado, motor, modelo, key configurada |
| GET | `/api/samples` | Audios de prueba disponibles |
| GET | `/api/sessions` | Lista de sesiones y estadísticas |
| POST | `/api/sessions` | Crea una sesión (JSON) |
| DELETE | `/api/sessions/{id}` | Elimina una sesión |
| POST | `/api/sessions/{id}/start` \| `/stop` | Controla una sesión |
| GET | `/api/sessions/{id}/transcript?format=srt\|vtt\|txt\|json&lang=translation\|original\|both` | Exporta |
| WS | `/ws` | Stream de eventos (caption, block, status, sessions) |

---

## Docker

```bash
cp .env.example .env   # completá GEMINI_API_KEY
docker compose up --build
# http://localhost:8000
```

---

## Deploy en producción (`sincro.gscod.com`)

Guía completa con **systemd + nginx + TLS** (y la alternativa Docker) en
[`deploy/README.md`](deploy/README.md). Incluye el `location` con *upgrade* de
WebSocket y `proxy_buffering off`, imprescindibles para subtítulos en vivo.

---

## Tests

```bash
.venv/bin/python -m pytest tests/ -q
```

---

## Estructura

```
src/captions/
  main.py            # FastAPI + WebSocket + export
  manager.py         # N sesiones
  session.py         # pipeline de una sesión + métricas
  events.py          # EventBus
  config.py          # settings + sessions.yaml
  audio/             # ffmpeg (file/stream), micrófono, PCM/WAV
  engines/           # gemini_live, gemini_chunk, local (whisper), mock
  translate.py       # MT offline (argostranslate)
  static/            # index (audiencia), overlay (OBS), monitor (producción)
samples/             # audios de prueba EN/ES
scripts/             # run.sh, make_samples.sh, test_gemini.py
deploy/              # nginx + systemd para sincro.gscod.com
sessions.yaml        # configuración de escenarios
```

## Créditos

Construido para la **Vibeathon de Nerdearla 2026**. Licencia MIT.
