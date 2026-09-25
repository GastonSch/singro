#!/usr/bin/env bash
# Regenera los audios de prueba de samples/ usando voces neuronales de edge-tts.
# Requiere: uv pip install edge-tts
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p samples

EN_TEXT="Welcome to Nerdearla. Today we are going to talk about how open source communities build accessible conferences. We run more than thirty sessions in parallel, and we use Kubernetes to orchestrate the transcription workers. Each audience member can pick a session and read the subtitles in their own language. The system detects the spoken language automatically and translates English into Spanish in real time. If you are watching from home, the stream is also captioned. Let us get started."

ES_TEXT="Bienvenidos a Nerdearla. Hoy vamos a hablar sobre accesibilidad en conferencias de codigo abierto. El sistema transcribe el audio en vivo y traduce automaticamente al espanol. Cada persona puede elegir la sesion y el idioma de los subtitulos. Nuestro objetivo es que ninguna charla quede sin ser entendida, sin importar el idioma en el que se hable. Gracias por acompanarnos."

python -m edge_tts --voice en-US-AriaNeural --text "$EN_TEXT" --write-media samples/demo_en.mp3
python -m edge_tts --voice es-AR-ElenaNeural --text "$ES_TEXT" --write-media samples/demo_es.mp3

echo "Listo: samples/demo_en.mp3 y samples/demo_es.mp3"
