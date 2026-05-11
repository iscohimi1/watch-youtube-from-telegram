# 🎬 YouTube → Telegram Bot

A Telegram bot that downloads any YouTube video and sends it directly to the user.
Large videos are automatically split into ≤45 MB parts. All files are deleted after sending.

---

## ⚙️ Requirements

- Python 3.11+
- `ffmpeg` installed on your system
- A Telegram Bot Token (from [@BotFather](https://t.me/BotFather))

---

## 🚀 Setup (step by step)

### 1. Install ffmpeg

**Ubuntu / Debian:**
```bash
sudo apt update && sudo apt install ffmpeg -y
```

**macOS:**
```bash
brew install ffmpeg
```

**Windows:**
Download from https://ffmpeg.org/download.html and add to PATH.

---

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

---

### 3. Get your Bot Token

1. Open Telegram → search [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the steps
3. Copy the token (looks like `123456:ABC-DEF...`)

---

### 4. Configure the bot

Open `bot.py` and replace the token on line 14:
```python
BOT_TOKEN = "123456:ABC-DEF..."   # <- your token here
```

---

### 5. Run the bot

```bash
python bot.py
```

---

## 📱 How to use

| User action | Bot response |
|---|---|
| Send `/start` | Welcome message |
| Send `/help` | Usage instructions |
| Send a YouTube link | Downloads & sends the video |

- Videos are capped at **720p** to keep file sizes manageable
- Videos larger than 45 MB are **split into parts** automatically
- All files are **deleted from the server** immediately after sending

---

## 🌐 Supported URL formats

```
https://www.youtube.com/watch?v=dQw4w9WgXcQ
https://youtu.be/dQw4w9WgXcQ
https://www.youtube.com/shorts/abc123
```

---

## ☁️ Deploy on a server (optional, 24/7)

**Using systemd (Linux VPS):**

Create `/etc/systemd/system/ytbot.service`:
```ini
[Unit]
Description=YouTube Telegram Bot
After=network.target

[Service]
WorkingDirectory=/home/youruser/youtube_bot
ExecStart=/usr/bin/python3 bot.py
Restart=always
User=youruser

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable ytbot
sudo systemctl start ytbot
sudo systemctl status ytbot
```

---

## 📌 Notes

- Very long videos (1h+) may take several minutes to download
- Age-restricted or private videos cannot be downloaded
- To keep yt-dlp up to date: `pip install -U yt-dlp`
