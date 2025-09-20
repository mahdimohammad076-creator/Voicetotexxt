import os
import logging
import whisper
from telegram import Update, InputFile
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    Defaults
)
from telegram.constants import ParseMode
import asyncio

# --- تنظیمات ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
MAX_FILE_SIZE = 500 * 1024 * 1024 

# --- لاگ‌گیری ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- بارگذاری مدل Whisper ---
MODEL_NAME = "small"
print(f"در حال بارگذاری مدل Whisper ({MODEL_NAME})...")
try:
    model = whisper.load_model(MODEL_NAME)
    print("مدل با موفقیت بارگذاری شد.")
except Exception as e:
    logger.error(f"خطا در بارگذاری مدل: {e}")
    print("تلاش برای بارگذاری مدل 'base'...")
    model = whisper.load_model("base")
    print("مدل 'base' با موفقیت بارگذاری شد.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_name = update.effective_user.first_name
    await update.message.reply_text(
        f"سلام {user_name}!\n\nیک فایل صوتی، ویدیویی یا پیام صوتی بفرست تا به متن تبدیلش کنم.",
        parse_mode=ParseMode.MARKDOWN
    )

async def process_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    media_file = message.voice or message.audio or message.video or message.video_note

    if not media_file: return
    if media_file.file_size > MAX_FILE_SIZE:
        await message.reply_text("⛔️ فایل خیلی بزرگ است!")
        return

    processing_message = await message.reply_text("✅ فایل دریافت شد. در حال آماده‌سازی...")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')

    file_path = None
    try:
        file_id = media_file.file_id
        file_path = f"{file_id}.tmp"
        new_file = await context.bot.get_file(file_id)
        await new_file.download_to_drive(file_path)
        
        await processing_message.edit_text("⏳ در حال تبدیل صوت به متن... (این ممکن است چند دقیقه طول بکشد)")
        
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, lambda: model.transcribe(file_path, fp16=False))

        transcribed_text = result['text']
        detected_language = result['language']
        
        if len(transcribed_text) > 3500:
            await processing_message.edit_text("✅ تبدیل انجام شد! متن در یک فایل ارسال می‌شود.")
            txt_path = f"{file_id}.txt"
            with open(txt_path, "w", encoding="utf-8") as f: f.write(transcribed_text)
            await message.reply_document(document=InputFile(txt_path))
            os.remove(txt_path)
        else:
            response_text = f"زبان: **{detected_language.upper()}**\n\n```{transcribed_text}```"
            await processing_message.edit_text(response_text, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.error(f"خطا: {e}")
        await processing_message.edit_text("❌ مشکلی در پردازش فایل پیش آمد.")
    finally:
        if file_path and os.path.exists(file_path): os.remove(file_path)

def main() -> None:
    if not TELEGRAM_TOKEN:
        logger.error("توکن تلگرام پیدا نشد!")
        return
    
    defaults = Defaults(read_timeout=120, connect_timeout=120)
    application = Application.builder().token(TELEGRAM_TOKEN).defaults(defaults).build()

    application.add_handler(CommandHandler("start", start))
    media_filter = filters.VOICE | filters.AUDIO | filters.VIDEO | filters.VIDEO_NOTE
    application.add_handler(MessageHandler(media_filter, process_media))

    print("ربات در حال اجراست...")
    application.run_polling()

if __name__ == "__main__":
    main()
