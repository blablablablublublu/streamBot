import os
import re
import requests
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Налаштування логування
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфігураційні змінні
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")   # Замість None введіть реальний API-ключ
CHANNEL_ID = "UCcBeq64BydUvdA-kZsITNlg"            # YouTube Channel ID

TIKTOK_USERNAME = "top_gamer_qq"
TELEGRAM_CHANNEL = "@testbotika12"                 # Telegram канал для повідомлень

TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
TWITCH_LOGIN = "dmqman"

# Зберігання активних стрімів
active_streams = {"YouTube": False, "TikTok": False, "Twitch": False}

def is_in_grey_zone():
    """
    Перевірка, чи перебуваємо в "сірій зоні".
    Сірі зони: з 2:00 до 12:00.
    """
    current_hour = asyncio.get_event_loop().time() // 3600 % 24  # Отримуємо поточний час
    return 2 <= current_hour <= 12

# Функції перевірки платформ
async def check_youtube_live():
    """
    Перевірка YouTube API або запасний метод (HTML).
    """
    try:
        if YOUTUBE_API_KEY:  # Використовує API, якщо ключ встановлено
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
            # Резервний варіант: пошук live через HTML-сторінку
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
    Використовує регулярний вираз для пошуку live у HTML.
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
    Перевіряє Twitch API або інший спосіб (HTML-сторінка).
    """
    try:
        if TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET:
            # Отримуємо access token
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

            # Отримуємо статус стріму
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

async def check_streams_and_notify(application):
    """
    Функція для періодичної перевірки стрімів та відправки повідомлень.
    """
    while True:
        if is_in_grey_zone():
            logger.info("Перевірки припинено через сірі зони.")
            await asyncio.sleep(300)
            continue

        for platform, check_function in [("YouTube", check_youtube_live),
                                         ("TikTok", check_tiktok_live),
                                         ("Twitch", check_twitch_live)]:
            is_live, link = await check_function()
            if is_live and not active_streams[platform]:  # Якщо стрім активний і ще не повідомляли
                active_streams[platform] = True
                message = f"🔴 {platform}: {link}"
                await application.bot.send_message(chat_id=TELEGRAM_CHANNEL, text=message)
            elif not is_live and active_streams[platform]:  # Якщо стрім завершився
                active_streams[platform] = False

        await asyncio.sleep(300)  # Інтервал перевірки – 5 хвилин

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обробник команди /start
    """
    await update.message.reply_text("Бот працює! Автоматичний моніторинг стрімів увімкнено.")

async def checkstreams_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /checkstreams: ручна перевірка.
    """
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
    """
    Головна функція для запуску бота.
    """
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("checkstreams", checkstreams_command))

    # Запускаємо моніторинг у фоні
    asyncio.create_task(check_streams_and_notify(application))

    application.run_polling()

if __name__ == "__main__":
    main()




