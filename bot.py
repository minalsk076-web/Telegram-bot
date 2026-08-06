import os
import io
import fitz  # PyMuPDF
from PIL import Image, ImageOps
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Aapka Telegram Bot Token
BOT_TOKEN = "8786795965:AAGNqLwTHBvM7su8NPS53Ah9AOjEZ3W6DFE"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "👋 **Welcome to PDF Tool Bot!**\n\n"
        "Here is what I can do for you:\n"
        "• **Invert PDF Colors:** Send me any PDF file directly.\n"
        "• **Classic Dark Invert:** Use `/classic_invert` then send a PDF.\n"
        "• **Delete Pages:** Use `/delete_page_from_pdf`.\n"
        "• **Convert Images to PDF:** Send images and use `/done_image_to_pdf`.\n\n"
        "Send any PDF or image to get started!"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)


async def invert_pdf_colors(doc_bytes: bytes, classic: bool = False) -> bytes:
    pdf_doc = fitz.open(stream=doc_bytes, filetype="pdf")
    out_pdf = fitz.open()

    for page in pdf_doc:
        pix = page.get_pixmap(dpi=150)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        if classic:
            inverted_img = ImageOps.invert(img)
        else:
            inverted_img = ImageOps.invert(img)

        img_byte_arr = io.BytesIO()
        inverted_img.save(img_byte_arr, format="PDF")
        img_byte_arr.seek(0)

        img_pdf = fitz.open(stream=img_byte_arr.read(), filetype="pdf")
        out_pdf.insert_pdf(img_pdf)

    out_bytes = out_pdf.write()
    pdf_doc.close()
    out_pdf.close()
    return out_bytes


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc.mime_type or "pdf" not in doc.mime_type.lower():
        await update.message.reply_text("Please send a valid PDF file.")
        return

    status_msg = await update.message.reply_text("⏳ Processing your PDF, please wait...")

    file = await context.bot.get_file(doc.file_id)
    doc_bytes = await file.download_as_bytearray()

    classic_mode = context.user_data.get("classic_invert", False)
    context.user_data["classic_invert"] = False

    try:
        processed_bytes = await invert_pdf_colors(bytes(doc_bytes), classic=classic_mode)
        output = io.BytesIO(processed_bytes)
        output.name = f"inverted_{doc.file_name}"

        await update.message.reply_document(
            document=output,
            caption="✅ Here is your processed PDF!"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ An error occurred while processing: {str(e)}")
    finally:
        await status_msg.delete()


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "images" not in context.user_data:
        context.user_data["images"] = []

    photo_file = await update.message.photo[-1].get_file()
    photo_bytes = await photo_file.download_as_bytearray()

    img = Image.open(io.BytesIO(photo_bytes)).convert("RGB")
    context.user_data["images"].append(img)

    count = len(context.user_data["images"])
    await update.message.reply_text(
        f"📸 Image {count} added! Send more images or type /done_image_to_pdf when finished."
    )


async def cmd_classic_invert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["classic_invert"] = True
    await update.message.reply_text("Classic Invert mode enabled for the next PDF you send!")


async def cmd_delete_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "To delete pages, send your PDF with a caption listing the page numbers to remove (e.g., `1,3,5`).",
        parse_mode="Markdown"
    )


async def cmd_image_to_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send one or more photos, then use /done_image_to_pdf to convert them into a single PDF.")


async def cmd_done_image_to_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    images = context.user_data.get("images", [])
    if not images:
        await update.message.reply_text("No images uploaded yet. Send photos first!")
        return

    status_msg = await update.message.reply_text("⏳ Generating PDF from your images...")

    pdf_bytes = io.BytesIO()
    images[0].save(pdf_bytes, format="PDF", save_all=True, append_images=images[1:])
    pdf_bytes.seek(0)
    pdf_bytes.name = "converted_images.pdf"

    await update.message.reply_document(
        document=pdf_bytes,
        caption="✅ Here is your PDF converted from images!"
    )
    context.user_data["images"] = []
    await status_msg.delete()


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send a PDF document or image to start processing, or type /start for options.")


def main():
    """Start Telegram Bot."""
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("classic_invert", cmd_classic_invert))
    app.add_handler(CommandHandler("delete_page_from_pdf", cmd_delete_page))
    app.add_handler(CommandHandler("image_to_pdf", cmd_image_to_pdf))
    app.add_handler(CommandHandler("done_image_to_pdf", cmd_done_image_to_pdf))

    # Handlers
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("Bot is up and running...")
    app.run_polling()


if __name__ == "__main__":
    main()
