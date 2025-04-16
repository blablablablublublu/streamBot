import os
import re
import requests
import logging
import threading
import time
from datetime import datetime
import telebot

# Налаштування логування
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфігураційні змінні
# Використовується новий токен, отриманий від BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN", "8041256909:AAGP38US7WMqPKP1FXCM59M_Abx0Q6nBtBk")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")  # Якщо є API-ключ, інакше залиште пустим
CHANNEL_ID = "UCcBeq64BydUvdA-kZsITNlg"           # YouTube Channel ID
TIKTOK_USERNAME = "top_gamer_qq"
TELEGRAM_CHANNEL = os.getenv("TELEGRAM_CHANNEL", "@testbotika12")  # Канал для повідомлень
TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
TWITCH_LOGIN = "dmqman"

# Ініціалізуємо бота
bot = telebot.TeleBot(BOT_TOKEN)

# Словник для відстеження активних стрімів (щоб уникнути спаму)
active_streams = {
    "YouTube": False,
    "TikTok": False,
    "Twitch": False
}

def in_grey_zone() -> bool:
    """
    Повертає True, якщо поточний час знаходиться в "сірій зоні" (з 2:00 до 12:00),
    коли перевірки відключені для економії запитів.
    """
    now = datetime.now()
    return 2 <= now.hour < 12

def check_youtube_live():
    """
    Перевіряє, чи веде YouTube канал стрім.
    Якщо заданий API-ключ, використовує YouTube Data API, інакше – резервний метод через HTML.
    """
    try:
        if YOUTUBE_API_KEY:
            url = ("https://www.googleapis.com/youtube/v3/search"
                   f"?part=snippet&channelId={CHANNEL_ID}&eventType=live&type=video&key={YOUTUBE_API_KEY}")
            resp = requests.get(url, timeout=5)
            data = resp.json()
            if data.get("items"):
                video_id = data["items"][0]["id"]["videoId"]
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                return True, video_url
        else:
            url = f"https://www.youtube.com/channel/{CHANNEL_ID}/live"
            resp = requests.get(url, timeout=5)
            if "isLiveBroadcast" in resp.text:
                return True, url
        return False, None
    except Exception as e:
        logger.error("Помилка перевірки YouTube: %s", e)
        return False, None

def check_tiktok_live():
    """
    Перевіряє, чи веде TikTok користувач стрім, шукаючи паттерн "liveStatus" у HTML-розмітці.
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
        logger.error("Помилка перевірки TikTok: %s", e)
        return False, None

def check_twitch_live():
    """
    Перевіряє наявність стріму на Twitch через API (при наявності client_id і client_secret).
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
        logger.error("Помилка перевірки Twitch: %s", e)
        return False, None

def check_streams_and_notify():
    """
    Фонова функція, яка кожні 5 хвилин перевіряє стріми на всіх платформах.
    Якщо знайдено новий стрім (тобто, повідомлення ще не надсилались),
    надсилає повідомлення в Telegram-канал та встановлює відповідну позначку.
    Якщо стрім завершився – позначку скидає.
    Перевірки не виконуються у "сірій зоні" (з 2:00 до 12:00).
    """
    while True:
        if in_grey_zone():
            logger.info("Перевірки відключені (сіра зона).")
            time.sleep(300)
            continue

        for platform, check_func in [
            ("YouTube", check_youtube_live),
            ("TikTok", check_tiktok_live),
            ("Twitch", check_twitch_live)
        ]:
            is_live, link = check_func()
            if is_live and not active_streams[platform]:
                active_streams[platform] = True
                message = f"🔴 {platform} стрім почався: {link}"
                try:
                    bot.send_message(TELEGRAM_CHANNEL, message)
                    logger.info("Надіслано повідомлення для %s", platform)
                except Exception as err:
                    logger.error("Помилка надсилання для %s: %s", platform, err)
            elif not is_live and active_streams[platform]:
                active_streams[platform] = False
        time.sleep(300)

def start_background_task():
    """
    Запускає фонову задачу перевірки стрімів в окремому потоці.
    """
    thread = threading.Thread(target=check_streams_and_notify)
    thread.daemon = True
    thread.start()

# ================================
# ОБРОБНИКИ ПОВІДОМЛЕНЬ (ДЕКОРАТОРИ)
# Розташовуємо їх слідом за всіма іншими визначеннями функцій, безпосередньо перед bot.polling()
# ================================

@bot.message_handler(commands=['start'])
def handle_start(message):
    bot.reply_to(message, "Бот працює! Автоматичний моніторинг стрімів увімкнено.")

@bot.message_handler(commands=['checkstreams'])
def handle_check_streams(message):
    results = []
    for platform, check in [
        ("YouTube", check_youtube_live),
        ("TikTok", check_tiktok_live),
        ("Twitch", check_twitch_live)
    ]:
        is_live, link = check()
        if is_live:
            results.append(f"{platform}: {link}")
    if results:
        response = "🔴 Активні стріми:\n" + "\n".join(results)
    else:
        response = "Зараз стрімів немає."
    bot.reply_to(message, response)

@bot.message_handler(content_types=['text'])
def handle_text(message):
    # Приклад обробки текстових повідомлень
    bot.reply_to(message, f"Привіт, ти написав: {message.text}")

# ================================
# Запуск фонового монітора та polling
# ================================
start_background_task()
bot.polling(none_stop=True)








