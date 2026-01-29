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
import logging
logging.basicConfig(level=logging.ERROR)
import yt_dlp






TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")


client = Groq(api_key=GROQ_API_KEY)


user_memory = {}
user_mode = {}


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



# -------- TEXT MESSAGE HANDLER --------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_text = update.message.text
    mode = user_mode.get(user_id, "normal")

    if mode == "funny":
        system_prompt = "You are a very funny assistant. Add humor in every reply."
    elif mode == "teacher":
        system_prompt = "You are a teacher. Explain clearly with examples."
    elif mode == "motivation":
        system_prompt = "You are a motivational speaker. Inspire the user."
    else:
        system_prompt = "You are a helpful AI assistant."

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
        # Memory limit (sirf last 10 messages rakhega)
     if len(user_memory[user_id]) > 10:
        user_memory[user_id] = user_memory[user_idel][:-10]


    except Exception as e:
        print("ERROR:", e)
        reply = "AI error aa gaya 😅"

    # typing indicator show karo
    await update.message.chat.send_action(action=ChatAction.TYPING)
    await asyncio.sleep(1.5)  # 1.5 sec delay (human jaisa)

    await update.message.reply_text(reply)



# -------- VOICE MESSAGE HANDLER --------
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
        user_memory[user_id] = [{"role": "system", "content": "You are a helpful AI assistant."}]

    user_memory[user_id].append({"role": "user", "content": text})

    chat_completion = client.chat.completions.create(
        messages=user_memory[user_id],
        model="llama-3.3-70b-versatile",
    )

    reply = chat_completion.choices[0].message.content
    user_memory[user_id].append({"role": "assistant", "content": reply})

    # typing indicator show karo
    await update.message.chat.send_action(action=ChatAction.TYPING)
    await asyncio.sleep(1.5)  # 1.5 sec delay (human jaisa)

    await update.message.reply_text(f"You said: {text}\n\n{reply}")

    os.remove("voice.ogg")
    os.remove("voice.wav")


# -------- RESET MEMORY COMMAND --------
async def reset_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    # Agar user memory exist karti hai to delete karo
    if user_id in user_memory:
        del user_memory[user_id]

    # Personality mode bhi reset
    if user_id in user_mode:
        del user_mode[user_id]

    await update.message.reply_text("🧠 Memory cleared! Ab main sab bhool gaya 😄")


# -------- GROUP MESSAGE HANDLER --------
bot_username = (await context.bot.get_me()).username.lower()
if f"@{bot_username}" not in update.message.text.lower():
    return

async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.lower()
    bot_username = context.bot.username.lower()

    # Check karo bot mention hua ya nahi
    if bot_username in user_text:
        user_id = update.message.from_user.id

        if user_id not in user_memory:
            user_memory[user_id] = [{"role": "system", "content": "You are a helpful AI assistant."}]

        user_memory[user_id].append({"role": "user", "content": user_text})

        try:
            chat_completion = client.chat.completions.create(
                messages=user_memory[user_id],
                model="llama-3.3-70b-versatile",
            )
            reply = chat_completion.choices[0].message.content
            user_memory[user_id].append({"role": "assistant", "content": reply})
             # Memory limit (sirf last 10 messages rakhega)
        if len(user_memory[user_id]) > 10:
            user_memory[user_id] = user_memory[user_idel][:-10]
        except Exception as e:
            print("ERROR:", e)
            reply = "AI error 😅"

        await update.message.reply_text(reply)

print("WEATHER KEY USED:", WEATHER_API_KEY)

# -------- WEATHER COMMAND --------
async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Use like this: /weather delhi")
        return

    city = " ".join(context.args)

    # FREE PLAN compatible endpoint (forecast API)
    url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={WEATHER_API_KEY}&units=metric"

    try:
        response = requests.get(url)
        data = response.json()

        # Agar city galat ho ya key issue ho
        if str(data.get("cod")) != "200":

            await update.message.reply_text("❌ City not found 😅")
            return

        # Forecast data se current-like first entry lete hain
        temp = data["list"][0]["main"]["temp"]
        desc = data["list"][0]["weather"][0]["description"]

        reply = (
            f"🌤 Weather in {city.title()}:\n"
            f"🌡 Temperature: {temp}°C\n"
            f"☁ Condition: {desc}"
        )

        await update.message.reply_text(reply)

    except Exception as e:
        print("WEATHER ERROR:", e)
        await update.message.reply_text("⚠ Weather service error aa gaya")






# -------- SEARCH COMMAND --------
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /search topic")
        return

    query = " ".join(context.args)

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))

        reply = "🔎 Top results:\n\n"
        for r in results:
            reply += f"📌 {r['title']}\n{r['href']}\n\n"

    except Exception as e:
        print(e)
        reply = "Search karne me error 😅"

    await update.message.reply_text(reply)







# -------- YOUTUBE INFO COMMAND --------
async def ytinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.args:
            await update.message.reply_text("❌ Link do bhai\nExample: /ytinfo <YouTube URL>")
            return

        url = context.args[0]

        await update.message.chat.send_action(action=ChatAction.TYPING)

       ydl_opts = {
    "quiet": True,
    "user_agent": "Mozilla/5.0",
    "extractor_args": {"youtube": {"player_client": ["android"]}},
    "skip_download": True,  # IMPORTANT
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










def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
   # Private chat ke liye
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_message))

# Group chat ke liye
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, handle_group_message))

    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, handle_group_message))
    app.add_handler(CommandHandler("weather", weather))
    app.add_handler(CommandHandler("search", search))
    app.add_handler(CommandHandler("ytinfo", ytinfo))
    


    

    app.add_handler(CommandHandler("funny", set_funny))
    app.add_handler(CommandHandler("teacher", set_teacher))
    app.add_handler(CommandHandler("motivation", set_motivation))
    app.add_handler(CommandHandler("normal", set_normal))
    app.add_handler(CommandHandler("reset", reset_memory))





    print("🤖 FREE AI Bot chal raha hai...")
    app.run_polling()


if __name__ == "__main__":
    main()








