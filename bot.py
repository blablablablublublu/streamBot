import re
import requests
import logging
import asyncio
import threading
import random
from datetime import datetime, timedelta
import telebot
from flask import Flask, request, abort
from bs4 import BeautifulSoup
import json
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
import pytz

# Налаштування логування
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфігурація
BOT_TOKEN = "8041256909:AAGP38US7WMqPKP1FXCM59M_Abx0Q6nBtBk"
YOUTUBE_API_KEY = "AIzaSyB1GlNtoCX2d2BM67n20hFeOqJ51nMZvnM"
CHANNEL_ID = "UCV1X9pvOdGnY5ZvmhifMKcw"
TIKTOK_USERNAME = "patron_wot"
TELEGRAM_CHANNEL = "@testbotika12"
TWITCH_CLIENT_ID = "your_twitch_client_id"
TWITCH_CLIENT_SECRET = "your_twitch_client_secret"
TWITCH_LOGIN = "dmqman"
WEBHOOK_URL_BASE = "https://streambot-yzkw.onrender.com"
WEBHOOK_ROUTE = "/webhook"
full_webhook_url = f"{WEBHOOK_URL_BASE}{WEBHOOK_ROUTE}?token={BOT_TOKEN}"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
]

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
active_streams = {"YouTube": False, "TikTok": False, "Twitch": False}

# Twitch токен кешування
twitch_token = None
token_expiry = None

ASYNC_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(ASYNC_LOOP)
threading.Thread(target=ASYNC_LOOP.run_forever, daemon=True).start()

def safe_async_send(coro, timeout=5):
    global ASYNC_LOOP
    try:
        if ASYNC_LOOP.is_closed():
            ASYNC_LOOP = asyncio.new_event_loop()
            threading.Thread(target=ASYNC_LOOP.run_forever, daemon=True).start()
        return asyncio.run_coroutine_threadsafe(coro, ASYNC_LOOP).result(timeout=timeout)
    except Exception as e:
        logger.error("safe_async_send: %s", e)
        return None

def in_grey_zone(tz="Europe/Kiev") -> bool:
    now = datetime.now(pytz.timezone(tz))
    return 2 <= now.hour < 12

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2), retry=retry_if_exception_type((requests.RequestException,)))
def make_request(url, headers=None, params=None):
    return requests.get(url, headers=headers, params=params, timeout=5)

async def check_youtube_live():
    """Перевірка стріму на YouTube через API, HTML або JSON-LD."""
    try:
        # Перевірка через YouTube API
        if YOUTUBE_API_KEY:
            url = (
                "https://www.googleapis.com/youtube/v3/search"
                f"?part=snippet&channelId={CHANNEL_ID}&eventType=live&type=video&key={YOUTUBE_API_KEY}"
            )
            resp = await asyncio.to_thread(make_request, url)
            data = resp.json()
            if data.get("items"):
                video_id = data["items"][0]["id"]["videoId"]
                return True, f"https://www.youtube.com/watch?v={video_id}"
        
        # Перевірка через HTML
        html_check = await check_youtube_live_html()
        if html_check[0]:
            return html_check

        # Перевірка через JSON-LD
        json_ld_check = await check_youtube_live_json()
        if json_ld_check[0]:
            return json_ld_check

        return False, None
    except Exception as e:
        logger.error("Помилка перевірки YouTube: %s", e)
        return False, None

async def check_youtube_live_html():
    """Запасний метод перевірки YouTube через HTML."""
    try:
        url = f"https://www.youtube.com/channel/{CHANNEL_ID}/live"
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        resp = await asyncio.to_thread(make_request, url, headers=headers)
        soup = BeautifulSoup(resp.text, 'html.parser')
        live_indicator = soup.find("meta", {"name": "description"})
        live_badge = soup.find("span", string=re.compile("LIVE", re.I))
        is_live = live_indicator and "live" in live_indicator["content"].lower() and live_badge is not None
        logger.info("YouTube HTML: is_live=%s", is_live)
        return is_live, url if is_live else None
    except Exception as e:
        logger.error("Помилка YouTube HTML: %s", e)
        return False, None

async def check_youtube_live_json():
    """Перевірка через JSON-LD скрипти."""
    try:
        url = f"https://www.youtube.com/channel/{CHANNEL_ID}/live"
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        resp = await asyncio.to_thread(make_request, url, headers=headers)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                if not script.string:
                    continue
                data = json.loads(script.string)
                if data.get("@type") == "VideoObject" and data.get("isLiveBroadcast") is True:
                    logger.info("✅ YouTube live знайдено через JSON-LD!")
                    return True, url
            except Exception as json_err:
                logger.debug("Не вдалося обробити JSON-LD для YouTube: %s", json_err)
                continue

        logger.info("❌ YouTube live не знайдено через JSON-LD.")
        return False, None
    except Exception as e:
        logger.error("Помилка YouTube JSON-LD: %s", e)
        return False, None

    except Exception as e:
        logger.error("Помилка перевірки YouTube: %s", e)
        return False, None

