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
from django.conf import settings
from django.db import connection
from django.core.exceptions import ObjectDoesNotExist
import time
from datetime import timedelta
import whisper
import asyncio

# Cargar modelo Whisper una sola vez
WHISPER_MODEL = None

def get_whisper_model():
    global WHISPER_MODEL
    if WHISPER_MODEL is None:
        try:
            # Modelo small: mejor precisión manteniendo velocidad razonable
            WHISPER_MODEL = whisper.load_model("small")
        except Exception as e:
            logging.getLogger(__name__).error(f"No se pudo cargar el modelo Whisper: {e}")
            WHISPER_MODEL = None
    return WHISPER_MODEL

# Inicializa Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web.settings')
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
django.setup()

from accounts.models import CustomUser
from worklog.models import WorkLog

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Constantes para los estados de la conversación ---
SELECTING_TASK_TYPE, ENTERING_DESCRIPTION, SELECTING_STATUS, ENTERING_DURATION, ASK_COLLABORATOR, SELECTING_COLLABORATOR = range(6)

# --- Funciones Auxiliares ---
def get_user_from_chat(chat_id):
    """Obtiene el usuario desde el chat_id con manejo de errores de conexión"""
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            # Verificar si la conexión está activa
            if connection.connection is None or not connection.is_usable():
                connection.close()
                connection.ensure_connection()
            
            return CustomUser.objects.get(telegram_chat_id=chat_id)
        except Exception as e:
            logger.error(f"Error al obtener usuario (intento {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                try:
                    connection.close()
                    connection.ensure_connection()
                except:
                    pass
            else:
                logger.error(f"Falló al obtener usuario después de {max_retries} intentos")
                return None
    return None

def ensure_db_connection():
    """Asegura que la conexión a la base de datos esté activa"""
    try:
        if connection.connection is None or not connection.is_usable():
            connection.close()
            connection.ensure_connection()
        return True
    except Exception as e:
        logger.error(f"Error al conectar a la base de datos: {e}")
        return False

# --- Comandos del Bot ---

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.effective_chat.id
        user = get_user_from_chat(chat_id)

        if user:
            await update.message.reply_text(f"Hola {user.get_full_name()} 👷‍♂️\nUsá /tareas para ver tus tareas o /nueva_tarea para crear una.")
        else:
            await update.message.reply_text("🚫 No estás autorizado. Agregá tu chat ID en tu perfil desde la web.")
    except Exception as e:
        logger.error(f"Error en comando /start: {e}")
        await update.message.reply_text("❌ Error interno del bot. Por favor, intenta más tarde.")

# /tareas
async def tareas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not ensure_db_connection():
            await update.message.reply_text("❌ Error de conexión a la base de datos. Intenta más tarde.")
            return

        chat_id = update.effective_chat.id
        user = get_user_from_chat(chat_id)

        if not user:
            await update.message.reply_text("🚫 No estás autorizado.")
            return

        hoy = timezone.now()
        hace_un_mes = hoy - timedelta(days=30)
        
        # Obtener tareas con manejo de errores
        try:
            tareas = WorkLog.objects.filter(technician=user, start__gte=hace_un_mes).order_by('-start')
        except Exception as e:
            logger.error(f"Error al obtener tareas: {e}")
            await update.message.reply_text("❌ Error al obtener las tareas. Intenta más tarde.")
            return

        if not tareas.exists():
            await update.message.reply_text("No tenés tareas cargadas en el último mes.")
            return

        buttons = []
        for tarea in tareas:
            texto = f"{tarea.start.strftime('%d-%m %H:%M')} - {tarea.description[:40]}"
            buttons.append([InlineKeyboardButton(texto, callback_data=f"ver_tarea:{tarea.id}")])

        await update.message.reply_text("📋 Tareas del último mes:", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        logger.error(f"Error en comando /tareas: {e}")
        await update.message.reply_text("❌ Error interno del bot. Por favor, intenta más tarde.")

# Muestra detalle al tocar una tarea
async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()

        if query.data.startswith("ver_tarea:"):
            if not ensure_db_connection():
                await query.edit_message_text("❌ Error de conexión. Intenta más tarde.")
                return

            tarea_id = int(query.data.split(":")[1])
            try:
                tarea = WorkLog.objects.get(id=tarea_id)
                mensaje = (
                    f"🧑 Técnico: {tarea.technician.get_full_name()}\n"
                    f"📆 Inicio: {tarea.start.strftime('%Y-%m-%d %H:%M')}\n"
                    f"📆 Fin: {tarea.end.strftime('%Y-%m-%d %H:%M')}\n"
                    f"⏱️ Duración: {tarea.duration()} hs\n"
                    f"🔧 Tipo: {tarea.task_type} {'('+tarea.other_task_type+')' if tarea.task_type == 'Otros' else ''}\n"
                    f"📝 Descripción:\n{tarea.description}\n"
                    f"👥 Colaborador: {tarea.collaborator.get_full_name() if tarea.collaborator else 'Ninguno'}"
                )
                await query.edit_message_text(mensaje)
            except WorkLog.DoesNotExist:
                await query.edit_message_text("⚠️ La tarea no existe.")
            except Exception as e:
                logger.error(f"Error al mostrar tarea: {e}")
                await query.edit_message_text("❌ Error al mostrar la tarea.")
    except Exception as e:
        logger.error(f"Error en callback_query_handler: {e}")
        try:
            await update.callback_query.edit_message_text("❌ Error interno del bot.")
        except:
            pass

# --- Funciones para la conversación /nueva_tarea ---

async def nueva_tarea_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not ensure_db_connection():
            await update.message.reply_text("❌ Error de conexión a la base de datos. Intenta más tarde.")
            return ConversationHandler.END

        chat_id = update.effective_chat.id
        user = get_user_from_chat(chat_id)

        if not user:
            await update.message.reply_text("🚫 No estás autorizado.")
            return ConversationHandler.END

        context.user_data['technician'] = user

        # Obtener los tipos de tarea disponibles desde el modelo WorkLog
        task_type_choices = WorkLog._meta.get_field('task_type').choices
        buttons = [[InlineKeyboardButton(label, callback_data=f"task_type:{value}")] for value, label in task_type_choices]
        buttons.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancelar")])
        reply_markup = InlineKeyboardMarkup(buttons)

        await update.message.reply_text(
            "🛠️ ¿Qué tipo de tarea vas a registrar?",
            reply_markup=reply_markup
        )
        return SELECTING_TASK_TYPE
    except Exception as e:
        logger.error(f"Error en nueva_tarea_start: {e}")
        await update.message.reply_text("❌ Error interno del bot. Por favor, intenta más tarde.")
        return ConversationHandler.END

async def select_task_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        task_type_value = query.data.split(":")[1]
        context.user_data['task_type'] = task_type_value

        await query.edit_message_text(
            "📝 Enviá la descripción de la tarea (texto o audio)."
        )
        return ENTERING_DESCRIPTION
    except Exception as e:
        logger.error(f"Error en select_task_type: {e}")
        try:
            await update.callback_query.edit_message_text("❌ Error interno del bot.")
        except:
            pass
        return ConversationHandler.END

async def enter_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        description = ""
        if update.message.text:
            description = update.message.text
            logger.info(f"Descripción recibida como texto: {description}")
        elif update.message.voice:
            voice_file = await update.message.voice.get_file()
            file_extension = voice_file.file_path.split('.')[-1]
            file_name = f"voice_message_{update.effective_chat.id}_{timezone.now().timestamp()}.{file_extension}"
            audio_save_path = os.path.join(settings.MEDIA_ROOT, 'worklog_audios', file_name)
            os.makedirs(os.path.dirname(audio_save_path), exist_ok=True)
            await voice_file.download_to_drive(audio_save_path)
            logger.info(f"Audio descargado a: {audio_save_path}")
            # Guardar ruta relativa para FileField
            relative_path = os.path.relpath(audio_save_path, settings.MEDIA_ROOT)
            context.user_data['audio_file_relative'] = relative_path

            # Iniciar transcripción en segundo plano y continuar inmediatamente
            description = "[Audio adjunto - Transcribiendo...]"
            context.user_data['pending_transcription'] = audio_save_path
            
            # Mensaje inmediato para el usuario
            await update.message.reply_text("🎵 Audio recibido! Continuando con la tarea...")
            
            # Iniciar transcripción en segundo plano
            asyncio.create_task(process_transcription_background(update.effective_chat.id, audio_save_path, context))
        else:
            await update.message.reply_text("Por favor, enviá la descripción como texto o audio.")
            return ENTERING_DESCRIPTION

        context.user_data['description'] = description

        # Preguntar ESTADO inmediatamente
        status_choices = WorkLog._meta.get_field('status').choices
        buttons = [[InlineKeyboardButton(label, callback_data=f"status:{value}")] for value, label in status_choices]
        buttons.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancelar")])
        await update.message.reply_text(
            "📌 Seleccioná el estado de la tarea:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return SELECTING_STATUS
    except Exception as e:
        logger.error(f"Error en enter_description: {e}")
        await update.message.reply_text("❌ Error al procesar la descripción. Intenta de nuevo.")
        return ENTERING_DESCRIPTION

async def process_transcription_background(chat_id: int, audio_path: str, context: ContextTypes.DEFAULT_TYPE):
    """Procesa la transcripción en segundo plano y actualiza el contexto"""
    try:
        model = get_whisper_model()
        if model is None:
            logger.error("Modelo Whisper no disponible para transcripción en segundo plano")
            return
        
        # Transcribir el audio
        result = model.transcribe(audio_path, language="es", fp16=False)
        text = (result or {}).get('text', '').strip()
        
        if text:
            # Actualizar la descripción en el contexto
            context.user_data['description'] = text
            context.user_data['transcription_complete'] = True
            
            # Notificar al usuario que la transcripción está lista
            try:
                from telegram import Bot
                bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'))
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"✅ Transcripción lista: {text[:200]}{'...' if len(text) > 200 else ''}"
                )
            except Exception as e:
                logger.error(f"Error enviando notificación de transcripción: {e}")
        else:
            logger.warning("No se pudo extraer texto del audio en transcripción en segundo plano")
            
    except Exception as e:
        logger.error(f"Error en transcripción en segundo plano: {e}")
        # En caso de error, mantener la descripción como "[Audio adjunto]"
        context.user_data['description'] = "[Audio adjunto]"

async def select_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        if query.data.startswith("status:"):
            status_value = query.data.split(":")[1]
            context.user_data['status'] = status_value
            await query.edit_message_text(
                "⏱️ Indicá la duración en formato H:MM (ej. 1:45 para 1 hora 45 minutos, 0:24 para 24 minutos)."
            )
            return ENTERING_DURATION
        await query.edit_message_text("Selección inválida.")
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error en select_status: {e}")
        try:
            await update.callback_query.edit_message_text("❌ Error interno del bot.")
        except:
            pass
        return ConversationHandler.END

# Parseo de duración H:MM a timedelta
def parse_hhmm_to_timedelta(text: str) -> timedelta:
    text = text.strip()
    if ':' in text:
        parts = text.split(':')
        if len(parts) != 2:
            raise ValueError("Formato inválido")
        hours = int(parts[0]) if parts[0] else 0
        minutes = int(parts[1]) if parts[1] else 0
    else:
        # Permitir solo minutos si el usuario pone, por ejemplo, 24
        if not text.isdigit():
            raise ValueError("Formato inválido")
        hours = 0
        minutes = int(text)
    if minutes < 0 or minutes >= 60 or hours < 0:
        raise ValueError("Minutos deben ser 0-59")
    return timedelta(hours=hours, minutes=minutes)

async def enter_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        duration_str = update.message.text
        td = parse_hhmm_to_timedelta(duration_str)
        context.user_data['duration_td'] = td

        # Preguntar si trabajó con colaborador
        buttons = [
            [InlineKeyboardButton("Sí", callback_data="colaborador_si")],
            [InlineKeyboardButton("No", callback_data="colaborador_no")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="cancelar")]
        ]
        await update.message.reply_text(
            "¿Trabajaste con un colaborador?",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return ASK_COLLABORATOR
    except Exception:
        await update.message.reply_text("Formato inválido. Usá H:MM (ej. 1:30) o minutos (ej. 24).")
        return ENTERING_DURATION

async def ask_collaborator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        if query.data == "colaborador_si":
            if not ensure_db_connection():
                await query.edit_message_text("❌ Error de conexión. Intenta más tarde.")
                return ConversationHandler.END

            # Mostrar lista de técnicos
            tecnicos = CustomUser.objects.filter(user_type='tecnico').exclude(id=context.user_data['technician'].id)
            if not tecnicos.exists():
                await query.edit_message_text("No hay otros técnicos disponibles para seleccionar como colaborador.")
                context.user_data['collaborator'] = None
                return await save_task(update, context)
            buttons = [
                [InlineKeyboardButton(f"{t.get_full_name()} ({t.username})", callback_data=f"colaborador_id:{t.id}")]
                for t in tecnicos
            ]
            buttons.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancelar")])
            await query.edit_message_text(
                "Seleccioná el colaborador:",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            return SELECTING_COLLABORATOR
        else:
            context.user_data['collaborator'] = None
            await query.edit_message_text("No se seleccionó colaborador.")
            return await save_task(update, context)
    except Exception as e:
        logger.error(f"Error en ask_collaborator: {e}")
        try:
            await update.callback_query.edit_message_text("❌ Error interno del bot.")
        except:
            pass
        return ConversationHandler.END

async def select_collaborator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        if query.data.startswith("colaborador_id:"):
            colaborador_id = int(query.data.split(":")[1])
            colaborador = CustomUser.objects.filter(id=colaborador_id, user_type='tecnico').first()
            if colaborador:
                context.user_data['collaborator'] = colaborador
                await query.edit_message_text(f"Colaborador seleccionado: {colaborador.get_full_name()} ({colaborador.username})")
            else:
                await query.edit_message_text("Colaborador inválido.")
                context.user_data['collaborator'] = None
            return await save_task(update, context)
        else:
            await query.edit_message_text("Selección inválida.")
            return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error en select_collaborator: {e}")
        try:
            await update.callback_query.edit_message_text("❌ Error interno del bot.")
        except:
            pass
        return ConversationHandler.END

async def save_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not ensure_db_connection():
            await update.effective_chat.send_message("❌ Error de conexión a la base de datos. No se pudo guardar la tarea.")
            return ConversationHandler.END

        user = context.user_data['technician']
        end_time = timezone.now()
        duration_td = context.user_data.get('duration_td', timedelta())
        start_time = end_time - duration_td
        task_type = context.user_data['task_type']
        status_value = context.user_data.get('status', 'pendiente')
        collaborator = context.user_data.get('collaborator')
        audio_file_relative = context.user_data.get('audio_file_relative')
        
        # Usar la transcripción completa si está disponible
        final_description = context.user_data.get('description')
        if context.user_data.get('transcription_complete') and context.user_data.get('pending_transcription'):
            # Si la transcripción se completó, usar el texto transcrito
            final_description = context.user_data.get('description')
        elif context.user_data.get('pending_transcription'):
            # Si aún está transcribiendo, mantener el marcador
            final_description = "[Audio adjunto - Transcribiendo...]"
        
        # Guardar la tarea
        worklog = WorkLog.objects.create(
            technician=user,
            collaborator=collaborator,
            start=start_time,
            end=end_time,
            task_type=task_type,
            description=final_description,
            status=status_value,
            created_by=user,
            audio_file=audio_file_relative if audio_file_relative else None,
        )
        
        await update.effective_chat.send_message("✅ Tarea registrada correctamente.")
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error al guardar tarea: {e}")
        await update.effective_chat.send_message("❌ Error al guardar la tarea. Por favor, intenta más tarde.")
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text("❌ Operación cancelada.")
        else:
            await update.message.reply_text("❌ Operación cancelada.")
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error en cancel: {e}")
        return ConversationHandler.END

# --- Main Bot Setup ---
def main():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN no definido en .env")
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
            SELECTING_TASK_TYPE: [
                CallbackQueryHandler(select_task_type, pattern="^task_type:"), 
                CallbackQueryHandler(cancel, pattern="^cancelar$")
            ],
            ENTERING_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_description),
                MessageHandler(filters.VOICE, enter_description),
                CallbackQueryHandler(cancel, pattern="^cancelar$")
            ],
            SELECTING_STATUS: [
                CallbackQueryHandler(select_status, pattern="^status:"),
                CallbackQueryHandler(cancel, pattern="^cancelar$")
            ],
            ENTERING_DURATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_duration), 
                CallbackQueryHandler(cancel, pattern="^cancelar$")
            ],
            ASK_COLLABORATOR: [
                CallbackQueryHandler(ask_collaborator, pattern="^colaborador_"), 
                CallbackQueryHandler(cancel, pattern="^cancelar$")
            ],
            SELECTING_COLLABORATOR: [
                CallbackQueryHandler(select_collaborator, pattern="^colaborador_id:"), 
                CallbackQueryHandler(cancel, pattern="^cancelar$")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
    application.add_handler(nueva_tarea_conv_handler)

    logger.info("Bot iniciado...")
    application.run_polling()

if __name__ == "__main__":
    main()