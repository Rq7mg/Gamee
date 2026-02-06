from telegram import Update
from telegram.ext import CallbackQueryHandler, ContextTypes
import random

async def truth_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data != "dogruluk":
        return
    choices = ["Doğruluk: En son kime yalan söyledin?", "Cesaret: 10 şınav çek!"]
    await query.edit_message_text(random.choice(choices))
