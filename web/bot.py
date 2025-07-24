import os
import django
import logging
from datetime import timedelta
import telegram.ext
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)
from django.utils import timezone
from django.conf import settings # Para acceder a MEDIA_ROOT

# Inicializa Django
# Asegúrate de que 'web.settings' sea el path correcto a tu archivo settings.py
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web.settings')
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
django.setup()

from accounts.models import CustomUser
from worklog.models import WorkLog

# Importar aquí tu función de transcripción.
# Por ahora, usaré un placeholder. ¡Necesitarás implementarla!
# Ejemplo: from .audio_processor import transcribe_audio
def transcribe_audio_placeholder(audio_file_path):
    """
    Función placeholder para transcribir audio.
    Deberás reemplazarla con una implementación real (ej. con Google Speech-to-Text, Whisper, etc.).
    """
    logger.info(f"Transcribiendo audio de: {audio_file_path}")
    # Simula una transcripción
    return "Esta es una transcripción de prueba del audio."

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Constantes para los estados de la conversación ---
SELECTING_TASK_TYPE, ENTERING_DESCRIPTION, ENTERING_DURATION = range(3)

# --- Funciones Auxiliares ---
def get_user_from_chat(chat_id):
    try:
        return CustomUser.objects.get(telegram_chat_id=chat_id)
    except CustomUser.DoesNotExist:
        return None

# --- Comandos del Bot ---

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

# --- Funciones para la conversación /nueva_tarea ---

async def nueva_tarea_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = get_user_from_chat(chat_id)

    if not user:
        await update.message.reply_text("🚫 No estás autorizado.")
        return ConversationHandler.END

    context.user_data['technician'] = user
    context.user_data['start_time'] = timezone.now() # Captura el inicio de la tarea

    # Obtener los tipos de tarea disponibles desde el modelo WorkLog
    task_type_choices = WorkLog._meta.get_field('task_type').choices
    buttons = [[InlineKeyboardButton(label, callback_data=f"task_type:{value}")] for value, label in task_type_choices]
    reply_markup = InlineKeyboardMarkup(buttons)

    await update.message.reply_text(
        "🛠️ ¿Qué tipo de tarea vas a registrar?",
        reply_markup=reply_markup
    )
    return SELECTING_TASK_TYPE

async def select_task_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    task_type_value = query.data.split(":")[1]
    context.user_data['task_type'] = task_type_value

    if task_type_value == 'Otros':
        # Si es "Otros", pedimos una descripción más específica para 'other_task_type'
        await query.edit_message_text("Por favor, describe brevemente qué tipo de 'Otros' es.")
        # Podrías crear otro estado o manejarlo dentro de ENTERING_DESCRIPTION si prefieres.
        # Por simplicidad, asumiré que se manejará en la descripción principal por ahora.
        # Si necesitas un campo separado para 'other_task_type', deberás añadir un estado más.
    else:
        await query.edit_message_text(f"Has seleccionado: **{dict(WorkLog._meta.get_field('task_type').choices)[task_type_value]}**\n\n"
                                     "📝 Ahora, por favor, envía la **descripción** de la tarea. Puedes enviarla como texto o como mensaje de voz (audio).")

    return ENTERING_DESCRIPTION

