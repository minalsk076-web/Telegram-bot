import os
import fitz  # PyMuPDF
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Token seedha yahan daal diya hai
BOT_TOKEN = "8786795965:AAGNqLwTHBvM7su8NPS53Ah9AOjEZ3W6DFE"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 **PDF Bot Active Hai!**\n\nAb aap koi bhi PDF bhej sakte hain, main use invert kar dunga!")

async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if not document or not document.file_name.endswith('.pdf'):
        await update.message.reply_text("⚠️ Kripya sirf PDF file hi bhejein!")
        return

    status_msg = await update.message.reply_text("⏳ Processing your PDF... Please wait...")
    
    # File download karna
    file = await context.bot.get_file(document.file_id)
    input_path = f"downloads_{document.file_name}"
    output_path = f"processed_{document.file_name}"
    
    await file.download_to_drive(input_path)

    try:
        # PyMuPDF se PDF invert karna
        doc = fitz.open(input_path)
        for page in doc:
            pix = page.get_pixmap()
            pix.invert_irect(pix.rect)
        doc.save(output_path)
        doc.close()

        # Inverted PDF wapas bhejna
        with open(output_path, 'rb') as f:
            await update.message.reply_document(document=f, caption="✅ Here is your inverted PDF!")

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

    finally:
        # Purani files delete karna
        if os.path.exists(input_path):
            os.remove(input_path)
        if os.path.exists(output_path):
            os.remove(output_path)
        await status_msg.delete()

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))

    print("Bot is running smoothly...")
    app.run_polling()

if __name__ == "__main__":
    main()
