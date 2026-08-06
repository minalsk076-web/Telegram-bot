import os
import asyncio
import fitz  # PyMuPDF
from pyrogram import Client, filters

API_ID = int(os.environ.get("API_ID", "123456"))
API_HASH = os.environ.get("API_HASH", "your_api_hash")
BOT_TOKEN = "8786795965:AAGNqLwTHBvM7su8NPS53Ah9AOjEZ3W6DFE"

app = Client("pdf_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_modes = {}

@app.on_message(filters.command("start"))
async def start_cmd(client, message):
    await message.reply_text("👋 **PDF Bot Active Hai!**\n\nAb aap **2 GB tak ki PDF** easily invert kar sakte ho.\n\nSend any PDF to get started!")

@app.on_message(filters.command("classic_invert"))
async def set_invert_mode(client, message):
    user_id = message.from_user.id
    user_modes[user_id] = "invert"
    await message.reply_text("✨ **Classic Invert Mode Enabled!**\nAb agli PDF bhejoge toh dark mode (inverted) ho jayegi.")

@app.on_message(filters.document)
async def handle_document(client, message):
    if not message.document.file_name.endswith('.pdf'):
        await message.reply_text("⚠️ Kripya sirf PDF file hi bhejein!")
        return

    status_msg = await message.reply_text("⏳ Processing your PDF (Up to 2 GB supported)... Please wait...")
    
    input_path = await message.download()
    output_path = f"processed_{message.document.file_name}"

    try:
        doc = fitz.open(input_path)
        for page in doc:
            pix = page.get_pixmap()
            pix.invert_irect(pix.rect)
        doc.save(output_path)
        doc.close()

        await message.reply_document(output_path, caption="✅ Here is your inverted PDF!")

    except Exception as e:
        await message.reply_text(f"❌ Error during processing: {str(e)}")

    finally:
        if os.path.exists(input_path):
            os.remove(input_path)
        if os.path.exists(output_path):
            os.remove(output_path)
        await status_msg.delete()

async def main():
    await app.start()
    print("Bot started successfully!")
    await asyncio.gather(*(asyncio.Event().wait(),))

if __name__ == "__main__":
    asyncio.run(main())