async def check_tiktok_live():
    try:
        url = f"https://www.tiktok.com/@{TIKTOK_USERNAME}/live"
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        resp = await asyncio.to_thread(make_request, url, headers=headers)

        if resp.status_code != 200:
            logger.error("TikTok повернув статус: %s", resp.status_code)
            return False, None

        soup = BeautifulSoup(resp.text, "html.parser")

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                if not script.string:
                    continue
                data = json.loads(script.string)
                publication = data.get("publication")
                if data.get("@type") == "VideoObject" and isinstance(publication, dict) and publication.get("isLiveBroadcast"):
                    logger.info("✅ TikTok live знайдено через JSON!")
                    return True, url
            except Exception as json_err:
                logger.debug("Не вдалося обробити скрипт JSON: %s", json_err)
                continue

        logger.info("❌ TikTok live не знайдено через JSON.")
        return False, None
    except Exception as e:
        logger.error("Помилка перевірки TikTok: %s", e)
        return False, None

async def get_twitch_token():
    global twitch_token, token_expiry
    if twitch_token and token_expiry and token_expiry > datetime.now():
        return twitch_token
    try:
        token_url = "https://id.twitch.tv/oauth2/token"
        params = {
            "client_id": TWITCH_CLIENT_ID,
            "client_secret": TWITCH_CLIENT_SECRET,
            "grant_type": "client_credentials"
        }
        token_resp = await asyncio.to_thread(requests.post, token_url, params=params, timeout=5)
        data = token_resp.json()
        twitch_token = data.get("access_token")
        token_expiry = datetime.now() + timedelta(seconds=data.get("expires_in", 3600))
        return twitch_token
    except Exception as e:
        logger.error("Помилка отримання токена Twitch: %s", e)
        return None

async def check_twitch_live():
    try:
        if TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET:
            access_token = await get_twitch_token()
            if not access_token:
                return False, None
            headers = {"Client-ID": TWITCH_CLIENT_ID, "Authorization": f"Bearer {access_token}"}
            stream_resp = await asyncio.to_thread(
                make_request,
                "https://api.twitch.tv/helix/streams",
                headers=headers,
                params={"user_login": TWITCH_LOGIN}
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
            logger.info("Сіра зона – перевірки вимкнено.")
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
                    safe_async_send(bot.send_message(TELEGRAM_CHANNEL, message))
                    logger.info("Сповіщення відправлено для %s", platform)
                except Exception as err:
                    logger.error("Помилка надсилання для %s: %s", platform, err)
            elif not is_live and active_streams[platform]:
                active_streams[platform] = False
        await asyncio.sleep(300)

async def verify_webhook():
    while True:
        try:
            webhook_info = bot.get_webhook_info()
            if not webhook_info.url or webhook_info.url != full_webhook_url:
                bot.set_webhook(url=full_webhook_url)
                logger.info("Webhook відновлено: %s", full_webhook_url)
        except Exception as e:
            logger.error("Помилка перевірки вебхука: %s", e)
        await asyncio.sleep(3600)

def start_background_tasks():
    safe_async_send(check_streams_and_notify_async())
    safe_async_send(verify_webhook())

@bot.message_handler(commands=['start'])
def handle_start(message):
    safe_async_send(bot.reply_to(message, "Бот працює! Автоматичний моніторинг стрімів увімкнено."))

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
                try:
                    await bot.send_message(TELEGRAM_CHANNEL, f"🔴 {platform} стрім активний: {link}")
                except Exception as err:
                    logger.error("Помилка надсилання в канал для %s: %s", platform, err)
        response = "🔴 Активні стріми:\n" + "\n".join(results) if results else "Зараз стрімів немає."
        await bot.reply_to(message, response)
    safe_async_send(process())

@bot.message_handler(content_types=['text'])
def handle_text(message):
    safe_async_send(bot.reply_to(message, f"Привіт, ти написав: {message.text}"))

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    async def process_callback():
        await call.answer()
    safe_async_send(process_callback())

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
    if bot.set_webhook(url=full_webhook_url):
        logger.info("Webhook встановлено: %s", full_webhook_url)
    else:
        logger.error("Не вдалося встановити webhook на: %s", full_webhook_url)
    start_background_tasks()
    port = 5000
    app.run(host="0.0.0.0", port=port)


















