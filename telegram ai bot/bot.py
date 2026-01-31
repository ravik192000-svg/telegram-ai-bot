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
import PyPDF2
from openai import OpenAI
import base64



logging.basicConfig(level=logging.ERROR)

# ===== API KEYS =====
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")

client = Groq(api_key=GROQ_API_KEY)

vision_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


user_memory = {}
user_mode = {}

# ===== PDF TEXT EXTRACT FUNCTION =====
def extract_text_from_pdf(file_path):
    text = ""
    with open(file_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text += page.extract_text() + "\n"
    return text[:6000]  # limit to avoid token overflow


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
    if not context.args:
        await update.message.reply_text("❌ Use like this:\n/ytinfo <YouTube URL>")
        return

    url = context.args[0]

    await update.message.chat.send_action(action=ChatAction.TYPING)

    ydl_opts = {
        "quiet": True,
        "user_agent": "Mozilla/5.0",
        "skip_download": True,
        "nocheckcertificate": True,
        "geo_bypass": True,
        "extract_flat": True,  # important fallback mode
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        title = info.get("title", "N/A")
        uploader = info.get("uploader", "N/A")

        await update.message.reply_text(
            f"🎬 Title: {title}\n👤 Channel: {uploader}"
        )

    except Exception as e:
        print("YTINFO ERROR:", e)
        await update.message.reply_text(
            "⚠ Video details region restriction ki wajah se nahi mil pa rahi.\nTry another video link."
        )

# ==== PDF HANDLER =====
async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document

    if document.mime_type != "application/pdf":
        await update.message.reply_text("❌ Please send a PDF file.")
        return

    file = await document.get_file()
    await file.download_to_drive("file.pdf")

    pdf_text = extract_text_from_pdf("file.pdf")

    user_id = update.message.from_user.id
    user_memory[user_id] = [
        {"role": "system", "content": "Answer using this PDF content."},
        {"role": "user", "content": pdf_text}
    ]

    await update.message.reply_text("📄 PDF loaded! Now ask your question.")


# -------- IMAGE GENERATION (FREE HUGGINGFACE) --------
async def draw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /draw prompt")
        return

    prompt = " ".join(context.args)

    await update.message.chat.send_action(action=ChatAction.UPLOAD_PHOTO)

    API_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-2-1"
    headers = {"Authorization": f"Bearer {os.getenv('HF_API_KEY')}"}

    payload = {"inputs": prompt}

    try:
        response = requests.post(API_URL, headers=headers, json=payload)

        if response.status_code != 200:
            print("HF ERROR:", response.text)
            await update.message.reply_text("Image banane me error aa gaya 😅")
            return

        image_bytes = response.content

        await update.message.reply_photo(photo=image_bytes)

    except Exception as e:
        print("IMAGE ERROR:", e)
        await update.message.reply_text("Image generation error 😅")






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
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))
    app.add_handler(CommandHandler("draw", draw))





    print("🤖 Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
















