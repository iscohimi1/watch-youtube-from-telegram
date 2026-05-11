import os
import re
import asyncio
import subprocess
import logging
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, CallbackQueryHandler
)
import yt_dlp

# ─── CONFIG ──────────────────────────────────────────────────────────────────
BOT_TOKEN   = "YOUR_BOT_TOKEN_HERE"   # <- paste your token
DOWNLOAD_DIR = Path("downloads")
MAX_PART_MB  = 45                      # Telegram limit is 50 MB; stay safe
MAX_PART_B   = MAX_PART_MB * 1024 * 1024
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

YOUTUBE_RE = re.compile(
    r"(https?://)?(www\.)?"
    r"(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)"
    r"[\w\-]+"
)


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def sanitize(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", name)[:60]


def get_duration(path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True
    )
    return float(result.stdout.strip() or 0)


def split_video(video_path: str, uid: str) -> list[str]:
    """Split a video into ≤45 MB parts using ffmpeg stream copy."""
    size   = os.path.getsize(video_path)
    dur    = get_duration(video_path)
    parts  = max(2, int(size / MAX_PART_B) + 1)
    seg_dur = dur / parts
    output_parts = []

    for i in range(parts):
        start    = i * seg_dur
        out_path = str(DOWNLOAD_DIR / f"{uid}_part{i+1}.mp4")
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "quiet",
            "-i", video_path,
            "-ss", str(start), "-t", str(seg_dur),
            "-c", "copy", out_path
        ], check=True)
        output_parts.append(out_path)

    return output_parts


def cleanup(*paths):
    for p in paths:
        try:
            if p and os.path.exists(p):
                os.remove(p)
        except Exception:
            pass


# ─── DOWNLOAD ────────────────────────────────────────────────────────────────

def download_video(url: str, uid: str) -> tuple[str, dict]:
    """Download a YouTube video and return (file_path, info_dict)."""
    DOWNLOAD_DIR.mkdir(exist_ok=True)
    out_template = str(DOWNLOAD_DIR / f"{uid}.%(ext)s")

    ydl_opts = {
        "format": (
            "bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]"
            "/best[ext=mp4][height<=720]"
            "/best[ext=mp4]/best"
        ),
        "merge_output_format": "mp4",
        "outtmpl": out_template,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        path = ydl.prepare_filename(info).rsplit(".", 1)[0] + ".mp4"

    return path, info


# ─── HANDLERS ────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 *YouTube to Telegram Bot*\n\n"
        "Just send me any YouTube link and I'll download and send the video "
        "right here — no app switching needed.\n\n"
        "If the video is large I'll split it into parts automatically. "
        "Files are deleted from my server right after sending! 🔒\n\n"
        "Supports: `youtube.com/watch?v=...`, `youtu.be/...`, Shorts",
        parse_mode="Markdown",
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *How to use:*\n\n"
        "1. Copy a YouTube video link\n"
        "2. Paste it here and send\n"
        "3. Wait — the bot downloads, compresses if needed, and sends\n"
        "4. Large videos are split into ≤45 MB parts\n"
        "5. Everything is deleted from the server after sending ✅\n\n"
        "*Tips:*\n"
        "• Works with Shorts too\n"
        "• Videos are capped at 720p to keep sizes manageable\n"
        "• Very long videos (1h+) may take a few minutes",
        parse_mode="Markdown",
    )


async def handle_link(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if not YOUTUBE_RE.search(text):
        await update.message.reply_text(
            "❌ That doesn't look like a YouTube link.\n"
            "Please send a valid `youtube.com` or `youtu.be` URL.",
            parse_mode="Markdown",
        )
        return

    uid       = f"{update.effective_user.id}_{update.message.message_id}"
    video_path = None
    parts      = []

    # ── Status message ──
    status = await update.message.reply_text("⏳ Fetching video info…")

    try:
        # ── Download ──
        await status.edit_text("📥 Downloading… this may take a moment")
        video_path, info = await asyncio.get_event_loop().run_in_executor(
            None, download_video, text, uid
        )

        title    = sanitize(info.get("title", "video"))
        duration = info.get("duration", 0)
        mins, secs = divmod(int(duration), 60)
        size_mb  = os.path.getsize(video_path) / (1024 * 1024)

        await status.edit_text(
            f"✅ Downloaded: *{title}*\n"
            f"⏱ Duration: {mins}m {secs}s  |  💾 Size: {size_mb:.1f} MB\n\n"
            f"📤 Sending…",
            parse_mode="Markdown",
        )

        # ── Send ──
        if size_mb <= MAX_PART_MB:
            with open(video_path, "rb") as f:
                await update.message.reply_video(
                    f,
                    caption=f"🎬 {title}",
                    supports_streaming=True,
                    read_timeout=120,
                    write_timeout=120,
                )
        else:
            await status.edit_text(
                f"✂️ Video is {size_mb:.0f} MB — splitting into parts…"
            )
            parts = await asyncio.get_event_loop().run_in_executor(
                None, split_video, video_path, uid
            )
            total = len(parts)
            for i, part in enumerate(parts, 1):
                part_size = os.path.getsize(part) / (1024 * 1024)
                await status.edit_text(
                    f"📤 Sending part {i}/{total} ({part_size:.1f} MB)…"
                )
                with open(part, "rb") as f:
                    await update.message.reply_video(
                        f,
                        caption=f"🎬 {title}  —  Part {i}/{total}",
                        supports_streaming=True,
                        read_timeout=120,
                        write_timeout=120,
                    )
                cleanup(part)

        await status.edit_text("✅ Done! Enjoy the video 🎉\n🗑 File deleted from server.")

    except yt_dlp.utils.DownloadError as e:
        log.error("yt-dlp error: %s", e)
        await status.edit_text(
            "❌ Couldn't download this video.\n"
            "It might be age-restricted, private, or region-blocked."
        )
    except subprocess.CalledProcessError:
        await status.edit_text("❌ Failed to split the video. ffmpeg error.")
    except Exception as e:
        log.exception("Unexpected error")
        await status.edit_text(f"❌ Unexpected error:\n`{e}`", parse_mode="Markdown")
    finally:
        cleanup(video_path, *parts)


# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help",  cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))

    log.info("Bot is running…")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
