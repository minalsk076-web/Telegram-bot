import os
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from PIL import Image, ImageOps
from pdf2image import convert_from_path
import img2pdf
from pypdf import PdfReader, PdfWriter
from telegram import Update, constants
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

BOT_TOKEN = "8786795965:AAGNqLwTHBvM7su8NPS53Ah9AOjEZ3W6DFE"

# Conversation States
WAITING_PDF, WAITING_SPLIT_NUM, WAITING_RMV_NUM, WAITING_PHOTOS = range(4)

# --- DUMMY SERVER FOR RENDER PORT BINDING ---
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    server.serve_forever()
# ---------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "👋 Welcome!\n\nHere is all command\n\n"
        "1. /pdf_dvd\n"
        "2. /rmv_pg\n"
        "3. /img_pdf\n"
        "4. /invert_pdf\n\n"
        "*(Kisi bhi process ko beech mein rokne ke liye /cancel bhejein)*"
    )
    return ConversationHandler.END

# ----------------- 1. DIVIDE PDF -----------------
async def cmd_pdf_dvd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['action'] = 'split'
    await update.message.reply_text("Send your pdf (Ya cancel karne ke liye /cancel bhejein)")
    return WAITING_PDF

async def receive_pdf_for_split(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    file = await context.bot.get_file(doc.file_id)
    path = f"split_{update.effective_user.id}.pdf"
    await file.download_to_drive(path)
    context.user_data['pdf_path'] = path
    await update.message.reply_text("How many pages you want in per pdf file\n\nSend like this ( 10,20,30..etc )")
    return WAITING_SPLIT_NUM

async def process_pdf_split(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text("Send like this ( 10,20,30..etc )")
        return WAITING_SPLIT_NUM

    chunk_size = int(text)
    input_path = context.user_data.get('pdf_path')

    proc_msg = await update.message.reply_text("Your pdf is processing please wait.. ⏳")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.UPLOAD_DOCUMENT)

    try:
        reader = PdfReader(input_path)
        total_pages = len(reader.pages)

        for i in range(0, total_pages, chunk_size):
            writer = PdfWriter()
            for page_num in range(i, min(i + chunk_size, total_pages)):
                writer.add_page(reader.pages[page_num])
            
            out_path = f"modified_{user_id}_{i//chunk_size + 1}.pdf"
            with open(out_path, 'wb') as f:
                writer.write(f)
            
            with open(out_path, 'rb') as f:
                await update.message.reply_document(document=f)
            os.remove(out_path)

        await proc_msg.delete()

    except Exception as e:
        await proc_msg.edit_text(f"❌ Error: {str(e)}")
    finally:
        if input_path and os.path.exists(input_path):
            os.remove(input_path)
        context.user_data.clear()

    return ConversationHandler.END

# ----------------- 2. REMOVE PAGES -----------------
async def cmd_rmv_pg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['action'] = 'remove'
    await update.message.reply_text("Send your pdf file (Ya cancel karne ke liye /cancel bhejein)")
    return WAITING_PDF

async def receive_pdf_for_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    file = await context.bot.get_file(doc.file_id)
    path = f"rmv_{update.effective_user.id}.pdf"
    await file.download_to_drive(path)
    context.user_data['pdf_path'] = path
    await update.message.reply_text("Please select which page you want to remove.\n\nSend like this ( 1,2,3,4,5....etc those you want to remove )")
    return WAITING_RMV_NUM

async def process_pdf_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    raw_input = update.message.text.strip()
    input_path = context.user_data.get('pdf_path')

    proc_msg = await update.message.reply_text("Your pdf is processing please wait.. ⏳")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.UPLOAD_DOCUMENT)

    try:
        reader = PdfReader(input_path)
        total_pages = len(reader.pages)
        pages_to_del = set()

        parts = raw_input.replace(' ', '').split(',')
        for part in parts:
            if '-' in part:
                s, e = map(int, part.split('-'))
                for p in range(s, e + 1):
                    if 1 <= p <= total_pages:
                        pages_to_del.add(p - 1)
            elif part.isdigit():
                p = int(part)
                if 1 <= p <= total_pages:
                    pages_to_del.add(p - 1)

        writer = PdfWriter()
        for idx, page in enumerate(reader.pages):
            if idx not in pages_to_del:
                writer.add_page(page)

        out_path = f"modified_{user_id}.pdf"
        with open(out_path, 'wb') as f:
            writer.write(f)

        with open(out_path, 'rb') as f:
            await update.message.reply_document(
                document=f,
                caption=f"Your pages are removed successfully ( p.no:- {raw_input} )"
            )

        os.remove(out_path)
        await proc_msg.delete()

    except Exception as e:
        await proc_msg.edit_text(f"❌ Error: {str(e)}")
    finally:
        if input_path and os.path.exists(input_path):
            os.remove(input_path)
        context.user_data.clear()

    return ConversationHandler.END

# ----------------- 3. IMAGE TO PDF (Album Spam Fixed) -----------------
async def cmd_img_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['photos'] = []
    await update.message.reply_text("Send me photo (Ya cancel karne ke liye /cancel bhejein)")
    return WAITING_PHOTOS

