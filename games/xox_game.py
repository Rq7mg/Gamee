from telegram import Update
from telegram.ext import CallbackQueryHandler, ContextTypes

async def xox_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data != "xox":
        return
    await query.edit_message_text("⭕ XOX başladı! (Placeholder)")
