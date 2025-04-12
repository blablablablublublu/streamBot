import requests
import time
import asyncio
import json
import logging
from telegram.ext import Application

# Налаштування логування
logging.basicConfig(
    filename='bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 🔑 Дані
API_KEY = 'AIzaSyB1GlNtoCX2d2BM67n20hFeOqJ51nMZvnM'
CHANNEL_ID = 'UCcBeq64BydUvdA-kZsITNlg'
BOT_TOKEN = '8041256909:AAGjruzEE61q_H4R5zAwpTf53Peit37lqEg'
CHAT_ID = '@testbotika12'

app = Application.builder().token(BOT_TOKEN).build()

TIKTOK_USERNAME = 'top_gamer_qq'
TWITCH_CLIENT_ID = "твій_client_id"
TWITCH_ACCESS_TOKEN = "твій_access_token"
TWITCH_STREAMERS = ["top_gamer_qq", "dmqman"]

def save_status():
    status = {
        "was_live_youtube": was_live_youtube,
        "was_live_tiktok": was_live_tiktok,
        "was_live_twitch": was_live_twitch
    }
    with open("status.json", "w") as f:
        json.dump(status, f)

def load_status():
    try:
        with open("status.json", "r") as f:
            status = json.load(f)
        return status.get("was_live_youtube", False), status.get("was_live_tiktok", False), status.get("was_live_twitch", {streamer: False for streamer in TWITCH_STREAMERS})
    except FileNotFoundError:
        return False, False, {streamer: False for streamer in TWITCH_STREAMERS}

was_live_youtube, was_live_tiktok, was_live_twitch = load_status()

async def check_youtube():
    global was_live_youtube
    try:
        url = f'https://www.googleapis.com/youtube/v3/search?part=snippet&channelId={CHANNEL_ID}&type=video&eventType=live&key={API_KEY}'
        response = requests.get(url).json()

        if 'error' in response:
            logging.error(f"YouTube API помилка: {response['error']['message']}")
            return None, None

        items = response.get('items', [])
        if items:
            video_id = items[0]['id']['videoId']
            title = items[0]['snippet']['title']
            logging.info(f"YouTube: Знайдено стрім - {title}, {video_id}")
            return f'https://www.youtube.com/watch?v={video_id}', title
        else:
            logging.info("YouTube: Стріму немає")
    except Exception as e:
        logging.error(f"YouTube помилка: {e}")
    return None, None

async def check_tiktok():
    global was_live_tiktok
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        url = f'https://www.tiktok.com/@{TIKTOK_USERNAME}/live'
        response = requests.get(url, headers=headers)

        if response.status_code == 200 and '"isLive":true' in response.text:
            logging.info(f"TikTok: Стрім активний - {url}")
            return f'https://www.tiktok.com/@{TIKTOK_USERNAME}/live'
        else:
            logging.info("TikTok: Стріму немає")
            return None
    except Exception as e:
        logging.error(f"TikTok помилка: {e}")
        return None

async def check_twitch(streamer):
    global was_live_twitch
    try:
        url = f"https://api.twitch.tv/helix/streams?user_login={streamer}"
        headers = {
            "Authorization": f"Bearer {TWITCH_ACCESS_TOKEN}",
            "Client-Id": TWITCH_CLIENT_ID
        }
        response = requests.get(url, headers=headers)
        data = response.json()

        if data.get("data"):
            stream = data["data"][0]
            title = stream["title"]
            stream_url = f"https://www.twitch.tv/{streamer}"
            logging.info(f"Twitch: Стрім активний для {streamer} - {title}")
            return stream_url, title
        else:
            logging.info(f"Twitch: Стріму немає для {streamer}")
    except Exception as e:
        logging.error(f"Twitch помилка для {streamer}: {e}")
    return None, None

async def send_message(text):
    try:
        await app.bot.send_message(chat_id=CHAT_ID, text=text)
        logging.info(f"Повідомлення надіслано у Telegram: {text}")
    except Exception as e:
        logging.error(f"Помилка при відправці повідомлення у Telegram: {e}")

async def main():
    global was_live_youtube, was_live_tiktok, was_live_twitch
    logging.info("Бот запущений, чекаємо 30 секунд перед першою перевіркою...")
    await asyncio.sleep(30)

    while True:
        try:
            link, title = await check_youtube()
            if link and not was_live_youtube:
                await send_message(f"🔴 YouTube стрім почався!\n🎥 {title}\n👉 {link}")
                was_live_youtube = True
            elif link is None and was_live_youtube:
                was_live_youtube = False
            await asyncio.sleep(5)

            tiktok_live = await check_tiktok()
            if tiktok_live and not was_live_tiktok:
                await send_message(f"🎥 TikTok стрім почався!\n👉 {tiktok_live}")
                was_live_tiktok = True
            elif tiktok_live is None and was_live_tiktok:
                was_live_tiktok = False
            await asyncio.sleep(5)

            for streamer in TWITCH_STREAMERS:
                twitch_link, twitch_title = await check_twitch(streamer)
                if twitch_link and not was_live_twitch[streamer]:
                    await send_message(f"🔴 Twitch стрім почався!\n🎥 {twitch_title}\n👉 {twitch_link}")
                    was_live_twitch[streamer] = True
                elif twitch_link is None and was_live_twitch[streamer]:
                    was_live_twitch[streamer] = False
                await asyncio.sleep(2)

        except Exception as e:
            logging.error(f"Помилка у циклі main: {e}")

        save_status()
        await asyncio.sleep(50)

if __name__ == "__main__":
    asyncio.run(main())