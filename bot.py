import os
import re
import requests
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Налаштування логування
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфігураційні змінні
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")  # Вкажіть, якщо є API-ключ
CHANNEL_ID = "UCcBeq64BydUvdA-kZsITNlg"           # YouTube Channel ID

TIKTOK_USERNAME = "top_gamer_qq"
TELEGRAM_CHANNEL = "@testbotika12"                # Telegram канал для повідомлень

TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
TWITCH_LOGIN = "dmqman"

# Словник для відстеження стану стрімів по платформах
active_streams = {"YouTube": False, "TikTok": False, "Twitch": False}


def in_grey_zone() -> bool:
    """
    Повертає True, якщо поточний час у "сірій зоні" перевірок (з 2:00 до 12:00).
    """
    now = datetime.now()
    return 2 <= now.hour < 12


# Функції перевірки платформ

async def check_youtube_live():
    """
    Перевіряє YouTube API або, при відсутності API-ключа, спираючись на HTML-сторінку.
    """
    try:
        if YOUTUBE_API_KEY:
            url = (
                "https://www.googleapis.com/youtube/v3/search"
                f"?part=snippet&channelId={CHANNEL_ID}&eventType=live&type=video&key={YOUTUBE_API_KEY}"
            )
            resp = requests.get(url, timeout=5)
            data = resp.json()
            if data.get("items"):
                video_id = data["items"][0]["id"]["videoId"]
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                return True, video_url
        else:
            # Резервний варіант – HTML перевірка
            url = f"https://www.youtube.com/channel/{CHANNEL_ID}/live"
            resp = requests.get(url, timeout=5)
            if "isLiveBroadcast" in resp.text:
                return True, url
        return False, None
    except Exception as e:
        logger.error("Помилка при перевірці YouTube: %s", e)
        return False, None


async def check_tiktok_live():
    """
    Перевіряє наявність стріму в TikTok через пошук регулярним виразом паттерна "liveStatus".
    """
    try:
        url = f"https://www.tiktok.com/@{TIKTOK_USERNAME}"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=5)
        match = re.search(r'"liveStatus"\s*:\s*(true|false)', resp.text, re.IGNORECASE)
        if match and match.group(1).lower() == "true":
            return True, url
        return False, None
    except Exception as e:
        logger.error("Помилка при перевірці TikTok: %s", e)
        return False, None


async def check_twitch_live():
    """
    Перевіряє Twitch через API або альтернативний метод, якщо API доступний.
    """
    try:
        if TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET:
            token_url = "https://id.twitch.tv/oauth2/token"
            params = {
                "client_id": TWITCH_CLIENT_ID,
                "client_secret": TWITCH_CLIENT_SECRET,
                "grant_type": "client_credentials"
            }
            token_resp = requests.post(token_url, params=params, timeout=5)
            token_data = token_resp.json()
            access_token = token_data.get("access_token")
            if not access_token:
                return False, None

            headers = {
                "Client-ID": TWITCH_CLIENT_ID,
                "Authorization": f"Bearer {access_token}"
            }
            stream_resp = requests.get(
                "https://api.twitch.tv/helix/streams",
                headers=headers,
                params={"user_login": TWITCH_LOGIN},
                timeout=5
            )
            stream_data = stream_resp.json()
            if stream_data.get("data"):
                live_url = f"https://www.twitch.tv/{TWITCH_LOGIN}"
                return True, live_url
        return False, None
    except Exception as e:
        logger.error("Помилка при перевірці Twitch: %s", e)
        return False, None


# Фонова функція, яка запускається кожні 5 хвилин за допомогою job_queue
async def check_streams_and_notify(context: ContextTypes.DEFAULT_TYPE):
    """
    Фонова задача, яка перевіряє зазначені платформи та надсилає повідомлення
    в Telegram-канал лише на початку стріму. Якщо стрім вже активний, нове повідомлення не
    надсилається до його завершення. Також, якщо поточний час належить "сірій зоні",
    перевірки не виконуються.
    """
    if in_grey_zone():
        logger.info("Перевірки відключено в сірій зоні.")
        return

    # Перевірка кожної платформи
    for platform, check_function in [
        ("YouTube", check_youtube_live),
        ("TikTok", check_tiktok_live),
        ("Twitch", check_twitch_live)
    ]:
        is_live, link = await check_function()
        # Якщо стрім активний, але ми ще не повідомляли – надсилаємо повідомлення
        if is_live and not active_streams[platform]:
            active_streams[platform] = True
            message = f"🔴 {platform} стрім почався: {link}"
            await context.bot.send_message(chat_id=TELEGRAM_CHANNEL, text=message)
            logger.info("Надіслано повідомлення про %s", platform)
        # Якщо стрім не активний, скидаємо стан
        elif not is_live and active_streams[platform]:
            active_streams[platform] = False


# Обробники команд для ручної перевірки

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот працює! Автоматичний моніторинг стрімів увімкнено.")


async def checkstreams_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    results = {
        "YouTube": await check_youtube_live(),
        "TikTok": await check_tiktok_live(),
        "Twitch": await check_twitch_live()
    }
    message = "🔴 **Результати перевірки:**\n"
    any_live = False
    for platform, (is_live, link) in results.items():
        if is_live:
            any_live = True
            message += f"{platform}: {link}\n"
    if not any_live:
        message = "Наразі стрімів немає."
    await update.message.reply_text(message)


def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("checkstreams", checkstreams_command))

    # Використовуємо job_queue для періодичного запуску перевірок кожні 5 хвилин
    application.job_queue.run_repeating(check_streams_and_notify, interval=300, first=0)

    logger.info("Бот запущено.")
    application.run_polling()


if __name__ == "__main__":
    main()





