import os
import logging
import telebot
from telebot import types
import ffmpeg
import docx2txt
from pdf2docx import Converter


# Note: docx2pdf requires Microsoft Word to be installed (Windows/macOS). 
# If hosting on Linux, consider using LibreOffice via CLI instead.
from docx2pdf import convert as convert_pdf


TOKEN = "Your Telegram Bot Token Here"  # Replace with your actual token
if not TOKEN:
    raise ValueError("No TELEGRAM_BOT_TOKEN found.")

bot = telebot.TeleBot(TOKEN)

# Logging setup
logger = telebot.logger
logger.setLevel(logging.INFO)


# Folder setup
PROJ_DIR = 'cur_proj'
if not os.path.exists(PROJ_DIR):
    os.makedirs(PROJ_DIR)

# Telegram's max download size for bots is 20MB
MAX_FILE_SIZE = 20 * 1024 * 1024 


@bot.message_handler(commands=['start'])
def start_msg(message):
    welcome_text = (
        "👋 *Hello! I am a File Converter Bot.*\n\n"
        "Send me an image, video, audio, PDF, or Word document, and I will convert it for you.\n"
        "*(Note: Maximum file size is 20MB)*"
    )
    bot.send_message(message.chat.id, text=welcome_text, parse_mode='Markdown')


@bot.message_handler(commands=["help"])
def help_msg(message):
    help_text = (
        "ℹ️ How to use:\n\n"
        "1. Send or forward a supported file.\n"
        "2. Choose the output format from the buttons.\n"
        "3. Receive your converted file.\n\n"
        "Commands:\n"
        "/start - Welcome message\n"
        "/help - Help message\n"
        "/formats - List all supported formats\n\n"
        "⚠️ Files are deleted from the server immediately after conversion."
    )
    bot.send_message(message.chat.id, text=help_text, parse_mode='Markdown')

@bot.message_handler(commands=["formats"])
def formats_msg(message):
    formats_text = (
        "📁 Supported Formats:\n\n"
        "🖼️ Images: JPG, PNG, JPEG, WEBP\n"
        "🎞️ Videos: MP4, AVI, MKV, MOV, GIF\n"
        "🎵 Audio: MP3, WAV, OGG, M4A, FLAC, Voice Note (OGG)\n"
        "📄 Documents: DOCX ↔ PDF, TXT (from DOCX)\n\n"
        "⚠️ Note: PDF to TXT conversion is not natively supported in this bot."
    )
    bot.send_message(message.chat.id, text=formats_text, parse_mode='Markdown')

