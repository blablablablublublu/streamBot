import logging
import asyncio
import threading
import requests
import json
from datetime import datetime
from bs4 import BeautifulSoup
import telebot
from flask import Flask, request, abort
import pytz

# ---------------- Налаштування логування ----------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------------- Конфігурація ----------------
BOT_TOKEN = "8041256909:AAGP38US7WMqPKP1FXCM59M_Abx0Q6nBtBk"
TIKTOK_USERNAME = "sh0kerix_youtube"
TELEGRAM_CHANNEL = "@testbotika12"
WEBHOOK_URL_BASE = "https://streambot-yzkw.onrender.com"
WEBHOOK_ROUTE = "/webhook"
full_webhook_url = f"{WEBHOOK_URL_BASE}{WEBHOOK_ROUTE}?token={BOT_TOKEN}"

# ---------------- Ініціалізація Flask і Telegram Bot ----------------
app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ---------------- Async event loop ----------------
ASYNC_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(ASYNC_LOOP)
threading.Thread(target=ASYNC_LOOP.run_forever, daemon=True).start()


def safe_async_send(coro, timeout=10):
    try:
        return asyncio.run_coroutine_threadsafe(coro, ASYNC_LOOP).result(timeout=timeout)
    except Exception as e:
        logger.error("safe_async_send exception: %s", e)
        raise


def in_grey_zone(tz="Europe/Kiev") -> bool:
    now = datetime.now(pytz.timezone(tz))
    return 2 <= now.hour < 12


def make_request(url, headers=None, params=None):
    return requests.get(url, headers=headers, params=params, timeout=5)


async def check_tiktok_live():
    try:
        url = f"https://www.tiktok.com/@{TIKTOK_USERNAME}/live"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = await asyncio.to_thread(make_request, url, headers=headers)
        soup = BeautifulSoup(resp.text, "html.parser")

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                if data.get("@type") == "VideoObject" and data.get("publication", {}).get("isLiveBroadcast"):
                    logger.info("✅ TikTok live знайдено через JSON!")
                    return True, url
            except Exception as json_err:
                logger.debug("Не вдалося обробити скрипт JSON: %s", json_err)
                continue

        logger.info("❌ TikTok live не знайдено через JSON.")
        return False, None
    except Exception as e:
        logger.error("Помилка перевірки TikTok через JSON: %s", e)
        return False, None


async def check_and_notify():
    while True:
        if in_grey_zone():
            logger.info("Сіра зона – перевірки вимкнено.")
            await asyncio.sleep(300)
            continue

        is_live, link = await check_tiktok_live()
        if is_live:
            msg = f"🔴 TikTok стрім активний: {link}"
            try:
                safe_async_send(bot.send_message(TELEGRAM_CHANNEL, msg))
                logger.info("Сповіщення відправлено")
            except Exception as e:
                logger.error("Помилка надсилання сповіщення: %s", e)
        await asyncio.sleep(300)


@bot.message_handler(commands=['start'])
def handle_start(message):
    safe_async_send(bot.reply_to(message, "Бот працює! TikTok перевірка активна."))


@app.route(WEBHOOK_ROUTE, methods=["POST"])
def webhook():
    if request.args.get("token") != BOT_TOKEN:
        abort(403)
    if request.headers.get("content-type") == "application/json":
        json_string = request.get_data().decode("utf-8")
        update = telebot.types.Update.de_json(json_string)
        try:
            safe_async_send(bot.process_new_updates([update]))
        except Exception as e:
            logger.error("Помилка обробки update: %s", e)
        return ""
    else:
        abort(403)

@app.route("/")
def index():
    return "Бот працює через webhook!"

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=full_webhook_url)
    safe_async_send(check_and_notify())
    app.run(host="0.0.0.0", port=5000)


















