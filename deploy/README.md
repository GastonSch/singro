# Deploy de Sincro en `sincro.gscod.com`

Opción rápida (LXC Debian, sin Docker) y opción Docker. El reverse proxy puede ser
**nginx** directo o **Nginx Proxy Manager (NPM)** con SSL.

## Opción rápida — script en el LXC Debian

Dentro del **LXC de la aplicación** (no el de NPM), como root:

```bash
apt-get update && apt-get install -y git
git clone https://github.com/GastonSch/singro /tmp/sincro-src
sudo GEMINI_API_KEY=AIza...tu_key... bash /tmp/sincro-src/deploy/install-lxc.sh
```

El script instala `ffmpeg`/`python3-venv`, clona el repo en `/opt/sincro`, crea el
venv, escribe `.env`, registra el servicio **systemd** `sincro` y lo arranca en
`0.0.0.0:8000`.

Verificar:

```bash
systemctl status sincro
curl -s http://127.0.0.1:8000/api/health
```

Si te olvidaste la key:

```bash
nano /opt/sincro/.env      # GEMINI_API_KEY=...
systemctl restart sincro
```

## Proxy + dominio

### Con Nginx Proxy Manager (NPM)

El NPM suele vivir en **otro contenedor**. Creá un *Proxy Host*:

- Domain: `sincro.gscod.com`
- Scheme: `http` · Forward Hostname: **IP del LXC de la app** · Forward Port: `8000`
- ✅ **Websockets Support** (imprescindible para los subtítulos en vivo)
- SSL: `Request a new certificate` / el que ya emitiste.

### Con nginx directo en el mismo host

```bash
sudo cp deploy/nginx-sincro.conf /etc/nginx/sites-available/sincro
sudo ln -sf /etc/nginx/sites-available/sincro /etc/nginx/sites-enabled/sincro
# DNS: A de sincro.gscod.com -> IP
sudo certbot --nginx -d sincro.gscod.com
sudo nginx -t && sudo systemctl reload nginx
```

El bloque `location /` trae el *upgrade* de WebSocket y `proxy_buffering off`.

## Opción Docker

```bash
cd /opt/sincro && cp .env.production.example .env   # completar GEMINI_API_KEY
docker compose up -d --build
```

Ajustá el `ports`/proxy para que nginx o NPM apunten al puerto `8000`.

## Verificación

```bash
curl -s https://sincro.gscod.com/api/health
curl -s https://sincro.gscod.com/api/sessions
```

- Audiencia: `https://sincro.gscod.com/`
- Monitor: `https://sincro.gscod.com/monitor`
- Overlay OBS: `https://sincro.gscod.com/overlay?session=escenario-1&lang=translation`

## Escalar varias sesiones

Agregá escenarios en `sessions.yaml` o con `POST /api/sessions`. Para varias
réplicas, mové el `EventBus` a Redis/NATS (ver *Multi-sesión y escalado* del
README principal).
