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
from django.db import models

# Cargar modelo Whisper una sola vez
WHISPER_MODEL = None

def get_whisper_model():
    global WHISPER_MODEL
    if WHISPER_MODEL is None:
        try:
            logger.info("Cargando modelo Whisper 'small'...")
            # Modelo small: mejor precisión manteniendo velocidad razonable
            WHISPER_MODEL = whisper.load_model("small")
            logger.info("Modelo Whisper 'small' cargado exitosamente")
        except Exception as e:
            logger.error(f"No se pudo cargar el modelo Whisper: {e}")
            WHISPER_MODEL = None
    else:
        logger.info("Modelo Whisper ya está cargado")
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
SELECTING_WORK_ORDER, SELECTING_TASK_TYPE, ENTERING_DESCRIPTION, SELECTING_STATUS, ENTERING_DURATION, ASK_COLLABORATOR, SELECTING_COLLABORATOR = range(7)

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
            await update.message.reply_text(f"Hola {user.get_full_name()} 👷‍♂️\nUsá /tareas para ver tus tareas, /nueva_tarea para crear una o /ver_OTs para ver tus Ordenes de Trabajo.")
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
        
        # Obtener todas las tareas asignadas al usuario o donde es colaborador, excluyendo cerradas
        try:
            tareas = WorkLog.objects.filter(
                models.Q(technician=user) | models.Q(collaborator=user)
            ).exclude(status='cerrada').order_by('-start')
        except Exception as e:
            logger.error(f"Error al obtener tareas: {e}")
            await update.message.reply_text("❌ Error al obtener las tareas. Intenta más tarde.")
            return

        if not tareas.exists():
            await update.message.reply_text("No tenés tareas activas asignadas o donde seas colaborador.")
            return

        buttons = []
        for tarea in tareas:
            # Determinar el rol del usuario en esta tarea
            if tarea.technician == user:
                rol = "👷 Técnico"
            else:
                rol = "🤝 Colaborador"
            
            texto = f"{rol} | {tarea.start.strftime('%d-%m %H:%M')} | {tarea.description[:35]}..."
            buttons.append([InlineKeyboardButton(texto, callback_data=f"ver_tarea:{tarea.id}")])

        # Agregar botón para nueva tarea
        buttons.append([InlineKeyboardButton("➕ Nueva Tarea", callback_data="nueva_tarea_bot")])

        await update.message.reply_text("📋 Tus tareas activas:", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        logger.error(f"Error en comando /tareas: {e}")
        await update.message.reply_text("❌ Error interno del bot. Por favor, intenta más tarde.")

# /ver_OTs - Listar órdenes de trabajo
async def ver_OTs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not ensure_db_connection():
            await update.message.reply_text("❌ Error de conexión a la base de datos. Intenta más tarde.")
            return

        chat_id = update.effective_chat.id
        user = get_user_from_chat(chat_id)

        if not user:
            await update.message.reply_text("🚫 No estás autorizado.")
            return

        # Importar WorkOrder aquí para evitar problemas de importación circular
        try:
            from work_order.models import WorkOrder
        except ImportError:
            await update.message.reply_text("❌ Error: Módulo de órdenes de trabajo no disponible.")
            return

        # Obtener órdenes asignadas al usuario o donde aparece como colaborador
        try:
            # Órdenes asignadas directamente (excluyendo cerradas)
            assigned_orders = WorkOrder.objects.filter(asignado_a=user).exclude(estado='cerrada')
            
            # Órdenes donde el usuario es colaborador en alguna tarea (excluyendo cerradas)
            collaborator_orders = WorkOrder.objects.filter(
                worklogs__collaborator=user
            ).exclude(estado='cerrada').distinct()
            
            # Combinar usando union (ya filtrados)
            all_orders = assigned_orders.union(collaborator_orders)
            
        except Exception as e:
            logger.error(f"Error al obtener órdenes: {e}")
            await update.message.reply_text("❌ Error al obtener las órdenes. Intenta más tarde.")
            return

        if not all_orders.exists():
            await update.message.reply_text("No tenés órdenes de trabajo asignadas o donde seas colaborador.")
            return

        # Crear botones para cada orden
        buttons = []
        for orden in all_orders:
            # Determinar el rol del usuario en esta orden
            if orden.asignado_a == user:
                rol = "👷 Asignado"
            else:
                rol = "🤝 Colaborador"
            
            # Mostrar prioridad con emoji
            prioridad_emoji = {
                'urgente': '🔴',
                'alta': '🟠', 
                'media': '🟡',
                'baja': '🟢'
            }.get(orden.prioridad, '⚪')
            
            texto = f"{prioridad_emoji} {orden.numero} | {rol} | {orden.titulo[:30]}..."
            buttons.append([InlineKeyboardButton(texto, callback_data=f"ver_orden:{orden.id}")])

        # Agregar botón para nueva tarea
        buttons.append([InlineKeyboardButton("➕ Nueva Tarea", callback_data="nueva_tarea_bot")])

        await update.message.reply_text("📋 Tus órdenes de trabajo:", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        logger.error(f"Error en comando /ver_OTs: {e}")
        await update.message.reply_text("❌ Error interno del bot. Por favor, intenta más tarde.")

# Muestra detalle al tocar una tarea o orden
async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()

        if query.data.startswith("ver_tarea:"):
            await show_task_detail(query)
        elif query.data.startswith("ver_orden:"):
            await show_work_order_detail(query)
        elif query.data == "nueva_tarea_bot":
            # Flujo directo para nueva tarea desde botón (sin ConversationHandler)
            await handle_nueva_tarea_direct(query, context)
        elif query.data.startswith("work_order:"):
            # Manejar selección de orden de trabajo desde flujo directo
            await handle_work_order_selection_direct(query, context)
        elif query.data.startswith("task_type:"):
            # Manejar selección de tipo de tarea desde flujo directo
            await handle_task_type_selection_direct(query, context)
        elif query.data.startswith("status_direct:"):
            # Manejar selección de estado desde flujo directo
            await handle_status_selection_direct(query, context)
        elif query.data.startswith("colaborador_direct:"):
            # Manejar selección de colaborador desde flujo directo
            await handle_collaborator_direct(query, context)
        elif query.data.startswith("colaborador_select:"):
            # Manejar selección específica de colaborador
            await handle_collaborator_select_direct(query, context)
        elif query.data == "save_task_direct":
            # Guardar tarea desde flujo directo
            await save_task_direct(query, context)
        elif query.data == "edit_transcription":
            # Editar transcripción
            await edit_transcription_direct(query, context)
        elif query.data == "edit_transcription_text":
            # Editar transcripción por texto
            await handle_edit_transcription_text(query, context)
        elif query.data == "edit_transcription_audio":
            # Editar transcripción por audio
            await handle_edit_transcription_audio(query, context)
        elif query.data == "volver_tareas":
            await tareas(update, context)
        elif query.data == "volver_ordenes":
            await ver_OTs(update, context)
        elif query.data == "cancelar":
            # Manejar cancelación desde cualquier punto del flujo
            await cancel(update, context)
        else:
            await query.edit_message_text("❌ Comando no reconocido.")
            
    except Exception as e:
        logger.error(f"Error en callback_query_handler: {e}")
        try:
            await update.callback_query.edit_message_text("❌ Error interno del bot.")
        except:
            pass

async def show_task_detail(query):
    """Muestra el detalle de una tarea específica"""
    try:
        if not ensure_db_connection():
            await query.edit_message_text("❌ Error de conexión. Intenta más tarde.")
            return

        tarea_id = int(query.data.split(":")[1])
        try:
            tarea = WorkLog.objects.get(id=tarea_id)
            
            # Determinar el rol del usuario en esta tarea
            if tarea.technician == query.from_user.id:
                rol = "👷 Técnico Principal"
            else:
                rol = "🤝 Colaborador"
            
            mensaje = (
                f"📋 <b>Detalle de Tarea</b>\n\n"
                f"{rol}\n"
                f"🧑 Técnico: {tarea.technician.get_full_name()}\n"
                f"📆 Inicio: {tarea.start.strftime('%Y-%m-%d %H:%M')}\n"
                f"📆 Fin: {tarea.end.strftime('%Y-%m-%d %H:%M')}\n"
                f"⏱️ Duración: {tarea.duration()} hs\n"
                f"🔧 Tipo: {tarea.task_type} {'('+tarea.other_task_type+')' if tarea.task_type == 'Otros' else ''}\n"
                f"📊 Estado: {tarea.get_status_display()}\n"
                f"📝 Descripción:\n{tarea.description}\n"
            )
            
            if tarea.collaborator:
                mensaje += f"👥 Colaborador: {tarea.collaborator.get_full_name()}\n"
            
            if tarea.work_order:
                mensaje += f"📋 Orden de Trabajo: {tarea.work_order}\n"
            
            # Botones de acción
            buttons = [
                [InlineKeyboardButton("🔙 Volver a Tareas", callback_data="volver_tareas")],
                [InlineKeyboardButton("➕ Nueva Tarea", callback_data="nueva_tarea_bot")]
            ]
            
            await query.edit_message_text(mensaje, reply_markup=InlineKeyboardMarkup(buttons), parse_mode='HTML')
            
        except WorkLog.DoesNotExist:
            await query.edit_message_text("⚠️ La tarea no existe.")
        except Exception as e:
            logger.error(f"Error al mostrar tarea: {e}")
            await query.edit_message_text("❌ Error al mostrar la tarea.")
    except Exception as e:
        logger.error(f"Error en show_task_detail: {e}")
        await query.edit_message_text("❌ Error interno del bot.")

async def show_work_order_detail(query):
    """Muestra el detalle de una orden de trabajo y sus tareas asociadas"""
    try:
        if not ensure_db_connection():
            await query.edit_message_text("❌ Error de conexión. Intenta más tarde.")
            return

        orden_id = int(query.data.split(":")[1])
        
        try:
            from work_order.models import WorkOrder
            orden = WorkOrder.objects.get(id=orden_id)
            
            # Obtener tareas asociadas
            tareas = WorkLog.objects.filter(
                models.Q(work_order=orden.numero) | models.Q(work_order_ref=orden)
            ).order_by('-start')
            
            # Calcular total de horas
            total_horas = sum([t.duration() for t in tareas])
            
            # Emoji para prioridad
            prioridad_emoji = {
                'urgente': '🔴',
                'alta': '🟠', 
                'media': '🟡',
                'baja': '🟢'
            }.get(orden.prioridad, '⚪')
            
            mensaje = (
                f"📋 <b>Orden de Trabajo: {orden.numero}</b>\n\n"
                f"📝 <b>Título:</b> {orden.titulo}\n"
                f"🏢 <b>Cliente:</b> {orden.cliente}\n"
                f"{prioridad_emoji} <b>Prioridad:</b> {orden.get_prioridad_display()}\n"
                f"📊 <b>Estado:</b> {orden.get_estado_display()}\n"
                f"👷 <b>Asignado a:</b> {orden.asignado_a.get_full_name() if orden.asignado_a else 'No asignado'}\n"
                f"📅 <b>Creación:</b> {orden.fecha_creacion.strftime('%d/%m/%Y %H:%M')}\n"
            )
            
            if orden.fecha_limite:
                mensaje += f"⏰ <b>Fecha límite:</b> {orden.fecha_limite.strftime('%d/%m/%Y %H:%M')}\n"
            
            if orden.descripcion:
                mensaje += f"📄 <b>Descripción:</b>\n{orden.descripcion}\n\n"
            
            mensaje += f"⏱️ <b>Total de horas:</b> {total_horas:.2f} hs\n"
            mensaje += f"📋 <b>Tareas asociadas:</b> {tareas.count()}\n"
            
            # Botones para las tareas asociadas
            buttons = []
            if tareas.exists():
                mensaje += "\n📋 <b>Tareas:</b>\n"
                for tarea in tareas[:5]:  # Mostrar máximo 5 tareas
                    texto = f"🔧 {tarea.start.strftime('%d/%m %H:%M')} - {tarea.description[:25]}..."
                    buttons.append([InlineKeyboardButton(texto, callback_data=f"ver_tarea:{tarea.id}")])
                
                if tareas.count() > 5:
                    buttons.append([InlineKeyboardButton(f"📋 Ver todas las tareas ({tareas.count()})", callback_data=f"ver_todas_tareas:{orden.id}")])
            
            # Botones de navegación
            buttons.extend([
                [InlineKeyboardButton("🔙 Volver a Órdenes", callback_data="volver_ordenes")],
                [InlineKeyboardButton("➕ Nueva Tarea", callback_data="nueva_tarea_bot")]
            ])
            
            await query.edit_message_text(mensaje, reply_markup=InlineKeyboardMarkup(buttons), parse_mode='HTML')
            
        except WorkOrder.DoesNotExist:
            await query.edit_message_text("⚠️ La orden de trabajo no existe.")
        except Exception as e:
            logger.error(f"Error al mostrar orden: {e}")
            await query.edit_message_text("❌ Error al mostrar la orden.")
    except Exception as e:
        logger.error(f"Error en show_work_order_detail: {e}")
        await query.edit_message_text("❌ Error interno del bot.")

# --- Funciones para la conversación /nueva_tarea ---

async def nueva_tarea_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia el flujo de creación de tarea (desde comando)"""
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
        context.user_data['chat_id'] = chat_id
        
        return await ask_work_order_selection(update, context)
            
    except Exception as e:
        logger.error(f"Error en nueva_tarea_start: {e}")
        await update.message.reply_text("❌ Error interno del bot. Por favor, intenta más tarde.")
        return ConversationHandler.END

async def nueva_tarea_from_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia el flujo de creación de tarea (desde callback)"""
    try:
        query = update.callback_query
        await query.answer()
        
        chat_id = query.message.chat.id
        user = get_user_from_chat(chat_id)

        if not user:
            await query.edit_message_text("🚫 No estás autorizado.")
            return ConversationHandler.END

        context.user_data['technician'] = user
        context.user_data['chat_id'] = chat_id
        
        return await ask_work_order_selection(query, context)
            
    except Exception as e:
        logger.error(f"Error en nueva_tarea_from_callback: {e}")
        try:
            await update.callback_query.edit_message_text("❌ Error interno del bot.")
        except:
            pass
        return ConversationHandler.END

async def ask_work_order_selection(update_or_query, context):
    """Pregunta si quiere asociar la tarea a una orden de trabajo"""
    try:
        # Determinar si es update o query
        is_query = hasattr(update_or_query, 'data')
        
        if is_query:
            # Es un callback query
            query = update_or_query
            chat_id = query.message.chat.id
            user = context.user_data['technician']
        else:
            # Es un update normal
            chat_id = update_or_query.effective_chat.id
            user = context.user_data['technician']
        
        # Obtener órdenes disponibles
        try:
            from work_order.models import WorkOrder
            
            assigned_orders = WorkOrder.objects.filter(asignado_a=user).exclude(estado='cerrada')
            collaborator_orders = WorkOrder.objects.filter(
                worklogs__collaborator=user
            ).exclude(estado='cerrada').distinct()
            
            available_orders = assigned_orders.union(collaborator_orders)
            
            if available_orders.exists():
                buttons = [
                    [InlineKeyboardButton("❌ No asociar a ninguna OT", callback_data="work_order:none")]
                ]
                
                for orden in available_orders:
                    prioridad_emoji = {
                        'urgente': '🔴',
                        'alta': '🟠', 
                        'media': '🟡',
                        'baja': '🟢'
                    }.get(orden.prioridad, '⚪')
                    
                    texto = f"{prioridad_emoji} {orden.numero} - {orden.titulo[:30]}..."
                    buttons.append([InlineKeyboardButton(texto, callback_data=f"work_order:{orden.id}")])
                
                if is_query:
                    await query.edit_message_text(
                        "📋 ¿Querés asociar esta tarea a una orden de trabajo?",
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
                else:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text="📋 ¿Querés asociar esta tarea a una orden de trabajo?",
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
                
                # Para el flujo directo, no retornamos estado
                if not is_query:
                    return SELECTING_WORK_ORDER
                return
            else:
                # No hay órdenes disponibles
                context.user_data['work_order'] = None
                if is_query:
                    await query.edit_message_text("No tenés órdenes de trabajo disponibles. Continuando sin asociar...")
                    # Continuar con el flujo directo
                    await ask_task_type_selection(query, context)
                else:
                    await context.bot.send_message(chat_id, "No tenés órdenes de trabajo disponibles. Continuando sin asociar...")
                    return await ask_task_type_selection(update_or_query, context)
                
        except ImportError:
            context.user_data['work_order'] = None
            if is_query:
                await ask_task_type_selection(update_or_query, context)
            else:
                return await ask_task_type_selection(update_or_query, context)
            
    except Exception as e:
        logger.error(f"Error en ask_work_order_selection: {e}")
        if not hasattr(update_or_query, 'data'):
            return ConversationHandler.END

async def select_work_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja la selección de orden de trabajo"""
    try:
        query = update.callback_query
        await query.answer()
        
        if query.data == "work_order:none":
            context.user_data['work_order'] = None
            await query.edit_message_text("✅ Continuando sin asociar a ninguna orden de trabajo.")
        else:
            work_order_id = int(query.data.split(":")[1])
            try:
                from work_order.models import WorkOrder
                work_order = WorkOrder.objects.get(id=work_order_id)
                context.user_data['work_order'] = work_order
                await query.edit_message_text(f"✅ Tarea asociada a: {work_order.numero} - {work_order.titulo}")
            except (WorkOrder.DoesNotExist, ValueError):
                context.user_data['work_order'] = None
                await query.edit_message_text("⚠️ Orden no válida. Continuando sin asociar.")
        
        return await ask_task_type_selection(query, context)
        
    except Exception as e:
        logger.error(f"Error en select_work_order: {e}")
        try:
            await update.callback_query.edit_message_text("❌ Error interno del bot.")
        except:
            pass
        return ConversationHandler.END

async def ask_task_type_selection(update_or_query, context):
    """Pregunta el tipo de tarea"""
    try:
        buttons = [
            [InlineKeyboardButton("🏭 Taller", callback_data="task_type:Taller")],
            [InlineKeyboardButton("🌍 Campo", callback_data="task_type:Campo")],
            [InlineKeyboardButton("📋 Diligencia", callback_data="task_type:Diligencia")],
            [InlineKeyboardButton("🔧 Otros", callback_data="task_type:Otros")],
            [InlineKeyboardButton("❌ Cancelar Tarea", callback_data="cancelar")]
        ]
        
        # Determinar si es update o query
        is_query = hasattr(update_or_query, 'data')
        
        if is_query:
            # Es un callback query
            query = update_or_query
            chat_id = query.message.chat.id
            await query.edit_message_text(
                "🔧 Seleccioná el tipo de tarea:",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        else:
            # Es un update normal
            chat_id = update_or_query.effective_chat.id
            await context.bot.send_message(
                chat_id=chat_id,
                text="🔧 Seleccioná el tipo de tarea:",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        
        return SELECTING_TASK_TYPE
        
    except Exception as e:
        logger.error(f"Error en ask_task_type_selection: {e}")
        return ConversationHandler.END

async def select_task_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja la selección del tipo de tarea"""
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
        if update.message.voice:
            try:
                # Procesar audio
                audio_file = await context.bot.get_file(update.message.voice.file_id)
                audio_path = f"worklog_audios/audio_{update.effective_user.id}_{int(time.time())}.ogg"
                
                # Guardar audio localmente
                os.makedirs("media/worklog_audios", exist_ok=True)
                await audio_file.download_to_drive(os.path.join("media", audio_path))
                
                context.user_data['audio_file_relative'] = audio_path
                context.user_data['pending_transcription'] = True
                context.user_data['description'] = "[Audio adjunto - Transcribiendo...]"
                
                # Iniciar transcripción en background
                chat_id = update.effective_chat.id
                logger.info(f"Iniciando transcripción para chat {chat_id}")
                asyncio.create_task(process_transcription_background(chat_id, audio_path, context))
                
                await update.message.reply_text("🎵 Audio recibido. Transcribiendo...")
                logger.info(f"Audio guardado en: {audio_path}")
                return await ask_status(update, context)
            except Exception as e:
                logger.error(f"Error procesando audio: {e}")
                context.user_data['description'] = "[Audio adjunto - Error al procesar]"
                context.user_data['pending_transcription'] = False
                await update.message.reply_text("❌ Error al procesar el audio. Por favor, intenta más tarde.")
                return ConversationHandler.END
        else:
            # Texto directo
            description = update.message.text
            context.user_data['description'] = description
            context.user_data['transcription_complete'] = True
            
            await update.message.reply_text(f"✅ Descripción registrada: {description}")
            return await ask_status(update, context)
            
    except Exception as e:
        logger.error(f"Error en enter_description: {e}")
        await update.message.reply_text("❌ Error al procesar la descripción. Por favor, intenta más tarde.")
        return ConversationHandler.END

async def process_transcription_background(chat_id: int, audio_path: str, context: ContextTypes.DEFAULT_TYPE):
    """Procesa la transcripción en segundo plano y actualiza el contexto"""
    try:
        logger.info(f"Iniciando transcripción para chat {chat_id}, archivo: {audio_path}")
        
        model = get_whisper_model()
        if model is None:
            logger.error("Modelo Whisper no disponible para transcripción en segundo plano")
            # Actualizar contexto con error
            if hasattr(context, 'user_data') and context.user_data:
                context.user_data['description'] = "[Audio adjunto - Error: Modelo Whisper no disponible]"
                context.user_data['pending_transcription'] = False
            return
        
        # Transcribir el audio
        logger.info(f"Transcribiendo audio: {audio_path}")
        result = model.transcribe(audio_path, language="es", fp16=False)
        text = (result or {}).get('text', '').strip()
        
        if text:
            # Actualizar la descripción en el contexto
            if hasattr(context, 'user_data') and context.user_data:
                context.user_data['description'] = text
                context.user_data['transcription_complete'] = True
                context.user_data['pending_transcription'] = False
                logger.info(f"Transcripción completada para chat {chat_id}: {text[:100]}...")
            else:
                logger.warning(f"Contexto no disponible para chat {chat_id} al completar transcripción")
        else:
            logger.warning("No se pudo extraer texto del audio en transcripción en segundo plano")
            if hasattr(context, 'user_data') and context.user_data:
                context.user_data['description'] = "[Audio adjunto - Error en transcripción]"
                context.user_data['pending_transcription'] = False
            
    except Exception as e:
        logger.error(f"Error en transcripción en segundo plano para chat {chat_id}: {e}")
        # En caso de error, mantener la descripción como "[Audio adjunto]"
        if hasattr(context, 'user_data') and context.user_data:
            context.user_data['description'] = "[Audio adjunto - Error en transcripción]"
            context.user_data['pending_transcription'] = False

async def select_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("status:"):
            status_value = query.data.split(":")[1]
            context.user_data['status'] = status_value
            
            await query.edit_message_text(f"✅ Estado seleccionado: {status_value}")
            
            # Preguntar duración
            await query.edit_message_text("⏱️ ¿Cuánto tiempo duró la tarea? (ej: 2:30, 0:20, 10:50)")
            return ENTERING_DURATION
        else:
            await query.edit_message_text("❌ Selección inválida.")
            return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error en select_status: {e}")
        try:
            await update.callback_query.edit_message_text("❌ Error interno del bot.")
        except:
            pass
        return ConversationHandler.END

async def ask_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pregunta el estado de la tarea (excluyendo 'abierta' y 'cerrada')"""
    try:
        buttons = [
            [InlineKeyboardButton("⏳ Pendiente", callback_data="status:pendiente")],
            [InlineKeyboardButton("🔄 En Proceso", callback_data="status:en_proceso")],
            [InlineKeyboardButton("⏸️ En Espera de Repuestos", callback_data="status:en_espera_repuestos")],
            [InlineKeyboardButton("✅ Completada", callback_data="status:completada")],
            [InlineKeyboardButton("❌ Cancelada", callback_data="status:cancelada")],
            [InlineKeyboardButton("❌ Cancelar Tarea", callback_data="cancelar")]
        ]
        
        await update.effective_chat.send_message(
            "📊 Seleccioná el estado de la tarea:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return SELECTING_STATUS
    except Exception as e:
        logger.error(f"Error en ask_status: {e}")
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
        work_order = context.user_data.get('work_order')
        audio_file_relative = context.user_data.get('audio_file_relative')
        
        # Usar la transcripción completa si está disponible
        final_description = context.user_data.get('description')
        if context.user_data.get('transcription_complete') and context.user_data.get('pending_transcription'):
            # Si la transcripción se completó, usar el texto transcrito
            final_description = context.user_data.get('description')
        elif context.user_data.get('pending_transcription'):
            # Si aún está transcribiendo, mantener el marcador
            final_description = "[Audio adjunto - Transcribiendo...]"
        
        # Preparar datos de la orden de trabajo
        work_order_value = None
        work_order_ref = None
        if work_order:
            work_order_value = work_order.numero
            work_order_ref = work_order
        
        # Guardar la tarea
        worklog = WorkLog.objects.create(
            technician=user,
            collaborator=collaborator,
            start=start_time,
            end=end_time,
            task_type=task_type,
            description=final_description,
            status=status_value,
            work_order=work_order_value,
            work_order_ref=work_order_ref,
            created_by=user,
            audio_file=audio_file_relative if audio_file_relative else None,
        )
        
        # Mensaje de confirmación
        mensaje = "✅ Tarea registrada correctamente."
        if work_order:
            mensaje += f"\n📋 Asociada a: {work_order.numero} - {work_order.titulo}"
        
        await update.effective_chat.send_message(mensaje)
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

async def ask_task_type_from_callback(query, context):
    """Pregunta el tipo de tarea desde un callback"""
    try:
        buttons = [
            [InlineKeyboardButton("🏭 Taller", callback_data="task_type:Taller")],
            [InlineKeyboardButton("🌍 Campo", callback_data="task_type:Campo")],
            [InlineKeyboardButton("📋 Diligencia", callback_data="task_type:Diligencia")],
            [InlineKeyboardButton("🔧 Otros", callback_data="task_type:Otros")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="cancelar")]
        ]
        
        await query.edit_message_text(
            "🔧 Seleccioná el tipo de tarea:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        # Nota: Aquí necesitaríamos manejar el estado de la conversación
        # Por ahora, solo mostramos la pregunta
    except Exception as e:
        logger.error(f"Error en ask_task_type_from_callback: {e}")
        await query.edit_message_text("❌ Error interno del bot.")

async def handle_nueva_tarea_direct(query, context):
    """Maneja el flujo directo de nueva tarea desde el botón"""
    try:
        await query.answer()
        chat_id = query.message.chat.id
        user = get_user_from_chat(chat_id)

        if not user:
            await query.edit_message_text("🚫 No estás autorizado.")
            return ConversationHandler.END

        context.user_data['technician'] = user
        context.user_data['chat_id'] = chat_id
        
        return await ask_work_order_selection(query, context)
    except Exception as e:
        logger.error(f"Error en handle_nueva_tarea_direct: {e}")
        try:
            await query.edit_message_text("❌ Error interno del bot.")
        except:
            pass
        return ConversationHandler.END

async def handle_work_order_selection_direct(query, context):
    """Maneja la selección de una orden de trabajo desde el flujo directo de nueva_tarea_bot"""
    try:
        if query.data == "work_order:none":
            context.user_data['work_order'] = None
            await query.edit_message_text("✅ Continuando sin asociar a ninguna orden de trabajo.")
        else:
            work_order_id = int(query.data.split(":")[1])
            try:
                from work_order.models import WorkOrder
                work_order = WorkOrder.objects.get(id=work_order_id)
                context.user_data['work_order'] = work_order
                await query.edit_message_text(f"✅ Tarea asociada a: {work_order.numero} - {work_order.titulo}")
            except (WorkOrder.DoesNotExist, ValueError):
                context.user_data['work_order'] = None
                await query.edit_message_text("⚠️ Orden no válida. Continuando sin asociar.")
        
        # Continuar con el flujo de nueva_tarea
        return await ask_task_type_selection(query, context)
        
    except Exception as e:
        logger.error(f"Error en handle_work_order_selection_direct: {e}")
        await query.edit_message_text("❌ Error interno del bot.")

async def handle_task_type_selection_direct(query, context):
    """Maneja la selección de tipo de tarea desde el flujo directo de nueva_tarea_bot"""
    try:
        await query.answer()
        task_type_value = query.data.split(":")[1]
        context.user_data['task_type'] = task_type_value

        await query.edit_message_text(
            "📝 Enviá la descripción de la tarea (texto o audio)."
        )
        
        # Establecer el estado para continuar con el flujo
        context.user_data['waiting_for_description'] = True
        
    except Exception as e:
        logger.error(f"Error en handle_task_type_selection_direct: {e}")
        await query.edit_message_text("❌ Error interno del bot.")

async def handle_status_selection_direct(query, context):
    """Maneja la selección de estado desde el flujo directo de nueva_tarea_bot"""
    try:
        await query.answer()
        status_value = query.data.split(":")[1]
        context.user_data['status'] = status_value

        await query.edit_message_text(f"✅ Estado seleccionado: {status_value}")
        
        # Preguntar duración
        await query.edit_message_text("⏱️ ¿Cuánto tiempo duró la tarea? (ej: 2:30, 0:20, 10:50)")
        
        # Marcar que estamos esperando duración
        context.user_data['waiting_for_duration'] = True
        
    except Exception as e:
        logger.error(f"Error en handle_status_selection_direct: {e}")
        await query.edit_message_text("❌ Error interno del bot.")

async def handle_direct_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja mensajes de texto y audio en el flujo directo de nueva tarea"""
    try:
        # Verificar si estamos esperando descripción
        if context.user_data.get('waiting_for_description'):
            if update.message.voice:
                try:
                    # Procesar audio
                    audio_file = await context.bot.get_file(update.message.voice.file_id)
                    audio_path = f"worklog_audios/audio_{update.effective_user.id}_{int(time.time())}.ogg"
                    
                    # Guardar audio localmente
                    os.makedirs("media/worklog_audios", exist_ok=True)
                    await audio_file.download_to_drive(os.path.join("media", audio_path))
                    
                    context.user_data['audio_file_relative'] = audio_path
                    context.user_data['pending_transcription'] = True
                    context.user_data['description'] = "[Audio adjunto - Transcribiendo...]"
                    
                    # Iniciar transcripción en background
                    chat_id = update.effective_chat.id
                    logger.info(f"Iniciando transcripción para chat {chat_id}")
                    asyncio.create_task(process_transcription_background(chat_id, os.path.join("media", audio_path), context))
                    
                    await update.message.reply_text("🎵 Audio recibido. Transcribiendo...")
                    logger.info(f"Audio guardado en: {os.path.join('media', audio_path)}")
                except Exception as e:
                    logger.error(f"Error procesando audio: {e}")
                    context.user_data['description'] = "[Audio adjunto - Error al procesar]"
                    context.user_data['pending_transcription'] = False
            else:
                # Texto directo
                description = update.message.text
                context.user_data['description'] = description
                context.user_data['transcription_complete'] = True
            
            # Limpiar flag de espera de descripción
            context.user_data['waiting_for_description'] = False
            
            # Continuar con el flujo - preguntar estado
            await ask_status_direct(update, context)
            
        # Verificar si estamos esperando duración
        elif context.user_data.get('waiting_for_duration'):
            duration_text = update.message.text
            try:
                # Parsear duración
                duration_td = parse_hhmm_to_timedelta(duration_text)
                context.user_data['duration_td'] = duration_td
                
                await update.message.reply_text(f"✅ Duración registrada: {duration_text}")
                
                # Limpiar flag de espera de duración
                context.user_data['waiting_for_duration'] = False
                
                # Preguntar si quiere colaborador
                await ask_collaborator_direct(update, context)
                
            except ValueError:
                await update.message.reply_text("❌ Formato inválido. Usá formato H:MM (ej: 2:30, 0:20, 10:50)")
            except Exception as e:
                logger.error(f"Error procesando duración: {e}")
                await update.message.reply_text("❌ Error al procesar la duración. Por favor, intenta más tarde.")
        
        else:
            # No estamos esperando ningún input, ignorar mensaje
            return
            
    except Exception as e:
        logger.error(f"Error en handle_direct_message: {e}")
        await update.message.reply_text("❌ Error al procesar el mensaje. Por favor, intenta más tarde.")

async def ask_status_direct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pregunta el estado de la tarea en el flujo directo"""
    try:
        buttons = [
            [InlineKeyboardButton("⏳ Pendiente", callback_data="status_direct:pendiente")],
            [InlineKeyboardButton("🔄 En Proceso", callback_data="status_direct:en_proceso")],
            [InlineKeyboardButton("⏸️ En Espera de Repuestos", callback_data="status_direct:en_espera_repuestos")],
            [InlineKeyboardButton("✅ Completada", callback_data="status_direct:completada")],
            [InlineKeyboardButton("❌ Cancelada", callback_data="status_direct:cancelada")],
            [InlineKeyboardButton("❌ Cancelar Tarea", callback_data="cancelar")]
        ]
        
        await update.message.reply_text(
            "📊 Seleccioná el estado de la tarea:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
    except Exception as e:
        logger.error(f"Error en ask_status_direct: {e}")
        await update.message.reply_text("❌ Error interno del bot.")

async def ask_collaborator_direct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pregunta si quiere agregar colaborador en el flujo directo"""
    try:
        buttons = [
            [InlineKeyboardButton("❌ No agregar colaborador", callback_data="colaborador_direct:none")],
            [InlineKeyboardButton("✅ Sí, agregar colaborador", callback_data="colaborador_direct:yes")]
        ]
        
        await update.message.reply_text(
            "👥 ¿Querés agregar un colaborador a esta tarea?",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
    except Exception as e:
        logger.error(f"Error en ask_collaborator_direct: {e}")
        await update.message.reply_text("❌ Error interno del bot.")

async def handle_collaborator_direct(query, context):
    """Maneja la selección de colaborador en el flujo directo"""
    try:
        await query.answer()
        
        if query.data == "colaborador_direct:none":
            context.user_data['collaborator'] = None
            await query.edit_message_text("✅ Continuando sin colaborador.")
        else:
            # Mostrar lista de técnicos disponibles
            try:
                from accounts.models import CustomUser
                technicians = CustomUser.objects.filter(user_type='tecnico').exclude(id=context.user_data['technician'].id)
                
                if technicians.exists():
                    buttons = []
                    for tech in technicians[:10]:  # Máximo 10 técnicos
                        buttons.append([InlineKeyboardButton(
                            f"👷 {tech.get_full_name()}", 
                            callback_data=f"colaborador_select:{tech.id}"
                        )])
                    
                    buttons.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancelar")])
                    
                    await query.edit_message_text(
                        "👥 Seleccioná el colaborador:",
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
                    return
                else:
                    await query.edit_message_text("❌ No hay técnicos disponibles para colaborar.")
                    context.user_data['collaborator'] = None
            except Exception as e:
                logger.error(f"Error obteniendo técnicos: {e}")
                context.user_data['collaborator'] = None
                await query.edit_message_text("⚠️ Error al obtener técnicos. Continuando sin colaborador.")
        
        # Mostrar resumen final de la tarea
        await show_task_summary_direct(query, context)
        
    except Exception as e:
        logger.error(f"Error en handle_collaborator_direct: {e}")
        await query.edit_message_text("❌ Error interno del bot.")

async def handle_collaborator_select_direct(query, context):
    """Maneja la selección específica de colaborador"""
    try:
        await query.answer()
        collaborator_id = int(query.data.split(":")[1])
        
        try:
            from accounts.models import CustomUser
            collaborator = CustomUser.objects.get(id=collaborator_id, user_type='tecnico')
            context.user_data['collaborator'] = collaborator
            
            await query.edit_message_text(f"✅ Colaborador seleccionado: {collaborator.get_full_name()}")
            
            # Mostrar resumen final de la tarea
            await show_task_summary_direct(query, context)
            
        except CustomUser.DoesNotExist:
            await query.edit_message_text("❌ Técnico no encontrado. Continuando sin colaborador.")
            context.user_data['collaborator'] = None
            await show_task_summary_direct(query, context)
            
    except Exception as e:
        logger.error(f"Error en handle_collaborator_select_direct: {e}")
        await query.edit_message_text("❌ Error interno del bot.")

async def show_task_summary_direct(query, context):
    """Muestra el resumen final de la tarea con opciones de transcripción"""
    try:
        # Obtener datos de la tarea
        task_type = context.user_data.get('task_type', 'N/A')
        description = context.user_data.get('description', 'N/A')
        status = context.user_data.get('status', 'N/A')
        duration = context.user_data.get('duration_td', timedelta())
        work_order = context.user_data.get('work_order')
        collaborator = context.user_data.get('collaborator')
        
        # Formatear duración
        hours = int(duration.total_seconds() // 3600)
        minutes = int((duration.total_seconds() % 3600) // 60)
        duration_str = f"{hours}:{minutes:02d}"
        
        # Construir mensaje de resumen
        summary = f"📋 <b>Resumen de la Tarea</b>\n\n"
        summary += f"🔧 <b>Tipo:</b> {task_type}\n"
        summary += f"📝 <b>Descripción:</b> {description}\n"
        summary += f"📊 <b>Estado:</b> {status}\n"
        summary += f"⏱️ <b>Duración:</b> {duration_str}\n"
        
        if work_order:
            summary += f"📋 <b>Orden de Trabajo:</b> {work_order.numero} - {work_order.titulo}\n"
        
        if collaborator:
            summary += f"👥 <b>Colaborador:</b> {collaborator.get_full_name()}\n"
        
        # Verificar si hay transcripción pendiente
        if context.user_data.get('pending_transcription'):
            summary += "\n🎵 <b>Audio:</b> Transcribiendo...\n"
            summary += "La transcripción se enviará cuando esté lista."
        
        # Botones de acción
        buttons = [
            [InlineKeyboardButton("💾 Guardar Tarea", callback_data="save_task_direct")],
            [InlineKeyboardButton("✏️ Editar Transcripción", callback_data="edit_transcription")],
            [InlineKeyboardButton("❌ Cancelar Tarea", callback_data="cancelar")]
        ]
        
        await query.edit_message_text(
            summary,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode='HTML'
        )
        
    except Exception as e:
        logger.error(f"Error en show_task_summary_direct: {e}")
        await query.edit_message_text("❌ Error al mostrar resumen de la tarea.")

async def save_task_direct(query, context):
    """Guarda la tarea desde el flujo directo de nueva_tarea_bot"""
    try:
        if not ensure_db_connection():
            await query.edit_message_text("❌ Error de conexión a la base de datos. No se pudo guardar la tarea.")
            return ConversationHandler.END

        user = context.user_data['technician']
        end_time = timezone.now()
        duration_td = context.user_data.get('duration_td', timedelta())
        start_time = end_time - duration_td
        task_type = context.user_data['task_type']
        status_value = context.user_data.get('status', 'pendiente')
        collaborator = context.user_data.get('collaborator')
        work_order = context.user_data.get('work_order')
        audio_file_relative = context.user_data.get('audio_file_relative')
        
        # Usar la transcripción completa si está disponible
        final_description = context.user_data.get('description')
        if context.user_data.get('transcription_complete') and context.user_data.get('pending_transcription'):
            # Si la transcripción se completó, usar el texto transcrito
            final_description = context.user_data.get('description')
        elif context.user_data.get('pending_transcription'):
            # Si aún está transcribiendo, mantener el marcador
            final_description = "[Audio adjunto - Transcribiendo...]"
        
        # Preparar datos de la orden de trabajo
        work_order_value = None
        work_order_ref = None
        if work_order:
            work_order_value = work_order.numero
            work_order_ref = work_order
        
        # Guardar la tarea
        worklog = WorkLog.objects.create(
            technician=user,
            collaborator=collaborator,
            start=start_time,
            end=end_time,
            task_type=task_type,
            description=final_description,
            status=status_value,
            work_order=work_order_value,
            work_order_ref=work_order_ref,
            created_by=user,
            audio_file=audio_file_relative if audio_file_relative else None,
        )
        
        # Mensaje de confirmación
        mensaje = "✅ Tarea registrada correctamente."
        if work_order:
            mensaje += f"\n📋 Asociada a: {work_order.numero} - {work_order.titulo}"
        
        await query.edit_message_text(mensaje)
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error al guardar tarea desde flujo directo: {e}")
        await query.edit_message_text("❌ Error al guardar la tarea. Por favor, intenta más tarde.")
        return ConversationHandler.END

async def edit_transcription_direct(query, context):
    """Permite editar la transcripción de la tarea desde el flujo directo"""
    try:
        await query.answer()
        audio_file_relative = context.user_data.get('audio_file_relative')
        if audio_file_relative:
            await query.edit_message_text(
                "📝 ¿Querés editar la transcripción de la tarea? (Texto o Audio)",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Texto", callback_data="edit_transcription_text")],
                    [InlineKeyboardButton("Audio", callback_data="edit_transcription_audio")],
                    [InlineKeyboardButton("❌ Cancelar", callback_data="cancelar")]
                ])
            )
        else:
            await query.edit_message_text(
                "📝 ¿Querés editar la transcripción de la tarea? (Texto)",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Texto", callback_data="edit_transcription_text")],
                    [InlineKeyboardButton("❌ Cancelar", callback_data="cancelar")]
                ])
            )
    except Exception as e:
        logger.error(f"Error en edit_transcription_direct: {e}")
        await query.edit_message_text("❌ Error interno del bot.")

async def handle_edit_transcription_text(query, context):
    """Maneja la edición de la transcripción por texto desde el flujo directo"""
    try:
        await query.answer()
        await query.edit_message_text(
            "📝 Escribí la nueva descripción de la tarea (texto o audio).",
            reply_markup=ReplyKeyboardRemove()
        )
        context.user_data['waiting_for_description'] = True
        context.user_data['transcription_complete'] = False # Resetear estado de transcripción
        context.user_data['pending_transcription'] = False # Resetear estado de transcripción pendiente
    except Exception as e:
        logger.error(f"Error en handle_edit_transcription_text: {e}")
        await query.edit_message_text("❌ Error interno del bot.")

async def handle_edit_transcription_audio(query, context):
    """Maneja la edición de la transcripción por audio desde el flujo directo"""
    try:
        await query.answer()
        await query.edit_message_text(
            "🎵 Enviá el nuevo audio de la tarea.",
            reply_markup=ReplyKeyboardRemove()
        )
        context.user_data['waiting_for_description'] = True
        context.user_data['transcription_complete'] = False # Resetear estado de transcripción
        context.user_data['pending_transcription'] = False # Resetear estado de transcripción pendiente
    except Exception as e:
        logger.error(f"Error en handle_edit_transcription_audio: {e}")
        await query.edit_message_text("❌ Error interno del bot.")

async def handle_edit_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja mensajes de texto y audio en el flujo de edición de transcripción"""
    try:
        # Verificar si estamos esperando descripción
        if context.user_data.get('waiting_for_description'):
            if update.message.voice:
                try:
                    # Procesar audio
                    audio_file = await context.bot.get_file(update.message.voice.file_id)
                    audio_path = f"worklog_audios/audio_{update.effective_user.id}_{int(time.time())}.ogg"
                    
                    # Guardar audio localmente
                    os.makedirs("media/worklog_audios", exist_ok=True)
                    await audio_file.download_to_drive(os.path.join("media", audio_path))
                    
                    context.user_data['audio_file_relative'] = audio_path
                    context.user_data['pending_transcription'] = True
                    context.user_data['description'] = "[Audio adjunto - Transcribiendo...]"
                    
                    # Iniciar transcripción en background
                    chat_id = update.effective_chat.id
                    logger.info(f"Iniciando transcripción para chat {chat_id}")
                    asyncio.create_task(process_transcription_background(chat_id, os.path.join("media", audio_path), context))
                    
                    await update.message.reply_text("🎵 Audio recibido. Transcribiendo...")
                    logger.info(f"Audio guardado en: {os.path.join('media', audio_path)}")
                except Exception as e:
                    logger.error(f"Error procesando audio: {e}")
                    context.user_data['description'] = "[Audio adjunto - Error al procesar]"
                    context.user_data['pending_transcription'] = False
            else:
                # Texto directo
                description = update.message.text
                context.user_data['description'] = description
                context.user_data['transcription_complete'] = True
            
            # Limpiar flag de espera de descripción
            context.user_data['waiting_for_description'] = False
            
            # Continuar con el flujo - preguntar estado
            await ask_status_direct(update, context)
            
        # Verificar si estamos esperando duración
        elif context.user_data.get('waiting_for_duration'):
            duration_text = update.message.text
            try:
                # Parsear duración
                duration_td = parse_hhmm_to_timedelta(duration_text)
                context.user_data['duration_td'] = duration_td
                
                await update.message.reply_text(f"✅ Duración registrada: {duration_text}")
                
                # Limpiar flag de espera de duración
                context.user_data['waiting_for_duration'] = False
                
                # Preguntar si quiere colaborador
                await ask_collaborator_direct(update, context)
                
            except ValueError:
                await update.message.reply_text("❌ Formato inválido. Usá formato H:MM (ej: 2:30, 0:20, 10:50)")
            except Exception as e:
                logger.error(f"Error procesando duración: {e}")
                await update.message.reply_text("❌ Error al procesar la duración. Por favor, intenta más tarde.")
        
        else:
            # No estamos esperando ningún input, ignorar mensaje
            return
            
    except Exception as e:
        logger.error(f"Error en handle_edit_message: {e}")
        await update.message.reply_text("❌ Error al procesar el mensaje. Por favor, intenta más tarde.")

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
    application.add_handler(CommandHandler("ver_OTs", ver_OTs)) # Nuevo handler para /ver_OTs
    
    # Handler para callbacks (incluyendo nueva_tarea_bot)
    application.add_handler(CallbackQueryHandler(callback_query_handler))
    
    # Handler para mensajes de texto y audio en flujo directo
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        handle_direct_message
    ))
    application.add_handler(MessageHandler(
        filters.VOICE, 
        handle_direct_message
    ))
    
    # Handler para mensajes de edición de transcripción
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        handle_edit_message
    ))
    application.add_handler(MessageHandler(
        filters.VOICE, 
        handle_edit_message
    ))

    # Handler para la conversación de nueva_tarea (solo desde comando)
    nueva_tarea_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("nueva_tarea", nueva_tarea_start)],
        states={
            SELECTING_WORK_ORDER: [
                CallbackQueryHandler(select_work_order, pattern="^work_order:"),
                CallbackQueryHandler(cancel, pattern="^cancelar$")
            ],
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