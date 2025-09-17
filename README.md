# ⚔️ Aeternum-Sentinel

> **Your all-in-one Discord companion for New World — with automation, AI-powered image analysis, a sleek web dashboard and first-class Docker support.**

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
- `/update_icons` – update everyone's role icons
- `/sheet_sync` – sync members to Google Sheets
- `/changelog` – show latest changelog entry
- `/review` – send custom review message
- `/vod` – share VOD form link
- `/analyze_image` – manually analyze images for usernames _(NEW!)_
- `/create_team_stats` – create team statistics tables _(NEW!)_

### 🔍 AI-Powered Image Analysis _(NEW!)_
- ✅ **Pfeffi AI Integration:** Automatically extract usernames from uploaded images
- ✅ **Thread Monitoring:** Auto-analyze images uploaded to configured Discord threads  
- ✅ **Manual Analysis:** Use `/analyze_image` command for on-demand processing
- ✅ **Multi-Channel Support:** Monitor multiple channels with different values
- ✅ **Payout Tracking:** Automatically track participants in Google Sheets
- ✅ **Role-Based Permissions:** Configure which roles can confirm analysis results
- ✅ **Multi-Language Support:** Dynamic worksheet names in multiple languages
- ✅ **Username Confirmation:** Interactive confirmation system with edit capabilities

### 📊 Team Statistics Analysis _(NEW!)_
- ✅ **Multi-Image Processing:** Analyze team stats, composition, and enemy statistics
- ✅ **Structured Tables:** Create formatted tables in Google Sheets
- ✅ **Reference Names System:** Use composition as reference for accurate name matching
- ✅ **Smart Name Mapping:** AI-powered matching of misspelled names
- ✅ **Manual Corrections:** Edit player names with interactive modals
- ✅ **Auto-Solve Feature:** Automatically resolve name inconsistencies
- ✅ **Re-Analysis:** Handle missing players with intelligent re-processing

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

### 🎭 Reaction Roles _(NEW!)_
- ✅ **Interactive Setup:** Configure roles via web dashboard
- ✅ **Custom Emojis:** Use server emojis or Unicode characters
- ✅ **Role Management:** Users get/remove roles by reacting
- ✅ **Rich Embeds:** Customizable title, description, and role descriptions
- ✅ **Live Updates:** Edit and republish messages seamlessly

### 🌐 Web Dashboard
- ✅ **FastAPI + Jinja templates + SCSS styling.**  
- ✅ **Discord OAuth2 login & multi-guild selector.**  
- ✅ **Comprehensive Management:** Role-icons, voice channels, Google Sheets, and more
- ✅ **Image Analysis Configuration:** Full setup for AI features _(NEW!)_
- ✅ **Reaction Roles Designer:** Visual configuration interface _(NEW!)_
- ✅ **Health endpoint (`/health`) for orchestration.**

### 📊 Advanced Google Sheets Integration
- ✅ **Service-Account Authentication:** No OAuth flow needed
- ✅ **Per-Guild Configuration:** Manage via dashboard
- ✅ **Smart Username Mapping:** Right-click cells for vertical/horizontal mapping _(NEW!)_
- ✅ **Advanced Rule Columns:** Multi-rule system with flexible behaviors _(NEW!)_
  - **Multiple Rules per Column:** Create complex logic chains
  - **Flexible Behaviors:** First-match or combine-all strategies
  - **String & Boolean Modes:** Custom text or true/false values
  - **Visual Feedback:** Green highlights show rule columns in preview
- ✅ **Member Filtering:** Sync all members or filter by specific roles _(NEW!)_
- ✅ **Automatic Payout Tracking:** AI-extracted usernames → Google Sheets _(NEW!)_
- ✅ **Team Statistics Tables:** Structured game statistics analysis _(NEW!)_

### 💬 Custom Messages & Links
- ✅ **Review System:** Custom `/review` messages per server
- ✅ **VOD Integration:** Share VOD form links via `/vod` command
- ✅ **Per-Guild Configuration:** All settings managed via web dashboard

### 💾 Persistent Configuration
- **JSON per-guild files under `data/` — no database needed.**
- **Hot-reload configuration changes.**
- **Automatic backups and migration support.**

---

## 🚀 Quick Start (Docker Compose) 🐳

Create a `docker-compose.yml` like the one below and start the stack:

```bash
docker compose up -d
```

`docker-compose.yml` example (includes every available environment variable):

```yaml
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

      #===  Web server (defaults shown)
      HOST: "0.0.0.0"                           # default "0.0.0.0"
      PORT: "8000"                              # default 8000

      # === TLS (optional) ===
      # Provide absolute or container-internal paths to your certificate files.
      # When both are present **and** the files exist, Sentinel starts via HTTPS.
      SSL_CERTFILE: "/certs/fullchain.pem"      # no default
      SSL_KEYFILE: "/certs/privkey.pem"        # no default

      # === Google Sheets (optional) ===
      # Absolute path within the container to the service account JSON.
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

## 🔧 Configuration Guide

### 🔍 Setting up Image Analysis

1. **Get a Gemini API Key:** Visit [Google AI Studio](https://aistudio.google.com/app/apikey)
2. **Configure via Web Dashboard:**
   - Enable image analysis
   - Set monitored channels with values
   - Configure Gemini API key
   - Set up payout tracking (optional)
   - Configure role-based permissions

### 📊 Google Sheets Integration

1. **Create a Service Account:** Follow [Google's guide](https://developers.google.com/sheets/api/guides/authorizing#ServiceAccount)
2. **Share your Sheet:** Give the service account email edit access
3. **Configure via Dashboard:**
   - Set Sheet ID
   - Configure username mapping (right-click cells)
   - Set up rule columns for automated data entry
   - Configure member filtering options

### 🎭 Reaction Roles Setup

1. **Access Web Dashboard → Reaction Roles section**
2. **Configure:**
   - Select target channel
   - Add emoji → role mappings
   - Customize embed title and descriptions
   - Publish the message

---

## 🆕 What's New in Latest Version

### 🎯 **AI-Powered Features**
- **Image Analysis with Gemini AI:** Automatically extract usernames from screenshots
- **Team Statistics Processing:** Create structured tables from game statistics
- **Smart Name Matching:** AI resolves name inconsistencies and typos
- **Multi-Language Support:** Dynamic worksheet names in 5+ languages

### 🔧 **Enhanced Google Sheets**  
- **Advanced Rule System:** Multiple rules per column with flexible behaviors
- **Visual Preview:** Live highlighting of mapped areas and rule columns
- **Automated Payout Tracking:** From image analysis directly to spreadsheets
- **Member Role Filtering:** Sync only specific roles or all members

### 🎨 **Improved Web Interface**
- **Dark Theme:** Easy on the eyes with Discord-like styling
- **Interactive Configuration:** Context menus and live previews
- **Comprehensive Management:** All features accessible via web dashboard

---

## 🛠️ Contributing
Pull requests are welcome! For major changes, please open an issue first to discuss what you would like to change.

## 📄 License
MIT – see `LICENSE` for details.