async def enter_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    description = ""
    if update.message.text:
        description = update.message.text
        logger.info(f"Descripción recibida como texto: {description}")
    elif update.message.voice:
        voice_file = await update.message.voice.get_file()
        # Define la ruta donde guardar el archivo de audio.
        # Es crucial que esta ruta sea accesible por tu función de transcripción
        # y que persista entre reinicios del contenedor si es necesario para depuración.
        # Puedes usar os.path.join(settings.MEDIA_ROOT, 'worklog_audios', <filename>)
        # para guardarlo donde está mapeado en docker-compose.
        # Asegúrate de que el directorio exista: os.makedirs(..., exist_ok=True)
        
        # Generar un nombre de archivo único
        file_extension = voice_file.file_path.split('.')[-1]
        file_name = f"voice_message_{update.effective_chat.id}_{timezone.now().timestamp()}.{file_extension}"
        audio_save_path = os.path.join(settings.MEDIA_ROOT, 'worklog_audios', file_name)

        # Asegúrate de que la carpeta de destino exista
        os.makedirs(os.path.dirname(audio_save_path), exist_ok=True)

        await voice_file.download_to_drive(audio_save_path)
        logger.info(f"Audio descargado a: {audio_save_path}")

        # Aquí es donde llamas a tu función real de transcripción
        description = transcribe_audio_placeholder(audio_save_path) # Reemplaza con tu función real
        logger.info(f"Audio transcrito a: {description}")

        await update.message.reply_text(f"🎤 Audio transcrito a texto:\n_\"{description}\"_\n\n", parse_mode='Markdown')
    else:
        await update.message.reply_text("Por favor, envía la descripción como texto o como un mensaje de voz.")
        return ENTERING_DESCRIPTION # Permanece en este estado

    context.user_data['description'] = description
    await update.message.reply_text("⏱️ Ahora, por favor, envía la **duración** de la tarea en **horas decimales** (ej. 1.5 para una hora y media).")
    return ENTERING_DURATION

async def enter_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        duration_str = update.message.text
        duration = float(duration_str.replace(',', '.')) # Permite coma o punto
        if duration <= 0:
            await update.message.reply_text("La duración debe ser un número positivo. Inténtalo de nuevo.")
            return ENTERING_DURATION
        context.user_data['duration_hours'] = duration
    except ValueError:
        await update.message.reply_text("Formato de duración inválido. Por favor, introduce un número en horas decimales (ej. 0.5, 1, 2.75).")
        return ENTERING_DURATION

    # Guardar la tarea en la base de datos
    user = context.user_data['technician']
    start_time = context.user_data['start_time']
    end_time = start_time + timedelta(hours=context.user_data['duration_hours'])
    task_type = context.user_data['task_type']
    description = context.user_data['description']

    # Si el task_type es 'Otros', deberías haber pedido otro_task_type.
    # Por ahora, lo guardaré vacío si no lo tienes.
    other_task_type = ""
    if task_type == 'Otros':
        # Si tienes un estado previo para pedir other_task_type, lo obtendrías de context.user_data
        # Si no, podrías extraerlo de la descripción si es el caso.
        # Para este ejemplo, lo dejaré vacío.
        pass

    WorkLog.objects.create(
        technician=user,
        start=start_time,
        end=end_time,
        task_type=task_type,
        other_task_type=other_task_type, # Asegúrate de manejar esto si 'Otros' necesita un input específico
        description=description,
    )
    logger.info(f"Tarea registrada por {user.username}: {description}")

    await update.message.reply_text(
        f"✅ Tarea registrada con éxito:\n"
        f" Tipo: {dict(WorkLog._meta.get_field('task_type').choices)[task_type]}\n"
        f" Descripción: {description[:100]}...\n"
        f" Duración: {context.user_data['duration_hours']} horas",
        reply_markup=ReplyKeyboardRemove() # Elimina el teclado de opciones si lo usaste
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚫 Creación de tarea cancelada.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

# --- Main Bot Setup ---
def main():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        raise Exception("TELEGRAM_BOT_TOKEN no definido en .env")

    application = Application.builder().token(TOKEN).build()

    # Handlers existentes
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("tareas", tareas))
    application.add_handler(CallbackQueryHandler(callback_query_handler, pattern="^ver_tarea:"))

    # Handler para la conversación de nueva_tarea
    nueva_tarea_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("nueva_tarea", nueva_tarea_start)],
        states={
            SELECTING_TASK_TYPE: [CallbackQueryHandler(select_task_type, pattern="^task_type:")],
            ENTERING_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_description), # Para texto
                MessageHandler(filters.VOICE, enter_description), # Para audio
            ],
            ENTERING_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_duration)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True # Permite iniciar la conversación de nuevo si el bot se reinicia
    )
    application.add_handler(nueva_tarea_conv_handler)


    logger.info("Bot iniciado...")
    application.run_polling()

if __name__ == "__main__":
    main()