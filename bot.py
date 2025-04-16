import os
import re
import requests
import logging
import threading
import time
from datetime import datetime
import telebot
from flask import Flask, request, abort

# Налаштування логування
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфігураційні змінні
BOT_TOKEN = os.getenv("BOT_TOKEN", "8041256909:AAGP38US7WMqPKP1FXCM59M_Abx0Q6nBtBk")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "AIzaSyB1GlNtoCX2d2BM67n20hFeOqJ51nMZvnM")
CHANNEL_ID = "UCcBeq64BydUvdA-kZsITNlg"  # YouTube Channel ID
TIKTOK_USERNAME = "top_gamer_qq"
TELEGRAM_CHANNEL = os.getenv("TELEGRAM_CHANNEL", "@testbotika12")
TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")  # Якщо є, інакше залишається None
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
TWITCH_LOGIN = "dmqman"

# WEBHOOK URL (публічний URL вашого додатку, наприклад, Render)
WEBHOOK_URL_BASE = os.getenv("WEBHOOK_URL", "https://streambot-yzkw.onrender.com")
WEBHOOK_URL_PATH = f"/{BOT_TOKEN}"

if not WEBHOOK_URL_BASE:
    logger.error("WEBHOOK_URL не задано. Будь ласка, задайте публічний URL вашого додатку.")
    exit(1)

# Ініціалізуємо Flask-додаток та бота
app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)

# Словник для відстеження активних стрімів (щоб уникнути дублювання повідомлень)
active_streams = {
    "YouTube": False,
    "TikTok": False,
    "Twitch": False
}

def in_grey_zone() -> bool:
    """
    Повертає True, якщо теперішній час знаходиться в "сірій зоні" (з 2:00 до 12:00)
    для економії запитів.
    """
    now = datetime.now()
    return 2 <= now.hour < 12

def check_youtube_live():
    """
    Перевіряє наявність стріму на YouTube.
    Якщо API-ключ заданий, використовує YouTube Data API; інакше – перевірка через HTML.
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
    Перевіряє наявність стріму в TikTok, шукаючи у HTML паттерн "liveStatus".
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
    Перевіряє наявність стріму на Twitch через API (за наявності client_id та client_secret).
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
    Якщо виявлено новий стрім (і повідомлення ще не надсилалося), надсилає повідомлення
    в Telegram-канал. Якщо стрім завершився – прапорець скидається.
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
                    logger.info("Уведомлення відправлено для %s", platform)
                except Exception as err:
                    logger.error("Помилка надсилання для %s: %s", platform, err)
            elif not is_live and active_streams[platform]:
                active_streams[platform] = False
        time.sleep(300)

def start_background_task():
    """
    Запускає фонову задачу перевірки стрімів у окремому потоці.
    """
    thread = threading.Thread(target=check_streams_and_notify)
    thread.daemon = True
    thread.start()

# ================================
# ОБРОБНИКИ ПОВІДОМЛЕНЬ (ДЕКОРАТОРИ)
# Всі обробники мають бути розміщені в кінці файлу, перед запуском Flask-сервера.
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
    bot.reply_to(message, f"Привіт, ти написав: {message.text}")

# ================================
# WEBHOOK ROUTING для Flask
# ================================

@app.route(WEBHOOK_URL_PATH, methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        try:
            update = telebot.types.Update.de_json(json_string)
            bot.process_new_updates([update])
        except Exception as e:
            logger.error("Помилка обробки оновлення: %s", e)
        return ""
    else:
        abort(403)

@app.route("/")
def index():
    return "Бот працює через webhook!"

# ================================
# Запуск фонового монітора та налаштування webhook
# ================================
if __name__ == "__main__":
    start_background_task()

    # Видаляємо старий webhook і встановлюємо новий
    bot.remove_webhook()
    full_webhook_url = f"{WEBHOOK_URL_BASE}{WEBHOOK_URL_PATH}"
    if bot.set_webhook(url=full_webhook_url):
        logger.info("Webhook встановлено: %s", full_webhook_url)
    else:
        logger.error("Не вдалося встановити webhook на: %s", full_webhook_url)

    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)









