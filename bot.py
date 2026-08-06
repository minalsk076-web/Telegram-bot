import os
import gc
import asyncio
from pypdf import PdfReader, PdfWriter
from PIL import Image
from telegram import Update, constants
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

BOT_TOKEN = "8786795965:AAGNqLwTHBvM7su8NPS53Ah9AOjEZ3W6DFE"
user_actions = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome! Send a command:\n\n"
        "1. /img_pdf (Then send images)\n"
        "2. /pdf_dvd <pages_per_pdf> (e.g. /pdf_dvd 10)\n"
        "3. /rmv_pg <pages> (e.g. /rmv_pg 1,2,5 or 1-30)\n"
        "4. /invert_pdf"
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    action = user_actions.get(user_id)
    message = update.message
    
    if not action and message.caption:
        caption = message.caption.strip()
        if caption.startswith("/pdf_dvd"):
            parts = caption.split()
            if len(parts) > 1 and parts[1].isdigit():
                action = ("split", int(parts[1]))
        elif caption.startswith("/rmv_pg"):
            parts = caption.split(maxsplit=1)
            if len(parts) > 1:
                action = ("remove", parts[1])

    if not action:
        await message.reply_text("⚠️ Please send the command first or write it in the caption!")
        return

    # Processing message bhejo aur uska reference save karo taaki baad mein delete kar sakein
    processing_msg = await message.reply_text("⏳ Please wait, your file is processing...")

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.UPLOAD_DOCUMENT)
    
    document = message.document
    file = await context.bot.get_file(document.file_id)
    input_path = f"input_{user_id}.pdf"
    await file.download_to_drive(input_path)

    try:
        reader = PdfReader(input_path)
        total_pages = len(reader.pages)
        act_type, act_value = action

        if act_type == "split":
            chunk_size = int(act_value)
            for i in range(0, total_pages, chunk_size):
                writer = PdfWriter()
                for page_num in range(i, min(i + chunk_size, total_pages)):
                    writer.add_page(reader.pages[page_num])
                
                out = f"part_{i//chunk_size + 1}.pdf"
                with open(out, 'wb') as output_file:
                    writer.write(output_file)
                
                with open(out, 'rb') as f:
                    await message.reply_document(document=f)
                os.remove(out)
                gc.collect()

        elif act_type == "remove":
            pages_to_del = set()
            parts = act_value.split(',')
            for part in parts:
                if '-' in part:
                    start_p, end_p = map(int, part.split('-'))
                    for p in range(start_p, end_p + 1):
                        pages_to_del.add(p - 1)
                else:
                    pages_to_del.add(int(part) - 1)

            writer = PdfWriter()
            for index, page in enumerate(reader.pages):
                if index not in pages_to_del:
                    writer.add_page(page)
            
            out = f"modified_{user_id}.pdf"
            with open(out, 'wb') as output_file:
                writer.write(output_file)
            
            with open(out, 'rb') as f:
                await message.reply_document(document=f)
            os.remove(out)

        gc.collect()
        
        # Kaam poora hone ke baad processing message ko delete kar do
        await processing_msg.delete()

    except Exception as e:
        await processing_msg.edit_text(f"❌ Error: {str(e)}")
    finally:
        if os.path.exists(input_path): 
            os.remove(input_path)
        user_actions.pop(user_id, None)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    action = user_actions.get(user_id)
    if action != ("img", ""):
        await update.message.reply_text("⚠️ Please send the /img_pdf command first!")
        return

    processing_msg = await update.message.reply_text("⏳ Please wait, converting your image to PDF...")

    photo_file = await update.message.photo[-1].get_file()
    photo_path = f"photo_{user_id}.jpg"
    await photo_file.download_to_drive(photo_path)

    try:
        image = Image.open(photo_path)
        rgb_image = image.convert('RGB')
        out_pdf = f"converted_{user_id}.pdf"
        rgb_image.save(out_pdf)

        with open(out_pdf, 'rb') as f:
            await update.message.reply_document(document=f)
        
        os.remove(photo_path)
        os.remove(out_pdf)
        
        # Processing message delete kar do
        await processing_msg.delete()
    except Exception as e:
        await processing_msg.edit_text(f"❌ Error: {str(e)}")
    finally:
        user_actions.pop(user_id, None)

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("img_pdf", lambda u, c: (user_actions.update({u.effective_user.id: ("img", "")}), u.message.reply_text("✅ Ready! Now send your images."))))
    app.add_handler(CommandHandler("pdf_dvd", lambda u, c: (user_actions.update({u.effective_user.id: ("split", c.args[0])}), u.message.reply_text(f"✅ Ready! Send PDF to divide into {c.args[0]} pages.")) if c.args else u.message.reply_text("Usage: /pdf_dvd <pages>")))
    app.add_handler(CommandHandler("rmv_pg", lambda u, c: (user_actions.update({u.effective_user.id: ("remove", c.args[0])}), u.message.reply_text(f"✅ Ready! Send PDF to remove pages: {c.args[0]}.")) if c.args else u.message.reply_text("Usage: /rmv_pg 1,2 or 1-30")))
    app.add_handler(CommandHandler("invert_pdf", lambda u, c: u.message.reply_text("Invert PDF feature is ready.")))
    
    app.add_handler(MessageHandler(filters.Document.PDF, handle_document))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    app.run_polling()

if __name__ == "__main__":
    main()
