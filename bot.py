import os
import requests
import logging
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

# Налаштування логування
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Дані для бота та каналів
BOT_TOKEN = os.getenv("BOT_TOKEN", "8041256909:AAGP38US7WMqPKP1FXCM59M_Abx0Q6nBtBk")
YOUTUBE_API_KEY = os.getenv("AIzaSyB1GlNtoCX2d2BM67n20hFeOqJ51nMZvnM")  # Повинно бути встановлено
CHANNEL_ID = "UCcBeq64BydUvdA-kZsITNlg"  # YouTube Channel ID

TIKTOK_USERNAME = "top_gamer_qq"

TELEGRAM_CHANNEL = "@testbotika12"  # Telegram канал для розсилки повідомлень

# Дані для Twitch (отримайте з вашого акаунту Twitch developers)
TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
TWITCH_LOGIN = "dmqman"  # логін Twitch каналу з посилання https://www.twitch.tv/dmqman

def check_youtube_live():
    """
    Перевірка, чи веде YouTube канал прямий ефір.
    Використовується YouTube Data API.
    """
    if not YOUTUBE_API_KEY:
        logger.error("Не встановлено YOUTUBE_API_KEY")
        return False, None
    url = ("https://www.googleapis.com/youtube/v3/search"
           f"?part=snippet&channelId={CHANNEL_ID}&eventType=live&type=video&key={YOUTUBE_API_KEY}")
    try:
        resp = requests.get(url)
        data = resp.json()
        if data.get("items"):
            video_id = data["items"][0]["id"]["videoId"]
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            logger.info("YouTube live знайдено: %s", video_url)
            return True, video_url
        else:
            logger.info("YouTube live не знайдено.")
            return False, None
    except Exception as e:
        logger.error("Помилка при перевірці YouTube: %s", e)
        return False, None

def check_tiktok_live():
    """
    Перевірка, чи веде TikTok користувач стрім.
    Це демонстраційна реалізація. Для надійної перевірки потрібен більш стабільний метод або API.
    """
    try:
        url = f"https://www.tiktok.com/@{TIKTOK_USERNAME}"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            # Проста перевірка: шукаємо слово "live" у вмісті сторінки
            if "live" in resp.text.lower():
                live_url = f"https://www.tiktok.com/@{TIKTOK_USERNAME}"
                logger.info("TikTok live знайдено: %s", live_url)
                return True, live_url
            else:
                logger.info("TikTok live не знайдено.")
                return False, None
        else:
            logger.error("TikTok повернув статус: %s", resp.status_code)
            return False, None
    except Exception as e:
        logger.error("Помилка при перевірці TikTok: %s", e)
        return False, None

def check_twitch_live():
    """
    Перевірка, чи веде Twitch канал прямий ефір.
    Використовує Twitch API для отримання даних про користувача та стрім.
    """
    if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET:
        logger.error("Не встановлено TWITCH_CLIENT_ID або TWITCH_CLIENT_SECRET")
        return False, None
    try:
        # Отримати access token
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

        # Отримати дані користувача за логіном
        user_resp = requests.get("https://api.twitch.tv/helix/users", headers=headers, params={"login": TWITCH_LOGIN}, timeout=5)
        user_data = user_resp.json()
        if "data" not in user_data or not user_data["data"]:
            logger.error("Користувача Twitch не знайдено.")
            return False, None
        user_id = user_data["data"][0]["id"]

        # Перевірити статус стріму
        stream_resp = requests.get("https://api.twitch.tv/helix/streams", headers=headers, params={"user_id": user_id}, timeout=5)
        stream_data = stream_resp.json()
        if stream_data.get("data"):
            live_url = f"https://www.twitch.tv/{TWITCH_LOGIN}"
            logger.info("Twitch live знайдено: %s", live_url)
            return True, live_url
        else:
            logger.info("Twitch live не знайдено.")
            return False, None
    except Exception as e:
        logger.error("Помилка при перевірці Twitch: %s", e)
        return False, None

def check_streams() -> dict:
    """
    Функція перевіряє стріми на всіх платформах та повертає словник з результатами.
    """
    results = {}
    youtube_live, youtube_link = check_youtube_live()
    results["YouTube"] = {"live": youtube_live, "link": youtube_link}

    tiktok_live, tiktok_link = check_tiktok_live()
    results["TikTok"] = {"live": tiktok_live, "link": tiktok_link}

    twitch_live, twitch_link = check_twitch_live()
    results["Twitch"] = {"live": twitch_live, "link": twitch_link}

    return results

def checkstreams_command(update: Update, context: CallbackContext):
    """
    Обробник команди /checkstreams.
    Якщо серед платформ є активний стрім – відсилаємо повідомлення у вказаний Telegram канал,
    інакше – повідомляємо користувачу (приватно).
    """
    streams = check_streams()
    message_live = "Зараз йдуть стріми:\n"
    any_live = False
    for platform, details in streams.items():
        if details["live"]:
            any_live = True
            message_live += f"{platform}: {details['link']}\n"

    if any_live:
        # Надіслати повідомлення у публічний канал, де бот є модератором
        context.bot.send_message(chat_id=TELEGRAM_CHANNEL, text=message_live)
        update.message.reply_text("Стріми відправлено до публічного каналу.")
    else:
        # Надіслати повідомлення лише користувачу, який викликав команду
        update.message.reply_text("Наразі стрімів немає.")

def main():
    """
    Основна функція – ініціалізація бота та запуск опитувальника (polling).
    """
    updater = Updater(BOT_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("checkstreams", checkstreams_command))

    updater.start_polling()
    logger.info("Бот запущено.")
    updater.idle()

if __name__ == '__main__':
    main()
