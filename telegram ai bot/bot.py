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
from telegram import BotCommand




logging.basicConfig(level=logging.ERROR)

# ===== API KEYS =====
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
HF_API_KEY = os.getenv("HF_API_KEY")


client = Groq(api_key=GROQ_API_KEY)




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

# -------- RESET MEMORY COMMAND --------
async def reset_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    # Memory delete
    if user_id in user_memory:
        del user_memory[user_id]

    # Mode bhi reset
    if user_id in user_mode:
        del user_mode[user_id]

    await update.message.reply_text("🧠 Memory cleared! Ab main sab bhool gaya 😄")


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
            await update.message.reply_text("❌ Use like this:\n/ytinfo <YouTube URL or song name>")
            return

        query = " ".join(context.args)

        await update.message.chat.send_action(action=ChatAction.TYPING)

        # If it's not a link, search YouTube
        if "http" not in query:
            search_query = f"ytsearch:{query}"
        else:
            search_query = query

        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "nocheckcertificate": True,
            "geo_bypass": True,
            "extractor_args": {"youtube": {"player_client": ["android"]}},
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_query, download=False)

            if "entries" in info:
                info = info["entries"][0]

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
        await update.message.reply_text("Use like: /draw a cat with sunglasses")
        return

    prompt = " ".join(context.args)

    API_URL = "https://router.huggingface.co/hf-inference/models/stabilityai/stable-diffusion-xl-base-1.0"
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}

    await update.message.reply_text("🎨 Drawing image...")

    try:
        response = requests.post(API_URL, headers=headers, json={"inputs": prompt})

        if response.status_code != 200:
            print("HF ERROR:", response.text)
            await update.message.reply_text("❌ Image API error aa gaya")
            return

        image_bytes = response.content

        with open("image.png", "wb") as f:
            f.write(image_bytes)

        await update.message.reply_photo(photo=open("image.png", "rb"))

    except Exception as e:
        print("HF ERROR:", e)
        await update.message.reply_text("❌ Image generation failed")

# ==== SONG DOWNLOAD ====
async def song(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check kare command ke baad user ne query diya ya nahi
    if not context.args:
        await update.message.reply_text("Use: /song song name")
        return

    # User ka diya hua song name join kar rahe hain
    query = " ".join(context.args)

    await update.message.chat.send_action(action=ChatAction.TYPING)

    try:
        # yt-dlp options set kar rahe hain (sirf info lene ke liye)
        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "nocheckcertificate": True,
            "geo_bypass": True,
        }

        # yt-dlp se YouTube search karenge
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)['entries'][0]

        # Important details nikaal rahe hain
        title = info.get("title")
        duration = info.get("duration")
        uploader = info.get("uploader")
        url = info.get("webpage_url")

        mins, secs = divmod(duration, 60)

        # Final message bana ke bhej rahe hain
        await update.message.reply_text(
            f"🎵 {title}\n"
            f"👤 {uploader}\n"
            f"⏱ {mins}m {secs}s\n"
            f"🔗 {url}"
        )

    except Exception as e:
        print("SONG ERROR:", e)
        await update.message.reply_text("Song search me error 😅")


# ==== PDF READER =====
async def readpdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check kare user ne PDF bheja ya nahi
    if not update.message.document:
        await update.message.reply_text("Send a PDF file")
        return

    # Telegram server se file download
    file = await update.message.document.get_file()
    await file.download_to_drive("file.pdf")

    try:
        # PDF open karke text read karte hain
        reader = PyPDF2.PdfReader("file.pdf")
        text = ""

        # Har page ka text extract kar rahe hain
        for page in reader.pages:
            text += page.extract_text()

        # Sirf first 1000 characters bhej rahe (limit ke liye)
        await update.message.reply_text(text[:1000])

    except Exception as e:
        print("PDF ERROR:", e)
        await update.message.reply_text("PDF read nahi ho paya 😅")

    # File delete (storage bachane ke liye)
    os.remove("file.pdf")

