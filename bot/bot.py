import os
import django
import logging
from datetime import timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes

# Inicializa Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web.settings')  # Ajustá el nombre del proyecto si no es "core"
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
django.setup()

from accounts.models import CustomUser
from worklog.models import WorkLog
from django.utils import timezone

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Verifica si el chat_id está autorizado
def get_user_from_chat(chat_id):
    try:
        return CustomUser.objects.get(telegram_chat_id=chat_id)
    except CustomUser.DoesNotExist:
        return None

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = get_user_from_chat(chat_id)

    if user:
        await update.message.reply_text(f"Hola {user.get_full_name()} 👷‍♂️\nUsá /tareas para ver tus tareas o /nueva_tarea para crear una.")
    else:
        await update.message.reply_text("🚫 No estás autorizado. Agregá tu chat ID en tu perfil desde la web.")

# /tareas
async def tareas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = get_user_from_chat(chat_id)

    if not user:
        await update.message.reply_text("🚫 No estás autorizado.")
        return

    hoy = timezone.now()
    hace_un_mes = hoy - timedelta(days=30)
    tareas = WorkLog.objects.filter(technician=user, start__gte=hace_un_mes).order_by('-start')

    if not tareas.exists():
        await update.message.reply_text("No tenés tareas cargadas en el último mes.")
        return

    buttons = []
    for tarea in tareas:
        texto = f"{tarea.start.strftime('%d-%m %H:%M')} - {tarea.description[:40]}"
        buttons.append([InlineKeyboardButton(texto, callback_data=f"ver_tarea:{tarea.id}")])

    await update.message.reply_text("📋 Tareas del último mes:", reply_markup=InlineKeyboardMarkup(buttons))

# Muestra detalle al tocar una tarea
async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("ver_tarea:"):
        tarea_id = int(query.data.split(":")[1])
        try:
            tarea = WorkLog.objects.get(id=tarea_id)
            mensaje = (
                f"🧑 Técnico: {tarea.technician.get_full_name()}\n"
                f"📆 Inicio: {tarea.start.strftime('%Y-%m-%d %H:%M')}\n"
                f"📆 Fin: {tarea.end.strftime('%Y-%m-%d %H:%M')}\n"
                f"⏱️ Duración: {tarea.duration()} hs\n"
                f"🔧 Tipo: {tarea.task_type} {'('+tarea.other_task_type+')' if tarea.task_type == 'Otros' else ''}\n"
                f"📝 Descripción:\n{tarea.description}"
            )
            await query.edit_message_text(mensaje)
        except WorkLog.DoesNotExist:
            await query.edit_message_text("⚠️ La tarea no existe.")

# Main
def main():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        raise Exception("TELEGRAM_BOT_TOKEN no definido en .env")

    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("tareas", tareas))
    application.add_handler(telegram.ext.CallbackQueryHandler(callback_query_handler))

    logger.info("Bot iniciado...")
    application.run_polling()

if __name__ == "__main__":
    main()
