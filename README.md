# ⚔️ Aeternum-Sentinel

> **Your all-in-one Discord companion for New World — with automation, a sleek web dashboard and first-class Docker support.**

![Python](https://img.shields.io/badge/python-3.11-blue?logo=python)
![License](https://img.shields.io/badge/license-MIT-green)
![Docker](https://img.shields.io/badge/docker-ready-blue?logo=docker)

---

## ✨ Features

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

### 🔧 Utility Commands
- `/ping` – latency check.  
- `/web` – returns dashboard URL.

### 💾 Persistent Configuration
- JSON per-guild files under `data/` — **no database needed**.

---

## 🚀 Quick Start

### Option A: Docker Compose (recommended) 🐳

```bash
# 1) Get the code
$ git clone https://github.com/<your-org>/aeternum-sentinel.git
$ cd aeternum-sentinel

# 2) Copy env template & fill in your secrets
$ cp .env.example .env   # edit with your Discord credentials

# 3) Fire it up
$ docker compose up -d
```

`docker-compose.yml` (included in the repo) – minimal example:

```yaml
version: "3.8"
services:
  sentinel:
    image: ghcr.io/<your-org>/aeternum-sentinel:latest
    env_file:
      - .env
    volumes:
      - ./data:/app/data
    ports:
      - "8000:8000"   # Web UI
```

After the containers start, open **http://localhost:8000** ➜ **Login** ➜ configure away! ✨

### Option B: Local Development 🖥️

```bash
poetry install          # or pip install -r requirements.txt
cp .env.example .env    # add your Discord credentials
poetry run sentinel     # or python -m sentinel.cli
```

---

## 🛠️ Contributing
Pull requests are welcome! For major changes, please open an issue first to discuss what you would like to change.

## 📄 License
MIT – see `LICENSE` for details.
