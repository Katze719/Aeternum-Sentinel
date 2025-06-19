# ⚔️ Aeternum-Sentinel

> **Your all-in-one Discord companion for New World — with automation, a sleek web dashboard and first-class Docker support.**

![Python](https://img.shields.io/badge/python-3.12-blue?logo=python)
![License](https://img.shields.io/badge/license-MIT-green)
![Docker](https://img.shields.io/badge/docker-ready-blue?logo=docker)

**🪄 Quickest Start – Invite the Bot**

[➕ **Add Aeternum-Sentinel to your server**](https://discord.com/oauth2/authorize?client_id=1383522700244287630)

---

## ✨ Features

### 🤖 All Slash Commands
- `/ping` – latency check.  
- `/web` – returns dashboard URL.
- `/cleanup_voice` – clean up empty voice channels
- `/update_icons` – update everyones icons

### 🎙️ Temporary Voice Channels
- ✅ Designate one or more **generator** channels.  
- ✅ Bot auto-creates a private voice channel and moves the user in.  
- ✅ Custom naming via `{username}` / `{number}` placeholders.  
- ✅ Auto-cleanup of empty channels or manual `/cleanup_voice`.

### 🏷️ Role Icons in Nicknames
- ✅ Map roles to custom emojis & priorities.  
- ✅ Nicknames updated live on role change.  
- ✅ Format fully configurable (`{username} {icons}`).  
- ✅ Slash command `/update_icons` to refresh everyone.

### 🌐 Web Dashboard
- ✅ FastAPI + Jinja templates + SCSS styling.  
- ✅ Discord OAuth2 login & multi-guild selector.  
- ✅ Manage role-icons, voice-channel generators, command prefix & more.  
- ✅ Health endpoint (`/health`) for orchestration.

### 📊 Google-Sheets Sync
* **Service-Account-basierte Authentifizierung** (kein OAuth-Flow nötig).  
* Pro-Guild konfigurierbar über das Dashboard.  
* Slash-Command `/sheet_sync` überträgt Mitglieder-Listen nach Google Sheets.

### 💾 Persistent Configuration
- JSON per-guild files under `data/` — **no database needed**.

---

## 🚀 Quick Start (Docker Compose) 🐳

Create a `docker-compose.yml` like the one below and start the stack:

```bash
docker compose up -d
```

`docker-compose.yml` example (includes every available environment variable):

```yaml
version: "3.8"
services:
  sentinel:
    image: ghcr.io/katze719/aeternum-sentinel:latest
    restart: unless-stopped

    environment:
      # === Required ===
      DISCORD_TOKEN: "your-bot-token"           # (required)
      DISCORD_CLIENT_ID: "123456789012345678"   # (required)
      DISCORD_CLIENT_SECRET: "your-oauth-client-secret" # (required)

      # === Optional (defaults shown) ===
      COMMAND_PREFIX: "!"                       # default "!"
      OAUTH_REDIRECT_URI: "http://localhost:8000/callback"  # default shown

      # Web server
      HOST: "0.0.0.0"                           # default "0.0.0.0"
      PORT: "8000"                              # default 8000

      # === TLS (optional) ===
      # Provide absolute or container-internal paths to your certificate files.
      # When both are present **and** the files exist, Sentinel starts via HTTPS.
      SSL_CERTFILE: "/certs/fullchain.pem"      # no default
      SSL_KEYFILE: "/certs/privkey.pem"        # no default

      # === Google Sheets (optional) ===
      # Absolute Pfad innerhalb des Containers zur Service-Account-JSON.
      # Diese Datei muss *nicht* in der Web-UI eingegeben werden.
      GOOGLE_CREDENTIALS_PATH: "/secrets/google.json"

    volumes:
      - ./data:/app/data
      # Mount directory that contains your certificate and key (paths must match above!)
      - ./certs:/certs:ro  # read-only mount for TLS assets
      # Mount Service-Account-Key read-only:
      - ./secrets/google.json:/secrets/google.json:ro
    ports:
      - "8000:8000"   # FastAPI web UI
```

Once the container is running, open **http://localhost:8000** in your browser, log in with Discord and start configuring! ✨

---

## 🛠️ Contributing
Pull requests are welcome! For major changes, please open an issue first to discuss what you would like to change.

## 📄 License
MIT – see `LICENSE` for details.