@bot.message_handler(content_types=['photo', 'document', 'video', 'audio', 'animation'])
def handle_files(message):
    file_id = None
    ext = ''
    file_size = 0
    
    # Handle different content types and extract sizes
    try:
        if message.content_type == 'photo':
            file_info = message.photo[-1]
            file_id = file_info.file_id
            ext = '.jpg'
            file_size = file_info.file_size
        elif message.content_type == 'document':
            file_id = message.document.file_id
            ext = os.path.splitext(message.document.file_name)[1].lower()
            file_size = message.document.file_size
        elif message.content_type == 'video':
            file_id = message.video.file_id
            ext = os.path.splitext(message.video.file_name)[1].lower() if message.video.file_name else '.mp4'
            file_size = message.video.file_size
        elif message.content_type == 'animation':
            file_id = message.animation.file_id
            ext = os.path.splitext(message.animation.file_name)[1].lower() if message.animation.file_name else '.gif'
            file_size = message.animation.file_size
        elif message.content_type == 'audio':
            file_id = message.audio.file_id
            ext = os.path.splitext(message.audio.file_name)[1].lower() if message.audio.file_name else '.mp3'
            file_size = message.audio.file_size
            
        if not file_id:
            bot.reply_to(message, "⚠️ Could not process this file type.")
            return

        # File size limit check
        if file_size > MAX_FILE_SIZE:
            bot.reply_to(message, "❌ File is too large. Telegram bots can only download files up to 20MB.")
            return

        bot.send_chat_action(message.chat.id, 'typing')
        
        # Download file
        bot_file = bot.get_file(file_id)
        downloaded_file = bot.download_file(bot_file.file_path)
        
        # chat_id AND message_id to prevent collision between users
        unique_prefix = f"{message.chat.id}_{message.message_id}"
        orig_path = os.path.join(PROJ_DIR, f"{unique_prefix}{ext}")
        
        with open(orig_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        # Button markup based on file type
        markup = types.InlineKeyboardMarkup(row_width=3)
        
        if ext in ['.jpg', '.jpeg', '.png', '.webp']:
            markup.add(
                types.InlineKeyboardButton('PNG', callback_data=f'img_png_{ext}'),
                types.InlineKeyboardButton('JPG', callback_data=f'img_jpg_{ext}'),
                types.InlineKeyboardButton('JPEG', callback_data=f'img_jpeg_{ext}'),
                types.InlineKeyboardButton('WEBP', callback_data=f'img_webp_{ext}')
            )
        elif ext in ['.mp4', '.avi', '.mkv', '.mov']:
            markup.add(
                types.InlineKeyboardButton('MP4', callback_data=f'vid_mp4_{ext}'),
                types.InlineKeyboardButton('AVI', callback_data=f'vid_avi_{ext}'),
                types.InlineKeyboardButton('MKV', callback_data=f'vid_mkv_{ext}'),
                types.InlineKeyboardButton('MOV', callback_data=f'vid_mov_{ext}'),
                types.InlineKeyboardButton('GIF', callback_data=f'vid_gif_{ext}')
            )
        elif ext in ['.gif']:
            markup.add(
                types.InlineKeyboardButton('MP4', callback_data=f'gif_mp4_{ext}'),
                types.InlineKeyboardButton('MOV', callback_data=f'gif_mov_{ext}'),
                types.InlineKeyboardButton('AVI', callback_data=f'gif_avi_{ext}')
            )
        elif ext in ['.mp3', '.wav', '.ogg', '.m4a', '.flac']:
            markup.add(
                types.InlineKeyboardButton('MP3', callback_data=f'aud_mp3_{ext}'),
                types.InlineKeyboardButton('WAV', callback_data=f'aud_wav_{ext}'),
                types.InlineKeyboardButton('M4A', callback_data=f'aud_m4a_{ext}'),
                types.InlineKeyboardButton('FLAC', callback_data=f'aud_flac_{ext}'),
                types.InlineKeyboardButton('Voice Note', callback_data=f'aud_voice_{ext}')
            )
        elif ext in ['.docx']:
            markup.add(
                types.InlineKeyboardButton('PDF', callback_data=f'doc_pdf_{ext}'),
                types.InlineKeyboardButton('Text (TXT)', callback_data=f'doc_txt_{ext}')
            )
        elif ext in ['.pdf']:
            markup.add(
                types.InlineKeyboardButton('Word (DOCX)', callback_data=f'pdf_docx_{ext}'),
                types.InlineKeyboardButton('Text (TXT)', callback_data=f'pdf_txt_{ext}')
            )
        else:
            bot.reply_to(message, f"⚠️ Unsupported file extension: {ext}")
            os.remove(orig_path)
            return

        # Add a cancel button
        markup.add(types.InlineKeyboardButton('❌ Cancel', callback_data=f'cancel_none_{ext}'))
        bot.reply_to(message, '⚙️ Choose the format you want to convert to:', reply_markup=markup)

    except Exception as e:
        logger.error(f"Download Error: {e}")
        bot.reply_to(message, "❌ An error occurred while downloading the file. Please try again.")


@bot.callback_query_handler(func=lambda call: True)
def process_conversion(call):
    # Retrieve ids
    chat_id = call.message.chat.id
    target_id = call.message.reply_to_message.message_id
    unique_prefix = f"{chat_id}_{target_id}"
    
    data_parts = call.data.split('_', 2)
    if len(data_parts) != 3:
        return

    file_type, target_fmt, orig_ext = data_parts
    orig_path = os.path.join(PROJ_DIR, f"{unique_prefix}{orig_ext}")
    out_path = os.path.join(PROJ_DIR, f"{unique_prefix}_out.{target_fmt}")

    # Handle Cancellation
    if file_type == 'cancel':
        bot.delete_message(chat_id, call.message.message_id)
        if os.path.exists(orig_path):
            os.remove(orig_path)
        return

    if not os.path.exists(orig_path):
        bot.answer_callback_query(call.id, "⚠️ Original file not found. It may have expired or been deleted.", show_alert=True)
        bot.delete_message(chat_id, call.message.message_id)
        return

    bot.edit_message_text("⏳ Processing your file... Please wait.", chat_id, call.message.message_id)
    
    
    conversion_successful = False # Conversion status flag for cleanup logic

    try:
        # Image/Video/GIF conversions
        if file_type in ['img', 'vid', 'gif']:
            bot.send_chat_action(chat_id, 'upload_video' if file_type in ['vid', 'gif'] else 'upload_photo')
            if file_type == 'gif':
                ffmpeg.input(filename=orig_path).output(
                    filename=out_path, vcodec='libx264', pix_fmt='yuv420p', vf='scale=trunc(iw/2)*2:trunc(ih/2)*2', an=None
                ).run(overwrite_output=True, quiet=True)
            else:
                ffmpeg.input(filename=orig_path).output(filename=out_path).run(overwrite_output=True, quiet=True)

            with open(out_path, 'rb') as f:
                if target_fmt == 'gif':
                    bot.send_animation(chat_id, f)
                elif target_fmt in ['mp4', 'avi', 'mkv', 'mov']:
                    bot.send_video(chat_id, f)
                else:
                    bot.send_document(chat_id, f)
            conversion_successful = True

        # Audio conversions
        elif file_type == 'aud':
            bot.send_chat_action(chat_id, 'upload_audio')
            if target_fmt == 'voice':
                out_path = os.path.join(PROJ_DIR, f"{unique_prefix}.ogg")
                ffmpeg.input(orig_path).output(out_path, acodec='libopus').run(overwrite_output=True, quiet=True)
                with open(out_path, 'rb') as f:
                    bot.send_voice(chat_id, f)
            else:
                ffmpeg.input(orig_path).output(out_path).run(overwrite_output=True, quiet=True)
                with open(out_path, 'rb') as f:
                    bot.send_audio(chat_id, f)
            conversion_successful = True

        # Document (.docx)
        elif file_type == 'doc':
            bot.send_chat_action(chat_id, 'upload_document')
            if target_fmt == 'pdf':
                convert_pdf(orig_path, out_path)
                with open(out_path, 'rb') as f:
                    bot.send_document(chat_id, f)
            elif target_fmt == 'txt':
                text_content = docx2txt.process(orig_path)
                with open(out_path, 'w', encoding='utf-8') as f:
                    f.write(text_content)
                with open(out_path, 'rb') as f:
                    bot.send_document(chat_id, f)
            conversion_successful = True

        # Document (.pdf)
        elif file_type == 'pdf':
            bot.send_chat_action(chat_id, 'upload_document')
            if target_fmt == 'docx':
                cv = Converter(orig_path)
                cv.convert(out_path)
                cv.close()
                with open(out_path, 'rb') as f:
                    bot.send_document(chat_id, f)
            elif target_fmt == 'txt':
                # Send a message that PDF to TXT conversion is not supported
                raise NotImplementedError("PDF to TXT not supported without PyPDF2.")
            conversion_successful = True

        # Clean up
        if conversion_successful:
            bot.delete_message(chat_id, call.message.message_id)
    # Error handling
    except Exception as e:
        logger.error(f"Conversion Error: {e}")
        bot.edit_message_text(f"❌ An error occurred during conversion:\n`{str(e)}`", chat_id, call.message.message_id, parse_mode="Markdown")
        
    finally:
        # Deleting files after conversion
        if 'orig_path' in locals() and os.path.exists(orig_path):
            os.remove(orig_path)
        if 'out_path' in locals() and os.path.exists(out_path):
            os.remove(out_path)

if __name__ == '__main__':
    bot.infinity_polling()