# === LONG MEMORY ===
async def remember(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    # Agar user ne memory text nahi diya
    if not context.args:
        await update.message.reply_text("Use: /remember text")
        return

    # User ka text join karke memory me save
    memory_text = " ".join(context.args)
    user_memory[user_id] = [{"role": "system", "content": memory_text}]

    await update.message.reply_text("🧠 Memory saved!")

# ==== IMAGE CAPTION ====
async def caption_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check kare photo aaya ya nahi
    if not update.message.photo:
        await update.message.reply_text("Send image with caption command")
        return

    # Photo download
    photo_file = await update.message.photo[-1].get_file()
    await photo_file.download_to_drive("image.jpg")

    try:
        # Image ko binary me convert karke API ko bhej rahe
        with open("image.jpg", "rb") as f:
            img_bytes = f.read()

        response = requests.post(
            "https://router.huggingface.co/huggingface/blip-image-captioning-large",
            headers={"Authorization": f"Bearer {os.getenv('HF_API_KEY')}"},
            data=img_bytes
        )

        result = response.json()[0]["generated_text"]

        # Caption reply
        await update.message.reply_text(f"🖼️ Caption: {result}")

    except Exception as e:
        print("CAPTION ERROR:", e)
        await update.message.reply_text("Image samajh nahi aaya 😅")

    os.remove("image.jpg")

# ==== TRANSLATE ====
async def translate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check kare user ne text diya ya nahi
    if not context.args:
        await update.message.reply_text("Use: /translate text")
        return

    text = " ".join(context.args)

    try:
        # Google Translate unofficial API use kar rahe
        url = f"https://api.mymemory.translated.net/get?q={text}&langpair=en|hi"
        response = requests.get(url).json()

        # Translated text nikaal rahe
        translated = response["responseData"]["translatedText"]

        await update.message.reply_text(f"🌍 Translation:\n{translated}")

    except Exception as e:
        print("TRANSLATE ERROR:", e)
        await update.message.reply_text("Translate error 😅")

# -------- SONG DOWNLOAD COMMAND --------
async def song(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check kare user ne song name diya ya nahi
    if not context.args:
        await update.message.reply_text("Use: /song song name")
        return

    query = " ".join(context.args)

    await update.message.reply_text("🎵 Song search ho raha hai...")

    ydl_opts = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
        "outtmpl": "song.%(ext)s",
        "cookiefile": "cookies.txt",  # optional (ignore if not using)
    }

    try:
        # YouTube se first result download karega
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=True)
            file_path = ydl.prepare_filename(info['entries'][0])

        # Telegram pe audio bhejna
        await update.message.reply_audio(audio=open(file_path, "rb"))

        # File delete (storage bachane ke liye)
        os.remove(file_path)

    except Exception as e:
        print("SONG ERROR:", e)
        await update.message.reply_text("❌ Song download failed 😅")


# -------- IMAGE CAPTION FUNCTION --------
async def caption_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check kare photo aaya ya nahi
    if not update.message.photo:
        await update.message.reply_text("Photo bhejo caption ke liye 📸")
        return

    # Telegram server se image download
    photo_file = await update.message.photo[-1].get_file()
    await photo_file.download_to_drive("image.jpg")

    await update.message.reply_text("🖼 Image samajh raha hoon...")

    try:
        # HuggingFace image caption model API
        API_URL = "https://router.huggingface.co/hf-inference/models/Salesforce/blip-image-captioning-base"
        headers = {"Authorization": f"Bearer {os.getenv('HF_API_KEY')}"}

        with open("image.jpg", "rb") as f:
            img_bytes = f.read()

        response = requests.post(API_URL, headers=headers, data=img_bytes)

        result = response.json()[0]["generated_text"]

        await update.message.reply_text(f"📷 Caption: {result}")

    except Exception as e:
        print("CAPTION ERROR:", e)
        await update.message.reply_text("Image samajhne me error aa gaya 😅")

    # Image delete
    os.remove("image.jpg")





# -------- BOT MENU COMMANDS SETUP --------
async def set_bot_commands(app):
    await app.bot.set_my_commands([
        BotCommand("start", "Bot ko start kare"),
        BotCommand("help", "Sab commands ki list"),
        BotCommand("reset", "Memory clear kare"),
        BotCommand("weather", "Weather check kare"),
        BotCommand("search", "Google type search"),
        BotCommand("ytinfo", "YouTube video info"),
        BotCommand("draw", "AI image generate kare"),
        BotCommand("remember", "Long memory save kare"),
        BotCommand("translate", "Language translate kare"),
    ])


# ===== MAIN =====
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.post_init = set_bot_commands
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
    app.add_handler(CommandHandler("reset", reset_memory))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))
    app.add_handler(CommandHandler("draw", draw))
    app.add_handler(CommandHandler("song", song))
    app.add_handler(MessageHandler(filters.Document.PDF, readpdf))
    app.add_handler(CommandHandler("remember", remember))
    app.add_handler(MessageHandler(filters.PHOTO, caption_image))
    app.add_handler(CommandHandler("translate", translate))
    app.add_handler(CommandHandler("song", song))
    app.add_handler(MessageHandler(filters.PHOTO, caption_image))


    





    print("🤖 Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()




























