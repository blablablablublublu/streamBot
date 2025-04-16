import os
import re
import requests
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Налаштування логування
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфігураційні змінні
BOT_TOKEN = os.getenv("BOT_TOKEN", "8041256909:AAGP38US7WMqPKP1FXCM59M_Abx0Q6nBtBk")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")   # Встановіть змінну, якщо потрібно
CHANNEL_ID = "UCcBeq64BydUvdA-kZsITNlg"            # YouTube Channel ID

TIKTOK_USERNAME = "top_gamer_qq"
TELEGRAM_CHANNEL = "@testbotika12"                 # Telegram канал для повідомлень

# Дані для Twitch
TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
TWITCH_LOGIN = "dmqman"                            # Логін Twitch каналу

def check_youtube_live():
    """
    Перевіряє, чи веде YouTube канал прямий ефір за допомогою YouTube Data API.
    """
    if not YOUTUBE_API_KEY:
        logger.error("YOUTUBE_API_KEY не встановлено.")
        return False, None

    url = (
        "https://www.googleapis.com/youtube/v3/search"
        f"?part=snippet&channelId={CHANNEL_ID}&eventType=live&type=video&key={YOUTUBE_API_KEY}"
    )
    try:
        resp = requests.get(url, timeout=5)
        data = resp.json()
        if data.get("items"):
            video_info = data["items"][0]["id"]
            video_id = video_info.get("videoId")
            if video_id:
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                logger.info("YouTube live знайдено: %s", video_url)
                return True, video_url
        logger.info("YouTube live не знайдено")
        return False, None
    except Exception as e:
        logger.error("Помилка при перевірці YouTube: %s", e)
        return False, None

def check_tiktok_live():
    """
    Перевіряє, чи веде TikTok користувач стрім, шукаючи паттерн "liveStatus": true.
    Зауваження: HTML-розмітка TikTok може змінюватися, тому при потребі коригуйте регулярний вираз.
    """
    try:
        url = f"https://www.tiktok.com/@{TIKTOK_USERNAME}"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            # Шукаємо паттерн '"liveStatus": true' або '"liveStatus":false'
            match = re.search(r'"liveStatus"\s*:\s*(true|false)', resp.text, re.IGNORECASE)
            if match:
                live_status = match.group(1).lower() == "true"
                if live_status:
                    live_url = f"https://www.tiktok.com/@{TIKTOK_USERNAME}"
                    logger.info("TikTok live знайдено: %s", live_url)
                    return True, live_url
        logger.info("TikTok live не знайдено")
        return False, None
    except Exception as e:
        logger.error("Помилка при перевірці TikTok: %s", e)
        return False, None

def check_twitch_live():
    """
    Перевіряє, чи веде Twitch канал прямий ефір за допомогою Twitch API.
    """
    if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET:
        logger.error("TWITCH_CLIENT_ID або TWITCH_CLIENT_SECRET не встановлено.")
        return False, None

    try:
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
            logger.error("Не вдалося отримати Twitch access token.")
            return False, None

        headers = {
            "Client-ID": TWITCH_CLIENT_ID,
            "Authorization": f"Bearer {access_token}"
        }

        # Отримуємо дані користувача за логіном
        user_resp = requests.get(
            "https://api.twitch.tv/helix/users", headers=headers, params={"login": TWITCH_LOGIN}, timeout=5
        )
        user_data = user_resp.json()
        if "data" not in user_data or not user_data["data"]:
            logger.error("Користувача Twitch не знайдено.")
            return False, None
        user_id = user_data["data"][0]["id"]

        # Перевіряємо стан стріму
        stream_resp = requests.get(
            "https://api.twitch.tv/helix/streams", headers=headers, params={"user_id": user_id}, timeout=5
        )
        stream_data = stream_resp.json()
        if stream_data.get("data"):
            live_url = f"https://www.twitch.tv/{TWITCH_LOGIN}"
            logger.info("Twitch live знайдено: %s", live_url)
            return True, live_url
        logger.info("Twitch live не знайдено")
        return False, None
    except Exception as e:
        logger.error("Помилка при перевірці Twitch: %s", e)
        return False, None

def check_streams() -> dict:
    """
    Перевіряє наявність live-стрімів на всіх платформах.
    """
    results = {}
    
    youtube_live, youtube_link = check_youtube_live()
    results["YouTube"] = {"live": youtube_live, "link": youtube_link}
    
    tiktok_live, tiktok_link = check_tiktok_live()
    results["TikTok"] = {"live": tiktok_live, "link": tiktok_link}
    
    twitch_live, twitch_link = check_twitch_live()
    results["Twitch"] = {"live": twitch_live, "link": twitch_link}
    
    return results

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обробник команди /start для перевірки, що бот працює.
    """
    await update.message.reply_text("Бот працює! Відправте /checkstreams для перевірки стрімів.")

async def checkstreams_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обробник команди /checkstreams: перевіряє наявність live-стрімів.
    Якщо є активні стріми – надсилає повідомлення до публічного каналу,
    інакше – відправляє відповідь користувачу.
    """
    logger.info("Отримано команду /checkstreams від користувача %s", update.effective_user.username)
    streams = check_streams()
    logger.info("Результати перевірки стрімів: %s", streams)
    
    message_live = "Зараз йдуть стріми:\n"
    any_live = False
    for platform, details in streams.items():
        if details["live"]:
            any_live = True
            message_live += f"{platform}: {details['link']}\n"
    
    if any_live:
        await context.bot.send_message(chat_id=TELEGRAM_CHANNEL, text=message_live)
        await update.message.reply_text("Стріми відправлено до публічного каналу.")
    else:
        await update.message.reply_text("Наразі стрімів немає.")

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Додаємо обробники команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("checkstreams", checkstreams_command))

    logger.info("Бот запущено.")
    # Запуск роботи бота через polling
    application.run_polling()

if __name__ == '__main__':
    main()



