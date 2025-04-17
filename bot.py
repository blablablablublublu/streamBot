import os
import re
import requests
import logging
import asyncio
import threading
from datetime import datetime
import telebot
from flask import Flask, request, abort
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# ----- Налаштування логування -----
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ----- Конфігурація (з вашими даними) -----
BOT_TOKEN = "8041256909:AAGP38US7WMqPKP1FXCM59M_Abx0Q6nBtBk"
YOUTUBE_API_KEY = "AIzaSyB1GlNtoCX2d2BM67n20hFeOqJ51nMZvnM"
CHANNEL_ID = "UCcBeq64BydUvdA-kZsITNlg"
TIKTOK_USERNAME = "top_gamer_qq"
TELEGRAM_CHANNEL = "@testbotika12"

# Twitch налаштування (якщо потрібні)
TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
TWITCH_LOGIN = "dmqman"

WEBHOOK_URL_BASE = os.getenv("WEBHOOK_URL", "https://streambot-yzkw.onrender.com")
WEBHOOK_ROUTE = "/webhook"
full_webhook_url = f"{WEBHOOK_URL_BASE}{WEBHOOK_ROUTE}?token={BOT_TOKEN}"

# ----- Ініціалізація Flask та Telegram -----
app = Flask(__name__)
# Зверніть увагу: ми використовуємо парсинг як HTML
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
active_streams = {"YouTube": False, "TikTok": False, "Twitch": False}

# ----- Глобальний event loop для асинхронних операцій -----
ASYNC_LOOP = asyncio.new_event_loop()
# Запускаємо event loop у окремому потоці, щоб він був завжди доступний
threading.Thread(target=ASYNC_LOOP.run_forever, daemon=True).start()


def in_grey_zone() -> bool:
    now = datetime.now()
    return 2 <= now.hour < 12


# ----- Функції перевірки стрімів (асинхронні) -----
async def check_youtube_live():
    try:
        if YOUTUBE_API_KEY:
            url = (
                "https://www.googleapis.com/youtube/v3/search"
                f"?part=snippet&channelId={CHANNEL_ID}&eventType=live&type=video&key={YOUTUBE_API_KEY}"
            )
            resp = await asyncio.to_thread(requests.get, url, timeout=5)
            data = resp.json()
            if data.get("items"):
                video_id = data["items"][0]["id"]["videoId"]
                return True, f"https://www.youtube.com/watch?v={video_id}"
        return await check_youtube_live_html()
    except Exception as e:
        logger.error("Помилка перевірки YouTube: %s", e)
        return False, None


