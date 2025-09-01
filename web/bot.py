# bot.py
# -*- coding: utf-8 -*-

import os
import sys
import logging
import asyncio
import time
from datetime import timedelta
from functools import partial

CPU_COUNT = os.cpu_count() or 1

# ----------------------------
# Django setup
# ----------------------------
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "web.settings")
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
django.setup()

from django.utils import timezone
from django.db import connection
from django.db import models

from accounts.models import CustomUser
from worklog.models import WorkLog

# ----------------------------
# Telegram (python-telegram-bot v20)
# ----------------------------
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ----------------------------
# Logging
# ----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("worklog-bot-fw")

# Configurar niveles de logging específicos
logging.getLogger("faster_whisper").setLevel(logging.INFO)  # subir a DEBUG si querés más detalle

# Silenciar logs de HTTP requests de httpx y telegram
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)

# Mantener logs de errores importantes
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("telegram").setLevel(logging.ERROR)
logging.getLogger("telegram.ext").setLevel(logging.ERROR)

# ----------------------------
# Estados de conversación
# ----------------------------
SELECTING_WORK_ORDER, SELECTING_TASK_TYPE, ENTERING_DESCRIPTION, SELECTING_STATUS, ENTERING_DURATION, ASK_COLLABORATOR, SELECTING_COLLABORATOR = range(7)

# ----------------------------
# faster-whisper (CTranslate2)
# ----------------------------
from faster_whisper import WhisperModel

# ----------------------------
# Seguridad del bot
# ----------------------------
from bot_security import (
    validate_text, validate_audio_file, validate_audio_duration,
    sanitize_text, get_file_info, log_security_event
)

FW_MODEL = None

def get_fw_model() -> WhisperModel:
    global FW_MODEL
    if FW_MODEL is None:
        logger.info("Cargando faster-whisper 'medium' (CPU, int8)…")
        
        # Configurar directorio de cache personalizado
        cache_dir = os.path.join(os.getcwd(), '.cache', 'huggingface')
        os.makedirs(cache_dir, exist_ok=True)
        
        FW_MODEL = WhisperModel(
            "medium",
            device="cpu",
            compute_type="int8",
            cpu_threads=CPU_COUNT,
            num_workers=1,
            download_root=cache_dir
        )
        logger.info("Modelo faster-whisper cargado.")
    return FW_MODEL

def _fw_transcribe_sync(audio_path: str) -> str:
    """
    Transcripción síncrona con faster-whisper, con logs y fallback sin VAD.
    """
    model = get_fw_model()

    def _do_transcribe(vad_enabled: bool):
        segments, info = model.transcribe(
            audio_path,
            language="es",
            beam_size=1,
            vad_filter=vad_enabled,
            condition_on_previous_text=False
        )
        parts = [seg.text for seg in segments]
        text = ("".join(parts)).strip()
        return text, info

    # 1) Con VAD
    try:
        text, info = _do_transcribe(vad_enabled=True)
        logging.getLogger("faster_whisper").info(
            f"fw: language={getattr(info, 'language', 'n/a')} duration={getattr(info, 'duration', 'n/a')}"
        )
        if text:
            return text
        logging.getLogger("faster_whisper").warning("fw: texto vacío con VAD; reintento sin VAD…")
    except Exception as e:
        logging.getLogger("faster_whisper").error(f"fw: error con VAD: {e}")

    # 2) Sin VAD
    try:
        text, _ = _do_transcribe(vad_enabled=False)
        logging.getLogger("faster_whisper").info("fw: reintento sin VAD completado")
        return text
    except Exception as e:
        logging.getLogger("faster_whisper").error(f"fw: error sin VAD: {e}")
        return ""

async def fw_transcribe_in_executor(audio_path: str) -> str:
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(None, partial(_fw_transcribe_sync, audio_path))
    except Exception as e:
        logger.error(f"Error transcribiendo (faster-whisper): {e}")
        return ""

# ----------------------------
# Utilidades de DB y helpers
# ----------------------------
def ensure_db_connection() -> bool:
    try:
        if connection.connection is None or not connection.is_usable():
            connection.close()
            connection.ensure_connection()
        return True
    except Exception as e:
        logger.error(f"Error al conectar a la base de datos: {e}")
        return False

def get_user_from_chat(chat_id: int):
    max_retries, retry_delay = 3, 1.2
    for attempt in range(max_retries):
        try:
            if connection.connection is None or not connection.is_usable():
                connection.close()
                connection.ensure_connection()
            return CustomUser.objects.get(telegram_chat_id=chat_id)
        except Exception as e:
            logger.error(f"DB error get_user_from_chat (intento {attempt+1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                try:
                    connection.close()
                    connection.ensure_connection()
                except Exception:
                    pass
            else:
                return None

def parse_hhmm_to_timedelta(text: str) -> timedelta:
    text = text.strip()
    if ":" in text:
        parts = text.split(":")
        if len(parts) != 2:
            raise ValueError("Formato inválido")
        hours = int(parts[0]) if parts[0] else 0
        minutes = int(parts[1]) if parts[1] else 0
    else:
        if not text.isdigit():
            raise ValueError("Formato inválido")
        hours, minutes = 0, int(text)
    if minutes < 0 or minutes >= 60 or hours < 0:
        raise ValueError("Minutos deben ser 0-59")
    return timedelta(hours=hours, minutes=minutes)

# ----------------------------
# Helpers de UI (resumen + botones)
# ----------------------------
def build_summary_text_and_markup(context: ContextTypes.DEFAULT_TYPE):
    task_type = context.user_data.get("task_type", "N/A")
    description = context.user_data.get("description", "N/A")
    status = context.user_data.get("status", "N/A")
    duration = context.user_data.get("duration_td", timedelta())
    work_order = context.user_data.get("work_order")
    collaborator = context.user_data.get("collaborator")
    other_task_type = context.user_data.get("other_task_type")
    general_ops_subtype = context.user_data.get("general_ops_subtype")
    warranty = context.user_data.get("warranty")
    field_city = context.user_data.get("field_city")
    field_km_one_way = context.user_data.get("field_km_one_way")

    hours = int(duration.total_seconds() // 3600)
    minutes = int((duration.total_seconds() % 3600) // 60)
    duration_str = f"{hours}:{minutes:02d}"

    summary = (
        f"📋 <b>Resumen de la Tarea</b>\n\n"
        f"🔧 <b>Tipo:</b> {task_type}\n"
    )
    if task_type == "Otros" and other_task_type:
        summary += f"🧩 <b>Otro tipo:</b> {other_task_type}\n"
    if task_type == "Operaciones generales" and general_ops_subtype:
        summary += f"⚙️ <b>Subtipo:</b> {general_ops_subtype}\n"
    if task_type in ["Taller", "Campo"] and warranty is not None:
        summary += f"🛡️ <b>Garantía:</b> {'Sí' if warranty else 'No'}\n"
    if task_type == "Campo":
        if field_city:
            summary += f"🏙️ <b>Ciudad:</b> {field_city}\n"
        if field_km_one_way is not None:
            summary += f"🛣️ <b>Km ida:</b> {field_km_one_way}\n"
    summary += (
        f"📝 <b>Descripción:</b> {description}\n"
        f"📊 <b>Estado:</b> {status}\n"
        f"⏱️ <b>Duración:</b> {duration_str}\n"
    )
    if work_order:
        summary += f"📋 <b>Orden de Trabajo:</b> {work_order.numero} - {work_order.titulo}\n"
    if collaborator:
        summary += f"👥 <b>Colaborador:</b> {collaborator.get_full_name()}\n"

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("💾 Guardar Tarea", callback_data="save_task_direct")],
        [InlineKeyboardButton("✏️ Editar Transcripción", callback_data="edit_transcription")],
        [InlineKeyboardButton("❌ Cancelar Tarea", callback_data="cancelar")],
    ])
    return summary, buttons

