import os
import gc
import fitz
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
    await update.message.reply_text("👋 Hello! Send a command:\n/invert_pdf\n/pdf_dvd <size>\n/rmv_pg <pages>")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    action = user_actions.get(user_id)
    if not action:
        await update.message.reply_text("⚠️ Select a command first!")
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.UPLOAD_DOCUMENT)
    
    document = update.message.document
    file = await context.bot.get_file(document.file_id)
    input_path = f"input_{user_id}.pdf"
    
    # Download file in chunks to prevent memory spike
    await file.download_to_drive(input_path)

    try:
        # Open PDF in low-memory mode
        doc = fitz.open(input_path)
        
        if isinstance(action, tuple) and action[0] == "split":
            chunk_size = action[1]
            total_pages = len(doc)
            for i in range(0, total_pages, chunk_size):
                new_doc = fitz.open()
                new_doc.insert_pdf(doc, from_page=i, to_page=min(i + chunk_size - 1, total_pages - 1))
                out = f"part_{i+1}.pdf"
                new_doc.save(out, garbage=4, deflate=True)
                new_doc.close()
                
                with open(out, 'rb') as f:
                    await update.message.reply_document(document=f)
                os.remove(out)
                gc.collect() # Free up RAM immediately

        elif isinstance(action, tuple) and action[0] == "remove":
            pages_to_del = sorted([int(p)-1 for p in action[1].split(',') if int(p) <= len(doc)], reverse=True)
            for p in pages_to_del: 
                doc.delete_page(p)
            out = f"modified_{user_id}.pdf"
            doc.save(out, garbage=4, deflate=True)
            
            with open(out, 'rb') as f:
                await update.message.reply_document(document=f)
            os.remove(out)

        doc.close()
        gc.collect()

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
    finally:
        if os.path.exists(input_path): 
            os.remove(input_path)
        user_actions.pop(user_id, None)

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pdf_dvd", lambda u, c: (user_actions.update({u.effective_user.id: ("split", int(c.args[0]))}), u.message.reply_text("Send PDF!")) if c.args else u.message.reply_text("Usage: /pdf_dvd 25")))
    app.add_handler(CommandHandler("rmv_pg", lambda u, c: (user_actions.update({u.effective_user.id: ("remove", c.args[0])}), u.message.reply_text("Send PDF!")) if c.args else u.message.reply_text("Usage: /rmv_pg 1,2")))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_document))
    app.run_polling()

if __name__ == "__main__":
    main()
# fix