async def check_youtube_live_html():
    try:
        url = f"https://www.youtube.com/channel/{CHANNEL_ID}/live"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = await asyncio.to_thread(requests.get, url, headers=headers, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        live_indicator = soup.find("meta", {"name": "description"})
        if live_indicator and "live" in live_indicator["content"].lower():
            return True, url
        return False, None
    except Exception as e:
        logger.error("Помилка перевірки YouTube через HTML: %s", e)
        return False, None


async def check_tiktok_live():
    try:
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")  # без графічного інтерфейсу
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        url = f"https://www.tiktok.com/@{TIKTOK_USERNAME}"
        driver.get(url)
        html_content = driver.page_source
        soup = BeautifulSoup(html_content, 'html.parser')
        live_indicator = soup.find("div", {"class": "live-indicator"})
        driver.quit()
        if live_indicator:
            return True, url
        return False, None
    except Exception as e:
        logger.error("Помилка перевірки TikTok через Selenium: %s", e)
        return False, None


async def check_twitch_live():
    try:
        if TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET:
            token_url = "https://id.twitch.tv/oauth2/token"
            params = {
                "client_id": TWITCH_CLIENT_ID,
                "client_secret": TWITCH_CLIENT_SECRET,
                "grant_type": "client_credentials"
            }
            token_resp = await asyncio.to_thread(requests.post, token_url, params=params, timeout=5)
            access_token = token_resp.json().get("access_token")
            if not access_token:
                return False, None
            headers = {"Client-ID": TWITCH_CLIENT_ID, "Authorization": f"Bearer {access_token}"}
            stream_resp = await asyncio.to_thread(
                requests.get,
                "https://api.twitch.tv/helix/streams",
                headers=headers,
                params={"user_login": TWITCH_LOGIN},
                timeout=5
            )
            if stream_resp.json().get("data"):
                return True, f"https://www.twitch.tv/{TWITCH_LOGIN}"
        return False, None
    except Exception as e:
        logger.error("Помилка перевірки Twitch: %s", e)
        return False, None


async def check_streams_and_notify_async():
    while True:
        if in_grey_zone():
            logger.info("Перевірки відключені (сіра зона).")
            await asyncio.sleep(300)
            continue
        for platform, check_func in [
            ("YouTube", check_youtube_live),
            ("TikTok", check_tiktok_live),
            ("Twitch", check_twitch_live)
        ]:
            is_live, link = await check_func()
            if is_live and not active_streams[platform]:
                active_streams[platform] = True
                message = f"🔴 {platform} стрім почався: {link}"
                try:
                    # Використовуємо global event loop (ASYNC_LOOP) для надсилання повідомлень
                    asyncio.run_coroutine_threadsafe(
                        bot.send_message(TELEGRAM_CHANNEL, message),
                        ASYNC_LOOP
                    ).result(timeout=10)
                    logger.info("Уведомлення відправлено для %s", platform)
                except Exception as err:
                    logger.error("Помилка надсилання для %s: %s", platform, err)
            elif not is_live and active_streams[platform]:
                active_streams[platform] = False
        await asyncio.sleep(300)


def start_background_task():
    # Використовуємо глобальний event loop для запуску фонової coroutine
    asyncio.run_coroutine_threadsafe(check_streams_and_notify_async(), ASYNC_LOOP)


# ----- Telegram bot handlers (асинхронні) -----
@bot.message_handler(commands=['start'])
def handle_start(message):
    # Викликаємо асинхронно через run_coroutine_threadsafe
    future = asyncio.run_coroutine_threadsafe(
        bot.reply_to(message, "Бот працює! Автоматичний моніторинг стрімів увімкнено."),
        ASYNC_LOOP
    )
    try:
        future.result(timeout=10)
    except Exception as e:
        logger.error("Помилка у handle_start: %s", e)


@bot.message_handler(commands=['checkstreams'])
def handle_check_streams(message):
    async def process():
        results = []
        for platform, check_func in [
            ("YouTube", check_youtube_live),
            ("TikTok", check_tiktok_live),
            ("Twitch", check_twitch_live)
        ]:
            is_live, link = await check_func()
            if is_live:
                results.append(f"{platform}: {link}")
        if results:
            response = "🔴 Активні стріми:\n" + "\n".join(results)
        else:
            response = "Зараз стрімів немає."
        await bot.reply_to(message, response)
    future = asyncio.run_coroutine_threadsafe(process(), ASYNC_LOOP)
    try:
        future.result(timeout=10)
    except Exception as e:
        logger.error("Помилка у handle_check_streams: %s", e)


@bot.message_handler(content_types=['text'])
def handle_text(message):
    future = asyncio.run_coroutine_threadsafe(
        bot.reply_to(message, f"Привіт, ти написав: {message.text}"),
        ASYNC_LOOP
    )
    try:
        future.result(timeout=10)
    except Exception as e:
        logger.error("Помилка у handle_text: %s", e)


# ----- Flask webhook маршрут -----
@app.route(WEBHOOK_ROUTE, methods=['POST'])
def webhook():
    if request.args.get("token") != BOT_TOKEN:
        abort(403)
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        try:
            # Виконуємо обробку оновлення через наш глобальний event loop
            future = asyncio.run_coroutine_threadsafe(
                bot.process_new_updates([update]), ASYNC_LOOP
            )
            future.result(timeout=5)
        except Exception as e:
            logger.error("Помилка обробки update: %s", e)
        return ""
    else:
        abort(403)


@app.route("/")
def index():
    return "Бот працює через webhook!"


# ----- Запуск додатку -----
if __name__ == "__main__":
    # Видаляємо існуючий webhook та встановлюємо новий
    bot.remove_webhook()
    if bot.set_webhook(url=full_webhook_url):
        logger.info("Webhook встановлено: %s", full_webhook_url)
    else:
        logger.error("Не вдалося встановити webhook на: %s", full_webhook_url)
    # Запускаємо фонове завдання перевірки стрімів
    start_background_task()
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)