async def receive_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'photos' not in context.user_data:
        context.user_data['photos'] = []
        
    photo_file = await update.message.photo[-1].get_file()
    path = f"img_{update.effective_user.id}_{update.message.message_id}.jpg"
    await photo_file.download_to_drive(path)
    context.user_data['photos'].append(path)

    if update.message.media_group_id:
        return WAITING_PHOTOS

    photos = context.user_data['photos']
    msg = (
        f"Total number of received photo:- {len(photos)}\n\n"
        "if all photos are sended successfully then reply - Done\n\n"
        "Or you can send more photo"
    )
    await update.message.reply_text(msg)
    return WAITING_PHOTOS

async def process_img_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photos = context.user_data.get('photos', [])
    if not photos:
        await update.message.reply_text("No photos received! Send images first.")
        return WAITING_PHOTOS

    user_id = update.effective_user.id
    proc_msg = await update.message.reply_text("Your pdf making is processing please wait.. ⏳")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.UPLOAD_DOCUMENT)

    out_pdf = f"modified_{user_id}.pdf"
    try:
        with open(out_pdf, "wb") as f:
            f.write(img2pdf.convert(photos))

        with open(out_pdf, "rb") as f:
            await update.message.reply_document(
                document=f,
                caption=(
                    "Your pdf is completed ✅\n\n"
                    f"I have added your {len(photos)} images in {len(photos)} pages sequencely in 1 pdf"
                )
            )

        await proc_msg.delete()

    except Exception as e:
        await proc_msg.edit_text(f"❌ Error: {str(e)}")
    finally:
        for p in photos:
            if os.path.exists(p):
                os.remove(p)
        if os.path.exists(out_pdf):
            os.remove(out_pdf)
        context.user_data.clear()

    return ConversationHandler.END

# ----------------- 4. INVERT PDF (Color Inversion Fixed) -----------------
async def cmd_invert_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['action'] = 'invert'
    await update.message.reply_text("Please send your pdf (Ya cancel karne ke liye /cancel bhejein)")
    return WAITING_PDF

async def process_invert_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    doc = update.message.document
    file = await context.bot.get_file(doc.file_id)
    input_path = f"invert_{user_id}.pdf"
    await file.download_to_drive(input_path)

    proc_msg = await update.message.reply_text("PDF colors are inverting, please wait.. ⏳")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.UPLOAD_DOCUMENT)

    out_pdf = f"inverted_{doc.file_name}"
    inverted_paths = []

    try:
        images = convert_from_path(input_path)
        for i, img in enumerate(images):
            inv_img = ImageOps.invert(img.convert("RGB"))
            p = f"inv_{user_id}_{i}.jpg"
            inv_img.save(p, "JPEG")
            inverted_paths.append(p)

        with open(out_pdf, "wb") as f:
            f.write(img2pdf.convert(inverted_paths))

        with open(out_pdf, "rb") as f:
            await update.message.reply_document(
                document=f,
                caption="Your pdf colors are successfully inverted! ✅"
            )

        await proc_msg.delete()

    except Exception as e:
        await proc_msg.edit_text(f"❌ Error: {str(e)}")
    finally:
        if os.path.exists(input_path):
            os.remove(input_path)
        for p in inverted_paths:
            if os.path.exists(p):
                os.remove(p)
        if os.path.exists(out_pdf):
            os.remove(out_pdf)
        context.user_data.clear()

    return ConversationHandler.END

# ----------------- CANCEL COMMAND -----------------
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Process cancelled successfully. Ab aap doosri command use kar sakte hain!")
    return ConversationHandler.END

def main():
    # Start dummy HTTP server in background thread for Render port binding
    server_thread = threading.Thread(target=run_dummy_server, daemon=True)
    server_thread.start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("pdf_dvd", cmd_pdf_dvd),
            CommandHandler("rmv_pg", cmd_rmv_pg),
            CommandHandler("img_pdf", cmd_img_pdf),
            CommandHandler("invert_pdf", cmd_invert_pdf),
        ],
        states={
            WAITING_PDF: [
                MessageHandler(filters.Document.PDF, lambda u, c: 
                    receive_pdf_for_split(u, c) if c.user_data.get('action') == 'split' else (
                    receive_pdf_for_remove(u, c) if c.user_data.get('action') == 'remove' else
                    process_invert_pdf(u, c)
                ))
            ],
            WAITING_SPLIT_NUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_pdf_split)],
            WAITING_RMV_NUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_pdf_remove)],
            WAITING_PHOTOS: [
                MessageHandler(filters.PHOTO, receive_photos),
                MessageHandler(filters.Regex("^(Done|done)$"), process_img_pdf),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start),
            CommandHandler("pdf_dvd", cmd_pdf_dvd),
            CommandHandler("rmv_pg", cmd_rmv_pg),
            CommandHandler("img_pdf", cmd_img_pdf),
            CommandHandler("invert_pdf", cmd_invert_pdf),
        ],
    )

    app.add_handler(conv_handler)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    app.run_polling()

if __name__ == "__main__":
    main()
