# Deploy de Sincro en `sincro.gscod.com`

Guía de puesta en producción con **systemd + nginx** (recomendada, sin Docker) o
**Docker Compose**.

## 1. Código y entorno

```bash
sudo mkdir -p /opt/sincro && sudo chown "$USER" /opt/sincro
git clone <tu-repo> /opt/sincro && cd /opt/sincro
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env
nano .env            # CAPTIONS_ENGINE=gemini_live  y  GEMINI_API_KEY=...
```

## 2. Servicio systemd

```bash
sudo cp deploy/sincro.service /etc/systemd/system/sincro.service
# ajustá User/Group y las rutas si no usás /opt/sincro
sudo useradd -r -s /usr/sbin/nologin sincro 2>/dev/null || true
sudo chown -R sincro:sincro /opt/sincro
sudo systemctl daemon-reload
sudo systemctl enable --now sincro
sudo systemctl status sincro
```

El servicio escucha en `127.0.0.1:8000` (no expuesto directo).

## 3. nginx + TLS

```bash
sudo cp deploy/nginx-sincro.conf /etc/nginx/sites-available/sincro
sudo ln -sf /etc/nginx/sites-available/sincro /etc/nginx/sites-enabled/sincro
# DNS: apuntá el registro A de sincro.gscod.com a la IP del servidor
sudo certbot --nginx -d sincro.gscod.com
sudo nginx -t && sudo systemctl reload nginx
```

El bloque `location /` ya trae el *upgrade* de WebSocket y `proxy_buffering off`,
necesarios para que los subtítulos se transmitan en tiempo real.

## 4. Alternativa con Docker Compose

```bash
cp .env.example .env   # completar GEMINI_API_KEY
docker compose up -d --build
```

(En ese caso, apuntá el `proxy_pass` de nginx a `127.0.0.1:8000` igual que arriba.)

## 5. Verificación

```bash
curl -s https://sincro.gscod.com/api/health
# {"status":"ok","engine":"gemini_live","api_key_configured":true,...}

curl -s https://sincro.gscod.com/api/sessions
```

Abrí `https://sincro.gscod.com/` (audiencia), `/monitor` (producción) y
`/overlay?session=escenario-1&lang=translation` (OBS).

## Escalar varias sesiones

Todo corre en un proceso con tareas `asyncio`: agregá sesiones en `sessions.yaml`
o por `POST /api/sessions`. Para varias réplicas, mové el `EventBus` a Redis/NATS
(ver la sección *Multi-sesión y escalado* del README principal).
