import re
import requests
import logging
import asyncio
import threading
import random
from datetime import datetime
import telebot
from flask import Flask, request, abort
from bs4 import BeautifulSoup
import json
import pytz

# Конфігурація
BOT_TOKEN = "8041256909:AAGP38US7WMqPKP1FXCM59M_Abx0Q6nBtBk"
YOUTUBE_API_KEY = "AIzaSyB1GlNtoCX2d2BM67n20hFeOqJ51nMZvnM"
CHANNEL_ID = "UCV1X9pvOdGnY5ZvmhifMKcw"
TIKTOK_USERNAME = "patron_wot"
TELEGRAM_CHANNEL = "@testbotika12"
WEBHOOK_URL_BASE = "https://streambot-yzkw.onrender.com"
WEBHOOK_ROUTE = "/webhook"
FULL_WEBHOOK_URL = f"{WEBHOOK_URL_BASE}{WEBHOOK_ROUTE}?token={BOT_TOKEN}"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
]

# Логування
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask + Telebot
app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# Async loop
ASYNC_LOOP = asyncio.new_event_loop()
threading.Thread(target=ASYNC_LOOP.run_forever, daemon=True).start()

active_streams = {"YouTube": False, "TikTok": False}

def safe_async_send(coro, timeout=10):
    try:
        return asyncio.run_coroutine_threadsafe(coro, ASYNC_LOOP).result(timeout=timeout)
    except Exception as e:
        logger.error("safe_async_send error: %s", e)
        return None

def in_grey_zone(tz="Europe/Kiev") -> bool:
    now = datetime.now(pytz.timezone(tz))
    return 2 <= now.hour < 12

def make_request(url, headers=None, params=None):
    return requests.get(url, headers=headers, params=params, timeout=5)

async def check_youtube_live():
    try:
        url = (
            "https://www.googleapis.com/youtube/v3/search"
            f"?part=snippet&channelId={CHANNEL_ID}&eventType=live&type=video&key={YOUTUBE_API_KEY}"
        )
        resp = await asyncio.to_thread(make_request, url)
        data = resp.json()
        if data.get("items"):
            video_id = data["items"][0]["id"]["videoId"]
            return True, f"https://www.youtube.com/watch?v={video_id}"

        return await check_youtube_live_html()
    except Exception as e:
        logger.error("check_youtube_live error: %s", e)
        return False, None

async def check_youtube_live_html():
    try:
        url = f"https://www.youtube.com/channel/{CHANNEL_ID}/live"
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        resp = await asyncio.to_thread(make_request, url, headers=headers)
        soup = BeautifulSoup(resp.text, 'html.parser')
        badge = soup.find("span", string=re.compile("LIVE", re.I))
        meta = soup.find("meta", {"name": "description"})
        is_live = badge is not None and meta and "live" in meta.get("content", "").lower()
        return (is_live, url if is_live else None)
    except Exception as e:
        logger.error("check_youtube_live_html error: %s", e)
        return False, None

async def check_tiktok_live():
    try:
        url = f"https://www.tiktok.com/@{TIKTOK_USERNAME}/live"
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        resp = await asyncio.to_thread(make_request, url, headers=headers)
        if resp.status_code != 200:
            return False, None

        soup = BeautifulSoup(resp.text, "html.parser")
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                if not script.string:
                    continue
                data = json.loads(script.string)
                publication = data.get("publication")
                if data.get("@type") == "VideoObject" and isinstance(publication, dict) and publication.get("isLiveBroadcast"):
                    return True, url
            except Exception:
                continue
        return False, None
    except Exception as e:
        logger.error("check_tiktok_live error: %s", e)
        return False, None

async def monitor_streams():
    while True:
        if in_grey_zone():
            await asyncio.sleep(300)
            continue
        for platform, check_func in [("YouTube", check_youtube_live), ("TikTok", check_tiktok_live)]:
            is_live, link = await check_func()
            if is_live and not active_streams[platform]:
                active_streams[platform] = True
                safe_async_send(bot.send_message(TELEGRAM_CHANNEL, f"🔴 {platform} стрім почався: {link}"))
            elif not is_live and active_streams[platform]:
                active_streams[platform] = False
        await asyncio.sleep(300)

@app.before_first_request
def setup():
    try:
        bot.remove_webhook()
        bot.set_webhook(url=FULL_WEBHOOK_URL)
        safe_async_send(monitor_streams())
    except Exception as e:
        logger.error("setup error: %s", e)

@bot.message_handler(commands=['start'])
def handle_start(message):
    bot.reply_to(message, "Бот працює! Моніторинг стрімів увімкнено.")

@bot.message_handler(commands=['checkstreams'])
def handle_check(message):
    async def check():
        results = []
        for platform, check_func in [("YouTube", check_youtube_live), ("TikTok", check_tiktok_live)]:
            is_live, link = await check_func()
            if is_live:
                results.append(f"{platform}: {link}")
        reply = "🔴 Активні стріми:\n" + "\n".join(results) if results else "Зараз стрімів немає."
        await bot.send_message(message.chat.id, reply)
    safe_async_send(check())

@app.route(WEBHOOK_ROUTE, methods=["POST"])
def webhook():
    if request.args.get("token") != BOT_TOKEN:
        abort(403)
    if request.headers.get("content-type") == "application/json":
        update = telebot.types.Update.de_json(request.data.decode("utf-8"))
        safe_async_send(bot.process_new_updates([update]))
        return ""
    abort(403)

@app.route("/")
def index():
    return "Бот працює через Webhook!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)


