# ----------------------------
# Handlers principales
# ----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.effective_chat.id
        user = get_user_from_chat(chat_id)
        if user:
            logger.info(f"Usuario {user.get_full_name()} ({user.username}) inició el bot")
            await update.message.reply_text(
                f"Hola {user.get_full_name()} 👷‍♂️\n"
                f"Usá /tareas para ver tus tareas, /nueva_tarea para crear una o /ver_OTs para ver tus Órdenes de Campo."
            )
        else:
            logger.warning(f"Intento de acceso no autorizado desde chat_id: {chat_id}")
            await update.message.reply_text("🚫 No estás autorizado. Agregá tu chat ID en tu perfil desde la web.")
    except Exception as e:
        logger.error(f"/start error: {e}")
        await update.message.reply_text("❌ Error interno del bot. Intentá más tarde.")

async def tareas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not ensure_db_connection():
            await update.message.reply_text("❌ Error de conexión a DB. Probá más tarde.")
            return

        chat_id = update.effective_chat.id
        user = get_user_from_chat(chat_id)
        if not user:
            logger.warning(f"Intento de acceso no autorizado a /tareas desde chat_id: {chat_id}")
            await update.message.reply_text("🚫 No estás autorizado.")
            return
        
        logger.info(f"Usuario {user.get_full_name()} ({user.username}) consultó sus tareas")

        try:
            tareas_qs = WorkLog.objects.filter(
                models.Q(technician=user) | models.Q(collaborator=user)
            ).exclude(status="cerrada").order_by("-start")
        except Exception as e:
            logger.error(f"Error al obtener tareas: {e}")
            await update.message.reply_text("❌ No pude obtener tus tareas.")
            return

        if not tareas_qs.exists():
            await update.message.reply_text("No tenés tareas activas asignadas o como colaborador.")
            return

        buttons = []
        for t in tareas_qs[:25]:
            rol = "👷 Técnico" if t.technician == user else "🤝 Colaborador"
            texto = f"{rol} | {t.start.strftime('%d-%m %H:%M')} | {t.description[:35]}..."
            buttons.append([InlineKeyboardButton(texto, callback_data=f"ver_tarea:{t.id}")])
        buttons.append([InlineKeyboardButton("➕ Nueva Tarea", callback_data="nueva_tarea_bot")])

        await update.message.reply_text("📋 Tus tareas activas:", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        logger.error(f"/tareas error: {e}")
        await update.message.reply_text("❌ Error interno del bot.")

async def ver_OTs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not ensure_db_connection():
            await update.message.reply_text("❌ Error de conexión a DB. Probá más tarde.")
            return

        chat_id = update.effective_chat.id
        user = get_user_from_chat(chat_id)
        if not user:
            logger.warning(f"Intento de acceso no autorizado a /ver_OTs desde chat_id: {chat_id}")
            await update.message.reply_text("🚫 No estás autorizado.")
            return
        
        logger.info(f"Usuario {user.get_full_name()} ({user.username}) consultó sus órdenes de campo")

        from work_order.models import WorkOrder

        assigned_orders = WorkOrder.objects.filter(asignado_a=user).exclude(estado="cerrada")
        collaborator_orders = WorkOrder.objects.filter(worklogs__collaborator=user).exclude(estado="cerrada").distinct()
        all_orders = assigned_orders.union(collaborator_orders)

        if not all_orders.exists():
            await update.message.reply_text("No tenés órdenes asignadas o como colaborador.")
            return

        prioridad_emoji = {"urgente": "🔴", "alta": "🟠", "media": "🟡", "baja": "🟢"}
        buttons = []
        for o in all_orders[:25]:
            rol = "👷 Asignado" if o.asignado_a == user else "🤝 Colaborador"
            emoji = prioridad_emoji.get(o.prioridad, "⚪")
            texto = f"{emoji} {o.numero} | {rol} | {o.titulo[:30]}..."
            buttons.append([InlineKeyboardButton(texto, callback_data=f"ver_orden:{o.id}")])

        buttons.append([InlineKeyboardButton("➕ Nueva Tarea", callback_data="nueva_tarea_bot")])
        await update.message.reply_text("📋 Tus órdenes de campo:", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        logger.error(f"/ver_OTs error: {e}")
        await update.message.reply_text("❌ Error interno del bot.")

# -------- Detalles y navegación por callback --------

async def callback_query_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        data = query.data

        if data.startswith("ver_tarea:"):
            return await show_task_detail(query, context)
        if data.startswith("ver_orden:"):
            return await show_work_order_detail(query, context)
        if data == "nueva_tarea_bot":
            return await handle_nueva_tarea_direct(query, context)

        if data.startswith("work_order:"):
            return await handle_work_order_selection_direct(query, context)
        if data.startswith("task_type:"):
            return await handle_task_type_selection_direct(query, context)
        if data.startswith("general_ops_subtype:" ):
            return await handle_general_ops_subtype(query, context)
        if data.startswith("warranty:"):
            return await handle_warranty(query, context)
        if data.startswith("status_direct:"):
            return await handle_status_selection_direct(query, context)
        if data.startswith("colaborador_direct:"):
            return await handle_collaborator_direct(query, context)
        if data.startswith("colaborador_select:"):
            return await handle_collaborator_select_direct(query, context)
        if data == "save_task_direct":
            return await save_task_direct(query, context)
        if data == "edit_transcription":
            return await edit_transcription_direct(query, context)
        if data == "edit_transcription_text":
            return await handle_edit_transcription_text(query, context)
        if data == "edit_transcription_audio":
            return await handle_edit_transcription_audio(query, context)
        if data == "volver_tareas":
            return await volver_tareas_callback(query, context)
        if data == "volver_ordenes":
            return await volver_ordenes_callback(query, context)
        if data == "cancelar":
            return await cancel(update, context)

        await query.edit_message_text("❌ Comando no reconocido.")
    except Exception as e:
        logger.error(f"callback_query_router error: {e}")
        try:
            await update.callback_query.edit_message_text("❌ Error interno del bot.")
        except Exception:
            pass

async def volver_tareas_callback(query, context):
    """Wrapper para volver a tareas desde callback"""
    try:
        if not ensure_db_connection():
            await query.edit_message_text("❌ Error de conexión a DB. Probá más tarde.")
            return

        chat_id = query.message.chat.id
        user = get_user_from_chat(chat_id)
        if not user:
            await query.edit_message_text("🚫 No estás autorizado.")
            return

        try:
            tareas_qs = WorkLog.objects.filter(
                models.Q(technician=user) | models.Q(collaborator=user)
            ).exclude(status="cerrada").order_by("-start")
        except Exception as e:
            logger.error(f"Error al obtener tareas: {e}")
            await query.edit_message_text("❌ No pude obtener tus tareas.")
            return

        if not tareas_qs.exists():
            await query.edit_message_text("No tenés tareas activas asignadas o como colaborador.")
            return

        buttons = []
        for t in tareas_qs[:25]:
            rol = "👷 Técnico" if t.technician == user else "🤝 Colaborador"
            texto = f"{rol} | {t.start.strftime('%d-%m %H:%M')} | {t.description[:35]}..."
            buttons.append([InlineKeyboardButton(texto, callback_data=f"ver_tarea:{t.id}")])
        buttons.append([InlineKeyboardButton("➕ Nueva Tarea", callback_data="nueva_tarea_bot")])

        await query.edit_message_text("📋 Tus tareas activas:", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        logger.error(f"volver_tareas_callback error: {e}")
        await query.edit_message_text("❌ Error interno del bot.")

async def volver_ordenes_callback(query, context):
    """Wrapper para volver a órdenes desde callback"""
    try:
        if not ensure_db_connection():
            await query.edit_message_text("❌ Error de conexión a DB. Probá más tarde.")
            return

        chat_id = query.message.chat.id
        user = get_user_from_chat(chat_id)
        if not user:
            await query.edit_message_text("🚫 No estás autorizado.")
            return

        from work_order.models import WorkOrder

        assigned_orders = WorkOrder.objects.filter(asignado_a=user).exclude(estado="cerrada")
        collaborator_orders = WorkOrder.objects.filter(worklogs__collaborator=user).exclude(estado="cerrada").distinct()
        all_orders = assigned_orders.union(collaborator_orders)

        if not all_orders.exists():
            await query.edit_message_text("No tenés órdenes asignadas o como colaborador.")
            return

        prioridad_emoji = {"urgente": "🔴", "alta": "🟠", "media": "🟡", "baja": "🟢"}
        buttons = []
        for o in all_orders[:25]:
            rol = "👷 Asignado" if o.asignado_a == user else "🤝 Colaborador"
            emoji = prioridad_emoji.get(o.prioridad, "⚪")
            texto = f"{emoji} {o.numero} | {rol} | {o.titulo[:30]}..."
            buttons.append([InlineKeyboardButton(texto, callback_data=f"ver_orden:{o.id}")])

        buttons.append([InlineKeyboardButton("➕ Nueva Tarea", callback_data="nueva_tarea_bot")])
        await query.edit_message_text("📋 Tus órdenes de campo:", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        logger.error(f"volver_ordenes_callback error: {e}")
        await query.edit_message_text("❌ Error interno del bot.")

async def show_task_detail(query, context):
    try:
        if not ensure_db_connection():
            await query.edit_message_text("❌ Error de conexión. Probá más tarde.")
            return
        tarea_id = int(query.data.split(":")[1])
        t = WorkLog.objects.get(id=tarea_id)

        rol = "👷 Técnico Principal"
        msg = (
            f"📋 <b>Detalle de Tarea</b>\n\n"
            f"{rol}\n"
            f"🧑 Técnico: {t.technician.get_full_name()}\n"
            f"📆 Inicio: {t.start.strftime('%Y-%m-%d %H:%M')}\n"
            f"📆 Fin: {t.end.strftime('%Y-%m-%d %H:%M')}\n"
            f"⏱️ Duración: {t.duration()} hs\n"
            f"🔧 Tipo: {t.task_type}\n"
        )
        # Mostrar subtipo para Operaciones generales
        if t.task_type == "Operaciones generales" and t.general_ops_subtype:
            msg += f"⚙️ Subtipo: {t.general_ops_subtype}\n"
        # Mostrar otro tipo para Otros
        if t.task_type == "Otros" and t.other_task_type:
            msg += f"🧩 Otro tipo: {t.other_task_type}\n"
        # Mostrar garantía para Taller/Campo
        if t.task_type in ["Taller", "Campo"]:
            msg += f"🛡️ Garantía: {'Sí' if getattr(t, 'warranty', False) else 'No'}\n"
        # Mostrar ciudad y km para Campo
        if t.task_type == "Campo":
            if t.field_city:
                msg += f"🏙️ Ciudad: {t.field_city}\n"
            if t.field_km_one_way is not None:
                msg += f"🛣️ Km ida: {t.field_km_one_way}\n"
        msg += (
            f"📊 Estado: {t.get_status_display()}\n"
            f"📝 Descripción:\n{t.description}\n"
        )
        if t.collaborator:
            msg += f"👥 Colaborador: {t.collaborator.get_full_name()}\n"
        if t.work_order:
            msg += f"📋 Orden de Trabajo: {t.work_order}\n"

        buttons = [
            [InlineKeyboardButton("🔙 Volver a Tareas", callback_data="volver_tareas")],
            [InlineKeyboardButton("➕ Nueva Tarea", callback_data="nueva_tarea_bot")],
        ]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")
    except WorkLog.DoesNotExist:
        await query.edit_message_text("⚠️ La tarea no existe.")
    except Exception as e:
        logger.error(f"show_task_detail error: {e}")
        await query.edit_message_text("❌ Error al mostrar la tarea.")

async def show_work_order_detail(query, context):
    try:
        if not ensure_db_connection():
            await query.edit_message_text("❌ Error de conexión. Probá más tarde.")
            return

        from work_order.models import WorkOrder
        orden_id = int(query.data.split(":")[1])
        o = WorkOrder.objects.get(id=orden_id)

        tareas_qs = WorkLog.objects.filter(
            models.Q(work_order=o.numero) | models.Q(work_order_ref=o)
        ).order_by("-start")

        total_horas = sum([t.duration() for t in tareas_qs]) if tareas_qs.exists() else 0.0
        prioridad_emoji = {"urgente": "🔴", "alta": "🟠", "media": "🟡", "baja": "🟢"}.get(o.prioridad, "⚪")

        msg = (
            f"📋 <b>Orden de Trabajo: {o.numero}</b>\n\n"
            f"📝 <b>Título:</b> {o.titulo}\n"
            f"🏢 <b>Cliente:</b> {o.cliente}\n"
            f"{prioridad_emoji} <b>Prioridad:</b> {o.get_prioridad_display()}\n"
            f"📊 <b>Estado:</b> {o.get_estado_display()}\n"
            f"👷 <b>Asignado a:</b> {o.asignado_a.get_full_name() if o.asignado_a else 'No asignado'}\n"
            f"📅 <b>Creación:</b> {o.fecha_creacion.strftime('%d/%m/%Y %H:%M')}\n"
        )
        if o.fecha_limite:
            msg += f"⏰ <b>Fecha límite:</b> {o.fecha_limite.strftime('%d/%m/%Y %H:%M')}\n"
        if o.descripcion:
            msg += f"📄 <b>Descripción:</b>\n{o.descripcion}\n\n"

        msg += f"⏱️ <b>Total de horas:</b> {total_horas:.2f} hs\n"
        msg += f"📋 <b>Tareas asociadas:</b> {tareas_qs.count()}\n"

        buttons = []
        if tareas_qs.exists():
            msg += "\n📋 <b>Tareas:</b>\n"
            for t in tareas_qs[:5]:
                texto = f"🔧 {t.start.strftime('%d/%m %H:%M')} - {t.description[:25]}..."
                buttons.append([InlineKeyboardButton(texto, callback_data=f"ver_tarea:{t.id}")])

        buttons.extend([
            [InlineKeyboardButton("🔙 Volver a Órdenes", callback_data="volver_ordenes")],
            [InlineKeyboardButton("➕ Nueva Tarea", callback_data="nueva_tarea_bot")],
        ])
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")
    except Exception as e:
        logger.error(f"show_work_order_detail error: {e}")
        await query.edit_message_text("❌ Error al mostrar la orden.")

# -------- Flujo "nueva tarea" directo --------

async def handle_nueva_tarea_direct(query, context):
    try:
        chat_id = query.message.chat.id
        user = get_user_from_chat(chat_id)
        if not user:
            await query.edit_message_text("🚫 No estás autorizado.")
            return

        context.user_data.clear()
        context.user_data["technician"] = user
        context.user_data["chat_id"] = chat_id

        await ask_work_order_selection(query, context)
    except Exception as e:
        logger.error(f"handle_nueva_tarea_direct error: {e}")
        await query.edit_message_text("❌ Error interno del bot.")

async def ask_work_order_selection(update_or_query, context):
    try:
        from work_order.models import WorkOrder
        user = context.user_data.get("technician")
        assigned_orders = WorkOrder.objects.filter(asignado_a=user).exclude(estado="cerrada")
        collaborator_orders = WorkOrder.objects.filter(worklogs__collaborator=user).exclude(estado="cerrada").distinct()
        available_orders = assigned_orders.union(collaborator_orders)

        if available_orders.exists():
            buttons = [[InlineKeyboardButton("❌ No asociar a ninguna OT", callback_data="work_order:none")]]
            prioridad_emoji = {"urgente": "🔴", "alta": "🟠", "media": "🟡", "baja": "🟢"}
            for o in available_orders[:25]:
                texto = f"{prioridad_emoji.get(o.prioridad, '⚪')} {o.numero} - {o.titulo[:30]}..."
                buttons.append([InlineKeyboardButton(texto, callback_data=f"work_order:{o.id}")])

            if hasattr(update_or_query, "data"):
                await update_or_query.edit_message_text(
                    "📋 ¿Querés asociar esta tarea a una orden de trabajo?",
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
            else:
                await update_or_query.effective_chat.send_message(
                    "📋 ¿Querés asociar esta tarea a una orden de trabajo?",
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
        else:
            context.user_data["work_order"] = None
            if hasattr(update_or_query, "data"):
                await update_or_query.edit_message_text("No tenés órdenes disponibles. Continuando sin asociar…")
                await ask_task_type_selection(update_or_query, context)
            else:
                await update_or_query.effective_chat.send_message("No tenés órdenes disponibles. Continuando sin asociar…")
                await ask_task_type_selection(update_or_query, context)
    except Exception as e:
        logger.error(f"ask_work_order_selection error: {e}")
        if hasattr(update_or_query, "edit_message_text"):
            await update_or_query.edit_message_text("❌ Error al listar órdenes.")

async def handle_work_order_selection_direct(query, context):
    try:
        if query.data == "work_order:none":
            context.user_data["work_order"] = None
            await query.edit_message_text("✅ Continuando sin asociar a ninguna OT.")
        else:
            from work_order.models import WorkOrder
            work_order_id = int(query.data.split(":")[1])
            try:
                wo = WorkOrder.objects.get(id=work_order_id)
                context.user_data["work_order"] = wo
                await query.edit_message_text(f"✅ Tarea asociada a: {wo.numero} - {wo.titulo}")
            except WorkOrder.DoesNotExist:
                context.user_data["work_order"] = None
                await query.edit_message_text("⚠️ Orden no válida. Continuando sin asociar.")
        await ask_task_type_selection(query, context)
    except Exception as e:
        logger.error(f"handle_work_order_selection_direct error: {e}")
        await query.edit_message_text("❌ Error interno del bot.")

async def ask_task_type_selection(update_or_query, context):
    try:
        buttons = [
            [InlineKeyboardButton("🏭 Taller", callback_data="task_type:Taller")],
            [InlineKeyboardButton("🌍 Campo", callback_data="task_type:Campo")],
            [InlineKeyboardButton("📋 Diligencia", callback_data="task_type:Diligencia")],
            [InlineKeyboardButton("⚙️ Operaciones generales", callback_data="task_type:Operaciones generales")],
            [InlineKeyboardButton("🔧 Otros", callback_data="task_type:Otros")],
            [InlineKeyboardButton("❌ Cancelar Tarea", callback_data="cancelar")],
        ]
        if hasattr(update_or_query, "data"):
            await update_or_query.edit_message_text("🔧 Seleccioná el tipo de tarea:", reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await update_or_query.effective_chat.send_message("🔧 Seleccioná el tipo de tarea:", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        logger.error(f"ask_task_type_selection error: {e}")

async def ask_general_ops_subtype(update_or_query, context):
    try:
        buttons = [
            [InlineKeyboardButton("📦 Mandados/trámites", callback_data="general_ops_subtype:Mandados/tramites")],
            [InlineKeyboardButton("🗂️ Tareas administrativas", callback_data="general_ops_subtype:Tareas administrativas")],
            [InlineKeyboardButton("🚗 Movimiento de vehículos", callback_data="general_ops_subtype:Movimiento de vehiculos")],
            [InlineKeyboardButton("🧹 Limpieza", callback_data="general_ops_subtype:Limpieza")],
            [InlineKeyboardButton("❌ Cancelar Tarea", callback_data="cancelar")],
        ]
        if hasattr(update_or_query, "data"):
            await update_or_query.edit_message_text("⚙️ Elegí el subtipo de Operaciones generales:", reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await update_or_query.effective_chat.send_message("⚙️ Elegí el subtipo de Operaciones generales:", reply_markup=InlineKeyboardMarkup(buttons))
        context.user_data["waiting_for_general_ops_subtype"] = True
    except Exception as e:
        logger.error(f"ask_general_ops_subtype error: {e}")

async def handle_general_ops_subtype(query, context):
    try:
        subtype = query.data.split(":")[1]
        context.user_data["general_ops_subtype"] = subtype
        context.user_data["waiting_for_general_ops_subtype"] = False
        context.user_data["waiting_for_description"] = True
        await query.edit_message_text(f"✅ Subtipo seleccionado: {subtype}\n📝 Enviá la descripción de la tarea (texto o audio).")
    except Exception as e:
        logger.error(f"handle_general_ops_subtype error: {e}")
        await query.edit_message_text("❌ Error interno del bot.")

async def ask_warranty(update_or_query, context):
    try:
        buttons = [
            [InlineKeyboardButton("🛡️ Sí, es garantía", callback_data="warranty:yes")],
            [InlineKeyboardButton("❌ No", callback_data="warranty:no")],
        ]
        if hasattr(update_or_query, "data"):
            await update_or_query.edit_message_text("🛡️ ¿La tarea es garantía?", reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await update_or_query.effective_chat.send_message("🛡️ ¿La tarea es garantía?", reply_markup=InlineKeyboardMarkup(buttons))
        context.user_data["waiting_for_warranty"] = True
    except Exception as e:
        logger.error(f"ask_warranty error: {e}")

async def handle_warranty(query, context):
    try:
        val = query.data.split(":")[1]
        context.user_data["warranty"] = (val == "yes")
        context.user_data["waiting_for_warranty"] = False
        if context.user_data.get("task_type") == "Campo":
            await ask_field_city(query, context)
            return
        context.user_data["waiting_for_description"] = True
        await query.edit_message_text("📝 Enviá la descripción de la tarea (texto o audio).")
    except Exception as e:
        logger.error(f"handle_warranty error: {e}")
        await query.edit_message_text("❌ Error interno del bot.")

async def ask_field_city(update_or_query, context):
    try:
        if hasattr(update_or_query, "data"):
            await update_or_query.edit_message_text("🏙️ Ingresá la ciudad (Campo):")
        else:
            await update_or_query.effective_chat.send_message("🏙️ Ingresá la ciudad (Campo):")
        context.user_data["waiting_for_field_city"] = True
    except Exception as e:
        logger.error(f"ask_field_city error: {e}")
async def handle_task_type_selection_direct(query, context):
    try:
        task_type_value = query.data.split(":")[1]
        context.user_data["task_type"] = task_type_value
        if task_type_value == "Operaciones generales":
            await ask_general_ops_subtype(query, context)
            return
        if task_type_value in ["Taller", "Campo"]:
            await ask_warranty(query, context)
            return
        if task_type_value == "Otros":
            context.user_data["waiting_for_other_task_type"] = True
            await query.edit_message_text("✍️ Escribí el 'Otro tipo' de tarea.")
            return
        context.user_data["waiting_for_description"] = True
        await query.edit_message_text("📝 Enviá la descripción de la tarea (texto o audio).")
    except Exception as e:
        logger.error(f"handle_task_type_selection_direct error: {e}")
        await query.edit_message_text("❌ Error interno del bot.")

async def ask_status_direct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        buttons = [
            [InlineKeyboardButton("⏳ Pendiente", callback_data="status_direct:pendiente")],
            [InlineKeyboardButton("🔄 En Proceso", callback_data="status_direct:en_proceso")],
            [InlineKeyboardButton("⏸️ En Espera de Repuestos", callback_data="status_direct:en_espera_repuestos")],
            [InlineKeyboardButton("✅ Completada", callback_data="status_direct:completada")],
            [InlineKeyboardButton("❌ Cancelada", callback_data="status_direct:cancelada")],
            [InlineKeyboardButton("❌ Cancelar Tarea", callback_data="cancelar")],
        ]
        await update.message.reply_text("📊 Seleccioná el estado de la tarea:", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        logger.error(f"ask_status_direct error: {e}")
        await update.message.reply_text("❌ Error interno del bot.")

async def handle_status_selection_direct(query, context):
    try:
        status_value = query.data.split(":")[1]
        context.user_data["status"] = status_value
        await query.edit_message_text(f"✅ Estado seleccionado: {status_value}")
        context.user_data["waiting_for_duration"] = True
        await query.edit_message_text("⏱️ ¿Cuánto tiempo duró la tarea? (ej: 2:30, 0:20, 10:50)")
    except Exception as e:
        logger.error(f"handle_status_selection_direct error: {e}")
        await query.edit_message_text("❌ Error interno del bot.")

async def ask_collaborator_direct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        buttons = [
            [InlineKeyboardButton("❌ No agregar colaborador", callback_data="colaborador_direct:none")],
            [InlineKeyboardButton("✅ Sí, agregar colaborador", callback_data="colaborador_direct:yes")],
        ]
        await update.message.reply_text("👥 ¿Querés agregar un colaborador a esta tarea?", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        logger.error(f"ask_collaborator_direct error: {e}")
        await update.message.reply_text("❌ Error interno del bot.")

async def handle_collaborator_direct(query, context):
    try:
        if query.data == "colaborador_direct:none":
            context.user_data["collaborator"] = None
            # Si la transcripción no está lista, NO mostrar resumen ni botones; avisar y esperar
            if context.user_data.get("pending_transcription"):
                context.user_data["awaiting_transcription_for_summary"] = True
                await query.edit_message_text("⏳ Procesando audio… Te aviso cuando esté la transcripción para confirmar y guardar la tarea.")
                return
            # Si ya está lista, mostrar resumen con botones
            return await show_task_summary_direct(query, context)

        tecnicos = CustomUser.objects.filter(user_type="tecnico").exclude(id=context.user_data["technician"].id)
        if not tecnicos.exists():
            context.user_data["collaborator"] = None
            if context.user_data.get("pending_transcription"):
                context.user_data["awaiting_transcription_for_summary"] = True
                await query.edit_message_text("⏳ Procesando audio… Te aviso cuando esté la transcripción para confirmar y guardar la tarea.")
                return
            return await show_task_summary_direct(query, context)

        buttons = [[InlineKeyboardButton(f"👷 {t.get_full_name()}", callback_data=f"colaborador_select:{t.id}")]
                   for t in tecnicos[:10]]
        buttons.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancelar")])

        await query.edit_message_text("👥 Seleccioná el colaborador:", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        logger.error(f"handle_collaborator_direct error: {e}")
        await query.edit_message_text("❌ Error interno del bot.")

async def handle_collaborator_select_direct(query, context):
    try:
        collaborator_id = int(query.data.split(":")[1])
        colab = CustomUser.objects.filter(id=collaborator_id, user_type="tecnico").first()
        if colab:
            context.user_data["collaborator"] = colab
            await query.edit_message_text(f"✅ Colaborador seleccionado: {colab.get_full_name()}")
        else:
            context.user_data["collaborator"] = None
            await query.edit_message_text("❌ Técnico no encontrado. Continuando sin colaborador.")
        # Gate por transcripción
        if context.user_data.get("pending_transcription"):
            context.user_data["awaiting_transcription_for_summary"] = True
            await query.edit_message_text("⏳ Procesando audio… Te aviso cuando esté la transcripción para confirmar y guardar la tarea.")
            return
        await show_task_summary_direct(query, context)
    except Exception as e:
        logger.error(f"handle_collaborator_select_direct error: {e}")
        await query.edit_message_text("❌ Error interno del bot.")

async def show_task_summary_direct(query, context):
    try:
        # Si todavía transcribe, gatear
        if context.user_data.get("pending_transcription"):
            context.user_data["awaiting_transcription_for_summary"] = True
            await query.edit_message_text("⏳ Procesando audio… Te aviso cuando esté la transcripción para confirmar y guardar la tarea.")
            return

        summary, buttons = build_summary_text_and_markup(context)
        await query.edit_message_text(summary, reply_markup=buttons, parse_mode="HTML")
    except Exception as e:
        logger.error(f"show_task_summary_direct error: {e}")
        await query.edit_message_text("❌ Error al mostrar el resumen.")

async def save_task_direct(query, context):
    try:
        if not ensure_db_connection():
            await query.edit_message_text("❌ Error de conexión a DB. No se pudo guardar.")
            return ConversationHandler.END

        user = context.user_data["technician"]
        end_time = timezone.now()
        duration_td = context.user_data.get("duration_td", timedelta())
        start_time = end_time - duration_td
        task_type = context.user_data["task_type"]
        status_value = context.user_data.get("status", "pendiente")
        collaborator = context.user_data.get("collaborator")
        work_order = context.user_data.get("work_order")
        audio_file_relative = context.user_data.get("audio_file_relative")

        # A esta altura, como gateamos, no debería quedar pendiente, pero por seguridad:
        if context.user_data.get("pending_transcription"):
            await query.edit_message_text("⏳ Aún estamos transcribiendo el audio. Te muestro los botones cuando termine.")
            context.user_data["awaiting_transcription_for_summary"] = True
            return ConversationHandler.END

        final_description = context.user_data.get("description", "")

        work_order_value = work_order.numero if work_order else None
        work_order_ref = work_order if work_order else None

        # Crear la tarea
        worklog = WorkLog.objects.create(
            technician=user,
            collaborator=collaborator,
            start=start_time,
            end=end_time,
            task_type=task_type,
            other_task_type=context.user_data.get("other_task_type") if task_type == "Otros" else None,
            general_ops_subtype=context.user_data.get("general_ops_subtype") if task_type == "Operaciones generales" else None,
            warranty=context.user_data.get("warranty", False) if task_type in ["Taller", "Campo"] else False,
            field_city=context.user_data.get("field_city") if task_type == "Campo" else None,
            field_km_one_way=context.user_data.get("field_km_one_way") if task_type == "Campo" else None,
            description=final_description,
            status=status_value,
            work_order=work_order_value,
            work_order_ref=work_order_ref,
            created_by=user,
            audio_file=audio_file_relative if audio_file_relative else None,
        )

        # Log de actividad del usuario
        logger.info(f"Usuario {user.get_full_name()} ({user.username}) creó tarea #{worklog.id}: {task_type} - {final_description[:50]}...")
        if work_order:
            logger.info(f"Tarea #{worklog.id} asociada a OT: {work_order.numero}")

        msg = "✅ Tarea registrada correctamente."
        if work_order:
            msg += f"\n📋 Asociada a: {work_order.numero} - {work_order.titulo}"
        await query.edit_message_text(msg)
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"save_task_direct error: {e}")
        await query.edit_message_text("❌ Error al guardar la tarea.")
        return ConversationHandler.END

async def edit_transcription_direct(query, context):
    try:
        audio_file_relative = context.user_data.get("audio_file_relative")
        if audio_file_relative:
            await query.edit_message_text(
                "📝 ¿Querés editar la transcripción? (Texto o Audio)",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Texto", callback_data="edit_transcription_text")],
                    [InlineKeyboardButton("Audio", callback_data="edit_transcription_audio")],
                    [InlineKeyboardButton("❌ Cancelar", callback_data="cancelar")],
                ])
            )
        else:
            await query.edit_message_text(
                "📝 ¿Querés editar la transcripción? (Texto)",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Texto", callback_data="edit_transcription_text")],
                    [InlineKeyboardButton("❌ Cancelar", callback_data="cancelar")],
                ])
            )
    except Exception as e:
        logger.error(f"edit_transcription_direct error: {e}")
        await query.edit_message_text("❌ Error interno del bot.")

async def handle_edit_transcription_text(query, context):
    try:
        context.user_data["waiting_for_description"] = True
        context.user_data["transcription_complete"] = False
        context.user_data["pending_transcription"] = False
        await query.edit_message_text("📝 Escribí la nueva descripción de la tarea (texto).", reply_markup=ReplyKeyboardRemove())
    except Exception as e:
        logger.error(f"handle_edit_transcription_text error: {e}")
        await query.edit_message_text("❌ Error interno del bot.")

async def handle_edit_transcription_audio(query, context):
    try:
        context.user_data["waiting_for_description"] = True
        context.user_data["transcription_complete"] = False
        context.user_data["pending_transcription"] = False
        await query.edit_message_text("🎵 Enviá el nuevo audio de la tarea.", reply_markup=ReplyKeyboardRemove())
    except Exception as e:
        logger.error(f"handle_edit_transcription_audio error: {e}")
        await query.edit_message_text("❌ Error interno del bot.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.callback_query:
            await update.callback_query.edit_message_text("❌ Operación cancelada.")
        else:
            await update.message.reply_text("❌ Operación cancelada.")
        context.user_data.clear()
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"cancel error: {e}")
        return ConversationHandler.END

# ----------------------------
# Entrada de mensajes (texto/voz) para flujo directo y edición
# ----------------------------
async def handle_text_or_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Único handler para texto y audio.
    Flags:
      - waiting_for_description
      - waiting_for_duration
      - pending_transcription
      - awaiting_transcription_for_summary
    """
    try:
        # 1a) ¿Esperamos 'otro tipo'?
        if context.user_data.get("waiting_for_other_task_type"):
            raw_text = update.message.text or ""
            
            # Validar texto
            text_valid, text_error = validate_text(raw_text)
            if not text_valid:
                await update.message.reply_text(f"❌ {text_error}")
                log_security_event("other_task_type_rejected", {
                    "text_length": len(raw_text),
                    "error": text_error
                }, update.effective_user.id)
                return
            
            # Sanitizar texto
            other_text = sanitize_text(raw_text)
            context.user_data["other_task_type"] = other_text.strip()
            context.user_data["waiting_for_other_task_type"] = False
            context.user_data["waiting_for_description"] = True
            await update.message.reply_text("📝 Enviá la descripción de la tarea (texto o audio).")
            return

        # 1b) ¿Esperamos descripción?
        if context.user_data.get("waiting_for_description"):
            if update.message.voice:
                # Validar duración del audio
                duration_valid, duration_error = validate_audio_duration(update.message.voice.duration)
                if not duration_valid:
                    await update.message.reply_text(f"❌ {duration_error}")
                    log_security_event("audio_duration_rejected", {
                        "duration": update.message.voice.duration,
                        "error": duration_error
                    }, update.effective_user.id)
                    return

                # Guardar audio y lanzar transcripción
                audio_file = await context.bot.get_file(update.message.voice.file_id)

                rel_dir = "worklog_audios"
                abs_dir = os.path.join("media", rel_dir)
                os.makedirs(abs_dir, exist_ok=True)
                rel_path = f"{rel_dir}/audio_{update.effective_user.id}_{int(time.time())}.ogg"
                abs_path = os.path.join("media", rel_path)

                await audio_file.download_to_drive(abs_path)

                # Validar archivo de audio
                try:
                    size_bytes = os.path.getsize(abs_path)
                    file_info = get_file_info(abs_path)
                    
                    # Validar archivo
                    audio_valid, audio_error = validate_audio_file(abs_path, size_bytes)
                    if not audio_valid:
                        # Eliminar archivo inválido
                        try:
                            os.remove(abs_path)
                        except:
                            pass
                        
                        await update.message.reply_text(f"❌ {audio_error}")
                        log_security_event("audio_file_rejected", {
                            "file_info": file_info,
                            "error": audio_error
                        }, update.effective_user.id)
                        return
                    
                    logger.info(f"Audio validado y guardado: {abs_path} ({size_bytes} bytes)")
                    
                except Exception as e:
                    logger.error(f"Error validando audio: {e}")
                    await update.message.reply_text("❌ Error al procesar el archivo de audio")
                    return

                context.user_data["audio_file_relative"] = rel_path
                context.user_data["pending_transcription"] = True
                context.user_data["description"] = "[Audio adjunto - Transcribiendo…]"

                async def _bg(apath: str, chat_id: int):
                    try:
                        text = await fw_transcribe_in_executor(apath)
                        if context.user_data is not None:
                            if text:
                                # Validar texto transcrito
                                text_valid, text_error = validate_text(text)
                                if not text_valid:
                                    # Sanitizar texto si es muy largo o tiene caracteres problemáticos
                                    sanitized_text = sanitize_text(text)
                                    if len(sanitized_text) < 50:  # Si después de sanitizar es muy corto
                                        context.user_data["description"] = "[Audio adjunto - Transcripción no válida]"
                                        context.user_data["pending_transcription"] = False
                                        await context.bot.send_message(
                                            chat_id, 
                                            f"⚠️ Transcripción rechazada por seguridad: {text_error}"
                                        )
                                        log_security_event("transcription_rejected", {
                                            "error": text_error,
                                            "original_length": len(text)
                                        }, update.effective_user.id)
                                        return
                                    else:
                                        text = sanitized_text
                                        await context.bot.send_message(
                                            chat_id, 
                                            f"📝 Transcripción sanitizada:\n{text}"
                                        )
                                else:
                                    await context.bot.send_message(chat_id, f"📝 Transcripción lista:\n{text}")
                                
                                context.user_data["description"] = text
                                context.user_data["transcription_complete"] = True
                                context.user_data["pending_transcription"] = False
                            else:
                                context.user_data["description"] = "[Audio adjunto - Sin texto detectado]"
                                context.user_data["pending_transcription"] = False
                                try:
                                    size_b = os.path.getsize(apath)
                                except Exception:
                                    size_b = -1
                                await context.bot.send_message(
                                    chat_id,
                                    "⚠️ No se detectó texto en el audio.\n"
                                    f"(archivo: {os.path.basename(apath)}, tamaño: {size_b} bytes)\n"
                                    "Tip: hablá más cerca del micrófono o en un ambiente sin ruido."
                                )
                            # Si estábamos esperando para mostrar la última pregunta, enviarla ahora:
                            if context.user_data.get("awaiting_transcription_for_summary"):
                                summary, buttons = build_summary_text_and_markup(context)
                                await context.bot.send_message(chat_id, summary, reply_markup=buttons, parse_mode="HTML")
                                context.user_data["awaiting_transcription_for_summary"] = False
                    except Exception as e:
                        context.user_data["description"] = "[Audio adjunto - Error en transcripción]"
                        context.user_data["pending_transcription"] = False
                        await context.bot.send_message(chat_id, f"❌ Error transcribiendo: {e}")

                chat_id = update.effective_chat.id
                asyncio.create_task(_bg(abs_path, chat_id))
                await update.message.reply_text("🎵 Audio recibido. Transcribiendo…")

            else:
                # Texto directo - Validar contenido
                raw_text = update.message.text or ""
                
                # Validar texto
                text_valid, text_error = validate_text(raw_text)
                if not text_valid:
                    await update.message.reply_text(f"❌ {text_error}")
                    log_security_event("text_rejected", {
                        "text_length": len(raw_text),
                        "error": text_error
                    }, update.effective_user.id)
                    return
                
                # Sanitizar texto
                description = sanitize_text(raw_text)
                context.user_data["description"] = description
                context.user_data["transcription_complete"] = True
                context.user_data["pending_transcription"] = False

            context.user_data["waiting_for_description"] = False
            await ask_status_direct(update, context)
            return

        # 2a) ¿Esperamos subtipo de Operaciones generales?
        if context.user_data.get("waiting_for_general_ops_subtype"):
            # No manejamos por texto; viene por callback
            return

        # 2b) ¿Esperamos garantía?
        if context.user_data.get("waiting_for_warranty"):
            # No manejamos por texto; viene por callback
            return

        # 2c) ¿Esperamos ciudad/kms de Campo?
        if context.user_data.get("waiting_for_field_city"):
            raw_text = update.message.text or ""
            
            # Validar texto (más permisivo para nombres de ciudades)
            if len(raw_text) > 100:  # Límite más alto para nombres de ciudades
                await update.message.reply_text("❌ Nombre de ciudad demasiado largo. Máximo 100 caracteres.")
                log_security_event("city_name_rejected", {
                    "text_length": len(raw_text)
                }, update.effective_user.id)
                return
            
            # Sanitizar texto (solo caracteres básicos para nombres)
            city = re.sub(r'[^\w\s\-\.]', '', raw_text).strip()
            if not city:
                await update.message.reply_text("❌ Nombre de ciudad inválido.")
                return
            
            context.user_data["field_city"] = city
            context.user_data["waiting_for_field_city"] = False
            context.user_data["waiting_for_field_km"] = True
            await update.message.reply_text("🛣️ Ingresá los kilómetros de ida (número entero).")
            return
        if context.user_data.get("waiting_for_field_km"):
            km_text = update.message.text or ""
            
            # Validar que sea solo números
            if not km_text.isdigit():
                await update.message.reply_text("❌ Debe ser un número entero positivo. Probá de nuevo.")
                log_security_event("km_input_rejected", {
                    "input": km_text
                }, update.effective_user.id)
                return
            
            try:
                km_val = int(km_text)
                if km_val < 0 or km_val > 9999:  # Límite razonable para kilómetros
                    raise ValueError()
                context.user_data["field_km_one_way"] = km_val
                context.user_data["waiting_for_field_km"] = False
                context.user_data["waiting_for_description"] = True
                await update.message.reply_text("📝 Enviá la descripción de la tarea (texto o audio).")
            except ValueError:
                await update.message.reply_text("❌ Debe ser un número entero positivo entre 0 y 9999. Probá de nuevo.")
            return

        # 2d) ¿Esperamos duración?
        if context.user_data.get("waiting_for_duration"):
            duration_text = update.message.text or ""
            
            # Validar formato básico
            if len(duration_text) > 10:  # Límite razonable para formato de tiempo
                await update.message.reply_text("❌ Formato de duración inválido. Usá H:MM (ej: 2:30) o minutos (ej: 24).")
                log_security_event("duration_format_rejected", {
                    "input": duration_text
                }, update.effective_user.id)
                return
            
            # Validar que solo contenga caracteres permitidos
            if not re.match(r'^[\d:]+$', duration_text):
                await update.message.reply_text("❌ Formato inválido. Solo números y dos puntos. Usá H:MM (ej: 2:30) o minutos (ej: 24).")
                return
            
            try:
                td = parse_hhmm_to_timedelta(duration_text)
                context.user_data["duration_td"] = td
                context.user_data["waiting_for_duration"] = False
                await update.message.reply_text(f"✅ Duración registrada: {duration_text}")
                await ask_collaborator_direct(update, context)
            except ValueError:
                await update.message.reply_text("❌ Formato inválido. Usá H:MM (ej: 2:30) o minutos (ej: 24).")
            return

        # Si no esperamos nada, no respondemos
    except Exception as e:
        logger.error(f"handle_text_or_voice error: {e}")
        await update.message.reply_text("❌ Error al procesar el mensaje.")

# ----------------------------
# Conversación /nueva_tarea (opcional)
# ----------------------------
async def nueva_tarea_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not ensure_db_connection():
            await update.message.reply_text("❌ Error de conexión a DB. Probá más tarde.")
            return ConversationHandler.END
        chat_id = update.effective_chat.id
        user = get_user_from_chat(chat_id)
        if not user:
            await update.message.reply_text("🚫 No estás autorizado.")
            return ConversationHandler.END

        context.user_data.clear()
        context.user_data["technician"] = user
        context.user_data["chat_id"] = chat_id

        await ask_work_order_selection(update, context)
        return SELECTING_WORK_ORDER
    except Exception as e:
        logger.error(f"nueva_tarea_start error: {e}")
        await update.message.reply_text("❌ Error interno del bot.")
        return ConversationHandler.END

async def conv_select_work_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        if query.data == "work_order:none":
            context.user_data["work_order"] = None
            await query.edit_message_text("✅ Continuando sin asociar a ninguna OT.")
        else:
            from work_order.models import WorkOrder
            work_order_id = int(query.data.split(":")[1])
            try:
                wo = WorkOrder.objects.get(id=work_order_id)
                context.user_data["work_order"] = wo
                await query.edit_message_text(f"✅ Tarea asociada a: {wo.numero} - {wo.titulo}")
            except WorkOrder.DoesNotExist:
                context.user_data["work_order"] = None
                await query.edit_message_text("⚠️ Orden no válida. Continuando sin asociar.")

        await ask_task_type_selection(query, context)
        return SELECTING_TASK_TYPE
    except Exception as e:
        logger.error(f"conv_select_work_order error: {e}")
        await update.callback_query.edit_message_text("❌ Error interno del bot.")
        return ConversationHandler.END

async def conv_select_task_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        task_type_value = query.data.split(":")[1]
        context.user_data["task_type"] = task_type_value
        context.user_data["waiting_for_description"] = True
        await query.edit_message_text("📝 Enviá la descripción de la tarea (texto o audio).")
        return ENTERING_DESCRIPTION
    except Exception as e:
        logger.error(f"conv_select_task_type error: {e}")
        await update.callback_query.edit_message_text("❌ Error interno del bot.")
        return ConversationHandler.END

async def conv_enter_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_text_or_voice(update, context)
    return SELECTING_STATUS

async def conv_select_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        if query.data.startswith("status_direct:"):
            status_value = query.data.split(":")[1]
            context.user_data["status"] = status_value
            await query.edit_message_text(f"✅ Estado seleccionado: {status_value}")
            context.user_data["waiting_for_duration"] = True
            await query.edit_message_text("⏱️ ¿Cuánto tiempo duró la tarea? (ej: 2:30, 0:20, 10:50)")
            return ENTERING_DURATION
    except Exception as e:
        logger.error(f"conv_select_status error: {e}")
        await update.callback_query.edit_message_text("❌ Error interno del bot.")
        return ConversationHandler.END

async def conv_enter_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_text_or_voice(update, context)
    return ASK_COLLABORATOR

async def conv_ask_collaborator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return SELECTING_COLLABORATOR

# ----------------------------
# Main
# ----------------------------
def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN no definido.")
        sys.exit(1)

    logger.info("==== Diagnóstico entorno ====")
    logger.info("cpu_count=%s platform=%s", os.cpu_count(), sys.platform)
    logger.info("faster-whisper compute_type=int8 cpu_threads=%s", CPU_COUNT)
    logger.info("=============================")

    # Precarga modelo para evitar cold-start
    get_fw_model()

    application: Application = ApplicationBuilder().token(token).build()

    # Comandos
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("tareas", tareas))
    application.add_handler(CommandHandler("ver_OTs", ver_OTs))
    application.add_handler(CommandHandler("nueva_tarea", nueva_tarea_start))

    # Router de callbacks
    application.add_handler(CallbackQueryHandler(callback_query_router))

    # Un único handler para texto y voz (flujo directo + edición)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_or_voice))
    application.add_handler(MessageHandler(filters.VOICE, handle_text_or_voice))

    # Conversación opcional
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("nueva_tarea", nueva_tarea_start)],
        states={
            SELECTING_WORK_ORDER: [CallbackQueryHandler(conv_select_work_order, pattern="^work_order:")],
            SELECTING_TASK_TYPE: [CallbackQueryHandler(conv_select_task_type, pattern="^task_type:")],
            ENTERING_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, conv_enter_description),
                MessageHandler(filters.VOICE, conv_enter_description),
            ],
            SELECTING_STATUS: [CallbackQueryHandler(conv_select_status, pattern="^status_direct:")],
            ENTERING_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, conv_enter_duration)],
            ASK_COLLABORATOR: [CallbackQueryHandler(callback_query_router, pattern="^(colaborador_direct:|colaborador_select:)")],
            SELECTING_COLLABORATOR: [CallbackQueryHandler(callback_query_router, pattern="^(save_task_direct|cancelar)$")],
        },
        fallbacks=[CallbackQueryHandler(cancel, pattern="^cancelar$"), CommandHandler("cancel", cancel)],
        allow_reentry=True,
        per_chat=True,     # Rastrear conversaciones por chat individual
        per_user=True,     # Rastrear conversaciones por usuario individual
    )
    application.add_handler(conv_handler)

    logger.info("Bot iniciado (faster-whisper)…")
    application.run_polling()

if __name__ == "__main__":
    main()
