# ===== IMPORTS =====
from groq import Groq
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler
import speech_recognition as sr
from pydub import AudioSegment
import asyncio
from telegram.constants import ChatAction
import os
import requests
from ddgs import DDGS
import yt_dlp
import logging

logging.basicConfig(level=logging.ERROR)

# ===== API KEYS =====
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")

client = Groq(api_key=GROQ_API_KEY)

user_memory = {}
user_mode = {}

# ===== PERSONALITY COMMANDS =====
async def set_funny(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_mode[update.message.from_user.id] = "funny"
    await update.message.reply_text("😂 Funny mode ON!")

async def set_teacher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_mode[update.message.from_user.id] = "teacher"
    await update.message.reply_text("📚 Teacher mode ON!")

async def set_motivation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_mode[update.message.from_user.id] = "motivation"
    await update.message.reply_text("💪 Motivation mode ON!")

async def set_normal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_mode[update.message.from_user.id] = "normal"
    await update.message.reply_text("🙂 Normal mode ON!")

# ===== TEXT MESSAGE HANDLER =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_text = update.message.text
    mode = user_mode.get(user_id, "normal")

    system_prompt = {
        "funny": "You are a very funny assistant.",
        "teacher": "You are a teacher.",
        "motivation": "You are motivational.",
    }.get(mode, "You are a helpful assistant.")

    if user_id not in user_memory:
        user_memory[user_id] = [{"role": "system", "content": system_prompt}]

    user_memory[user_id].append({"role": "user", "content": user_text})

    try:
        chat_completion = client.chat.completions.create(
            messages=user_memory[user_id],
            model="llama-3.3-70b-versatile",
        )
        reply = chat_completion.choices[0].message.content
        user_memory[user_id].append({"role": "assistant", "content": reply})

        if len(user_memory[user_id]) > 10:
            user_memory[user_id] = user_memory[user_id][-10:]

    except Exception as e:
        print("AI ERROR:", e)
        reply = "AI error aa gaya 😅"

    await update.message.chat.send_action(action=ChatAction.TYPING)
    await asyncio.sleep(1.5)
    await update.message.reply_text(reply)

# ===== VOICE HANDLER =====
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.voice.get_file()
    await file.download_to_drive("voice.ogg")

    sound = AudioSegment.from_ogg("voice.ogg")
    sound.export("voice.wav", format="wav")

    r = sr.Recognizer()
    with sr.AudioFile("voice.wav") as source:
        audio = r.record(source)

    try:
        text = r.recognize_google(audio)
    except:
        await update.message.reply_text("Voice samajh nahi aaya 😅")
        return

    user_id = update.message.from_user.id

    if user_id not in user_memory:
        user_memory[user_id] = [{"role": "system", "content": "You are a helpful assistant."}]

    user_memory[user_id].append({"role": "user", "content": text})

    chat_completion = client.chat.completions.create(
        messages=user_memory[user_id],
        model="llama-3.3-70b-versatile",
    )

    reply = chat_completion.choices[0].message.content
    await update.message.reply_text(f"You said: {text}\n\n{reply}")

    os.remove("voice.ogg")
    os.remove("voice.wav")

# ===== GROUP HANDLER =====
async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_username = (await context.bot.get_me()).username.lower()
    user_text = update.message.text.lower()

    if f"@{bot_username}" not in user_text:
        return

    user_id = update.message.from_user.id

    if user_id not in user_memory:
        user_memory[user_id] = [{"role": "system", "content": "You are a helpful assistant."}]

    user_memory[user_id].append({"role": "user", "content": user_text})

    try:
        chat_completion = client.chat.completions.create(
            messages=user_memory[user_id],
            model="llama-3.3-70b-versatile",
        )
        reply = chat_completion.choices[0].message.content
        user_memory[user_id].append({"role": "assistant", "content": reply})

        if len(user_memory[user_id]) > 10:
            user_memory[user_id] = user_memory[user_id][-10:]

    except:
        reply = "AI error 😅"

    await update.message.reply_text(reply)

# ===== WEATHER =====
async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = " ".join(context.args)
    url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={WEATHER_API_KEY}&units=metric"

    data = requests.get(url).json()
    if str(data.get("cod")) != "200":
        await update.message.reply_text("City not found 😅")
        return

    temp = data["list"][0]["main"]["temp"]
    desc = data["list"][0]["weather"][0]["description"]

    await update.message.reply_text(f"🌤 Weather in {city}\n🌡 Temp: {temp}°C\n☁ {desc}")

# ===== SEARCH =====
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args)
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=3))

    reply = "🔎 Top results:\n\n"
    for r in results:
        reply += f"📌 {r['title']}\n{r['href']}\n\n"

    await update.message.reply_text(reply)

# ===== YTINFO =====
async def ytinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.args:
            await update.message.reply_text("❌ Use like this:\n/ytinfo <YouTube URL>")
            return

        url = context.args[0]

        await update.message.chat.send_action(action=ChatAction.TYPING)

        ydl_opts = {
            "quiet": True,
            "user_agent": "Mozilla/5.0",
            "extractor_args": {"youtube": {"player_client": ["android"]}},
            "skip_download": True,
            "nocheckcertificate": True,
            "geo_bypass": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        title = info.get("title", "N/A")
        views = info.get("view_count", "N/A")
        duration = info.get("duration", 0)
        uploader = info.get("uploader", "N/A")

        mins, secs = divmod(duration, 60)

        msg = (
            f"🎬 *Title:* {title}\n"
            f"👤 *Channel:* {uploader}\n"
            f"👁️ *Views:* {views}\n"
            f"⏱️ *Duration:* {mins}m {secs}s"
        )

        await update.message.reply_text(msg, parse_mode="Markdown")

    except Exception as e:
        print("YTINFO ERROR:", e)
        await update.message.reply_text("❌ Video info laane me error 😅")


# ===== MAIN =====
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_message))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, handle_group_message))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(CommandHandler("weather", weather))
    app.add_handler(CommandHandler("search", search))
    app.add_handler(CommandHandler("ytinfo", ytinfo))
    app.add_handler(CommandHandler("funny", set_funny))
    app.add_handler(CommandHandler("teacher", set_teacher))
    app.add_handler(CommandHandler("motivation", set_motivation))
    app.add_handler(CommandHandler("normal", set_normal))

    print("🤖 Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()










