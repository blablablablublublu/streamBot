import os
import re
import requests
import logging
import asyncio
from datetime import datetime
import telebot
from flask import Flask, request, abort
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8041256909:AAGP38US7WMqPKP1FXCM59M_Abx0Q6nBtBk"
YOUTUBE_API_KEY = "AIzaSyB1GlNtoCX2d2BM67n20hFeOqJ51nMZvnM"
CHANNEL_ID = "UCcBeq64BydUvdA-kZsITNlg"
TIKTOK_USERNAME = "top_gamer_qq"
TELEGRAM_CHANNEL = "@testbotika12"

WEBHOOK_URL_BASE = os.getenv("WEBHOOK_URL", "https://streambot-yzkw.onrender.com")
WEBHOOK_ROUTE = "/webhook"
full_webhook_url = f"{WEBHOOK_URL_BASE}{WEBHOOK_ROUTE}?token={BOT_TOKEN}"

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
active_streams = {"YouTube": False, "TikTok": False, "Twitch": False}

# Utility function to create a new asyncio event loop if necessary
def ensure_asyncio_event_loop():
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

# Example YouTube check function (simplified for clarity)
async def check_youtube_live():
    try:
        url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&channelId={CHANNEL_ID}&eventType=live&type=video&key={YOUTUBE_API_KEY}"
        resp = requests.get(url)
        data = resp.json()
        if data.get("items"):
            video_id = data["items"][0]["id"]["videoId"]
            return True, f"https://www.youtube.com/watch?v={video_id}"
        return False, None
    except Exception as e:
        logger.error(f"Помилка перевірки YouTube: {e}")
        return False, None

# Flask webhook route
@app.route(WEBHOOK_ROUTE, methods=["POST"])
def webhook():
    ensure_asyncio_event_loop()  # Ensure there's an event loop ready
    if request.args.get("token") != BOT_TOKEN:
        abort(403)
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        asyncio.run(bot.process_new_updates([update]))  # Use asyncio.run for processing
        return "OK"
    else:
        abort(403)

@app.route("/")
def index():
    return "Бот працює через webhook!"

# Start Flask and Telegram bot
if __name__ == "__main__":
    ensure_asyncio_event_loop()
    bot.remove_webhook()
    if bot.set_webhook(url=full_webhook_url):
        logger.info(f"Webhook встановлено: {full_webhook_url}")
    else:
        logger.error(f"Не вдалося встановити webhook на: {full_webhook_url}")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))












