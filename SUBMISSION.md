# Sincro — paquete de envío (Devpost)

- **Nombre:** Sincro
- **Lema:** Subtítulos y traducción en vivo, abiertos y a escala.
- **Demo en vivo:** https://sincro.gscod.com
- **Repositorio:** https://github.com/GastonSch/singro
- **Licencia:** MIT (OSI)
- **Video:** _(pegar link de YouTube)_

---

## Historia

### Inspiración
En Nerdearla hace años ofrecemos transcripción simultánea al español. Hoy se
resuelve con dos herramientas comerciales (una para español→español y otra para
traducir inglés→español en vivo). Funcionó durante años, pero este año hay **más
de 30 charlas en inglés, muchas en simultáneo**, y el esquema dejó de escalar:
es caro, depende de operación manual y no se puede replicar en otros eventos.
Casi todas las conferencias tienen el mismo problema y ninguna tiene una solución
abierta. **Sincro** nace de ahí: no reemplaza a los intérpretes humanos en todos
los contextos, sino que permite que una conferencia open source monte subtítulos
en vivo, en varios idiomas y escenarios, sin depender de una caja negra.

### Cómo lo construí
Pipeline en **Python asíncrono** con piezas desacopladas:
1. **Audio en vivo** desde micrófono, archivo o stream (RTSP/HTTP/HLS) e incluso
   **charlas de YouTube** (vía `yt-dlp`), normalizado a PCM 16 kHz mono con `ffmpeg`.
2. **Motor intercambiable:** `gemini_live` (Live API en streaming, traducción
   nativa con `translation_config`), `gemini_chunk` (REST), `local`
   (`faster-whisper` int8 + `argostranslate`) y `mock` (demos sin credenciales).
3. **`SessionManager`**: cada escenario es una tarea `asyncio`; motor compartido.
4. **EventBus + WebSocket** que difunde cada subtítulo a la vista de audiencia,
   al overlay de OBS y al monitor de producción.
5. **UI de audiencia** con **video embebido + botón Ejecutar** (sin autostart),
   export SRT/VTT/TXT/JSON, glosario de términos técnicos y Docker/systemd.

### Qué aprendí
- La **Live API** de Gemini permite transcripción de entrada e interpretación en
  un mismo stream (`input_audio_transcription` + traducción nativa).
- En tiempo real la **segmentación pesa más que el modelo**: con VAD a 500 ms el
  primer subtítulo pasó de ~27 s a ~5–7 s.
- Escalar es **desacoplar** captura, inferencia y difusión: pasar de 2 a 30
  sesiones es sumar tareas/réplicas, no reescribir.
- Un motor `mock` determinista permite desarrollar y testear sin credenciales ni GPU.

### Desafíos
- **Hardware hostil** (sin GPU, 8 núcleos, ~7 GB RAM): inviable correr 10 sesiones
  Whisper locales → diseño híbrido (Gemini para escala, local como fallback).
- **Reconexión de la Live API**: pump de audio persistente + backoff para que una
  charla larga no pierda subtítulos.
- **Deltas de transcripción**: el texto llega fragmentado; hubo que acumular y
  finalizar por pausa/fin de oración para exportar bloques coherentes.
- **REST en 503** y renombres de modelos (`gemini-2.5-flash` → `gemini-3.8-flash`);
  se resolvió usando el modelo Live de traducción.
- **Ritmo real del audio**: pacing manual de `ffmpeg` con loop para las demos.

---

## Built with
`Python, JavaScript, HTML, CSS, FastAPI, Uvicorn, google-genai, Gemini Live API
(gemini-3.5-live-translate-preview), asyncio, WebSockets, Faster-Whisper,
CTranslate2, Argos Translate, FFmpeg, yt-dlp, NumPy, Pydantic, PyYAML, Docker,
Docker Compose, uv, pytest`

---

## Guion del video (1–2 min)

1. **(0:00) Contexto (12 s).** “Nerdearla tiene 30+ charlas en inglés y necesita
   subtítulos y traducción a escala. Esto es Sincro.”
2. **(0:12) Escenario 1 EN→ES.** En `sincro.gscod.com`, elegir *Escenario 1*,
   presionar **▶ Ejecutar**. Mostrar el video y, al costado, el original en inglés
   y la traducción al español apareciendo en vivo (≈5 s de retraso).
3. **(0:45) Multisesión / idiomas.** Cambiar a *Escenario 2* (ES→EN) y ejecutarlo;
   mostrar que corre en simultáneo.
4. **(1:05) Charla real de Nerdearla.** *Escenario 3* toma audio de YouTube con el
   mismo video embebido y lo traduce.
5. **(1:20) Producción e innovación.** Mostrar `/monitor` (latencia/errores),
   `/overlay` (OBS) y una **exportación SRT**.
6. **(1:35) Escala y cierre.** “N sesiones en un proceso; el README explica cómo
   replicar con Redis/NATS. Open source, MIT, deploy en un comando.”

> Pro-tip del jurado: subir el video a YouTube y **subtitularlo en inglés con el
> propio Sincro** (usar el video como fuente y exportar el SRT).

---

## Checklist de envío
- [ ] Video en YouTube + subtítulos EN.
- [ ] Devpost: nombre, lema, historia (arriba), *Built with*, demo URL y repo.
- [ ] Repo público con licencia MIT y README.
- [ ] Enviado antes del **25/09/2026 15:00 UTC**.
