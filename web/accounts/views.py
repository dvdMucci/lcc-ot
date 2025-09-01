from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp.util import random_hex # No usado directamente en el código provisto, pero útil para OTP
import qrcode
import io
import base64
import pyotp # Necesario para la generación de la URL de configuración, aunque TOTPDevice lo maneja
from .models import CustomUser
from .forms import CustomUserCreationForm, ProfileForm, LoginForm, ChangePasswordForm

def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST, request=request)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('dashboard')
    else:
        form = LoginForm()
    
    return render(request, 'accounts/login.html', {'form': form})

@login_required
def logout_view(request):
    logout(request)
    return redirect('login')

@login_required
def dashboard(request):
    from django.db.models import Count, Sum, Q
    from django.utils import timezone
    from datetime import datetime, timedelta
    from work_order.models import WorkOrder
    from worklog.models import WorkLog
    
    # Estadísticas básicas
    context = {
        'user': request.user,
        'user_count': CustomUser.objects.count() if request.user.can_manage_users() else None,
    }
    
    # Estadísticas de órdenes de campo
    total_ordenes = WorkOrder.objects.count()
    ordenes_abiertas = WorkOrder.objects.filter(estado='abierta').count()
    ordenes_cerradas = WorkOrder.objects.filter(estado='cerrada').count()
    
    context.update({
        'total_ordenes': total_ordenes,
        'ordenes_abiertas': ordenes_abiertas,
        'ordenes_cerradas': ordenes_cerradas,
    })
    
    # Estadísticas de horas según el tipo de usuario
    if request.user.user_type == 'admin':
        # Para administradores: horas de todos los técnicos
        # Obtener todos los worklogs y calcular horas en Python
        worklogs = WorkLog.objects.select_related('technician').all()
        total_horas = 0
        horas_por_tecnico_dict = {}
        
        for worklog in worklogs:
            if worklog.start and worklog.end:
                horas = (worklog.end - worklog.start).total_seconds() / 3600
                total_horas += horas
                
                # Acumular horas por técnico
                username = worklog.technician.username
                if username not in horas_por_tecnico_dict:
                    horas_por_tecnico_dict[username] = 0
                horas_por_tecnico_dict[username] += horas
        
        # Convertir a lista ordenada para el top 5
        horas_por_tecnico = [
            {'technician__username': username, 'total_horas': round(horas, 2)}
            for username, horas in sorted(horas_por_tecnico_dict.items(), key=lambda x: x[1], reverse=True)[:5]
        ]
        
        context.update({
            'total_horas': round(total_horas, 2),
            'horas_por_tecnico': horas_por_tecnico,
            'es_admin': True
        })
    else:
        # Para otros usuarios: solo sus propias horas
        worklogs = WorkLog.objects.filter(technician=request.user).all()
        total_horas = 0
        
        for worklog in worklogs:
            if worklog.start and worklog.end:
                horas = (worklog.end - worklog.start).total_seconds() / 3600
                total_horas += horas
        
        context.update({
            'total_horas': round(total_horas, 2),
            'es_admin': False
        })
    
    # Gráfico de horas semanales del usuario actual (últimas 8 semanas)
    semanas = []
    horas_por_semana = []
    
    for i in range(8):
        fecha_fin = timezone.now() - timedelta(weeks=i)
        fecha_inicio = fecha_fin - timedelta(days=7)
        
        # Obtener horas de la semana del usuario actual
        worklogs_semana = WorkLog.objects.filter(
            technician=request.user,
            start__gte=fecha_inicio,
            start__lt=fecha_fin
        )
        
        total_horas_semana = 0
        for worklog in worklogs_semana:
            if worklog.start and worklog.end:
                horas = (worklog.end - worklog.start).total_seconds() / 3600
                total_horas_semana += horas
        
        semana_label = f"Sem {fecha_fin.strftime('%d/%m')}"
        semanas.append(semana_label)
        horas_por_semana.append(round(total_horas_semana, 1))
    
    # Invertir para mostrar del más reciente al más antiguo
    semanas.reverse()
    horas_por_semana.reverse()
    
    # Gráfico de horas mensuales del usuario actual (últimos 12 meses)
    meses = []
    horas_por_mes = []
    
    for i in range(12):
        fecha = timezone.now() - timedelta(days=30*i)
        fecha_inicio = fecha.replace(day=1)
        if i == 0:
            fecha_fin = timezone.now()
        else:
            fecha_fin = fecha_inicio + timedelta(days=32)
            fecha_fin = fecha_inicio.replace(day=1) - timedelta(days=1)
        
        # Obtener horas del mes del usuario actual
        worklogs_mes = WorkLog.objects.filter(
            technician=request.user,
            start__gte=fecha_inicio,
            start__lte=fecha_fin
        )
        
        total_horas_mes = 0
        for worklog in worklogs_mes:
            if worklog.start and worklog.end:
                horas = (worklog.end - worklog.start).total_seconds() / 3600
                total_horas_mes += horas
        
        mes_label = fecha.strftime('%b %Y')
        meses.append(mes_label)
        horas_por_mes.append(round(total_horas_mes, 1))
    
    # Invertir para mostrar del más reciente al más antiguo
    meses.reverse()
    horas_por_mes.reverse()
    
    # Gráfico de torta: distribución de tareas por tipo
    # Obtener todas las tareas del usuario actual
    worklogs_usuario = WorkLog.objects.filter(technician=request.user).select_related('work_order_ref')
    
    # Contar horas por tipo de tarea
    horas_por_tipo = {}
    horas_por_subtarea = {}
    horas_por_estado = {}
    
    # Datos para tabla de resumen
    resumen_tareas = []
    
    for worklog in worklogs_usuario:
        if worklog.start and worklog.end:
            horas = (worklog.end - worklog.start).total_seconds() / 3600
            
            # Tipo principal de tarea
            tipo_principal = worklog.task_type
            if tipo_principal not in horas_por_tipo:
                horas_por_tipo[tipo_principal] = 0
            horas_por_tipo[tipo_principal] += horas
            
            # Estado de la tarea
            estado = worklog.status
            if estado not in horas_por_estado:
                horas_por_estado[estado] = 0
            horas_por_estado[estado] += horas
            
            # Subtareas específicas con más detalle
            if tipo_principal == 'Operaciones generales' and worklog.general_ops_subtype:
                subtarea = f"Op. Gen: {worklog.general_ops_subtype}"
            elif tipo_principal == 'Otros' and worklog.other_task_type:
                subtarea = f"Otros: {worklog.other_task_type}"
            elif tipo_principal == 'Campo' and worklog.field_city:
                subtarea = f"Campo: {worklog.field_city}"
            elif tipo_principal == 'Taller':
                subtarea = f"Taller: {worklog.description[:30] if worklog.description else 'Sin descripción'}"
            else:
                subtarea = f"{tipo_principal}: {worklog.description[:30] if worklog.description else 'Sin descripción'}"
            
            if subtarea not in horas_por_subtarea:
                horas_por_subtarea[subtarea] = 0
            horas_por_subtarea[subtarea] += horas
            
            # Agregar a resumen para tabla
            resumen_tareas.append({
                'tipo': worklog.task_type,
                'estado': worklog.status,
                'descripcion': worklog.description,
                'horas': round(horas, 1),
                'fecha': worklog.start.date(),
                'orden_trabajo': worklog.work_order_ref.numero if worklog.work_order_ref else worklog.work_order or 'N/A'
            })
    
    # Preparar datos para el gráfico de torta
    tipos_tarea = list(horas_por_tipo.keys())
    horas_tipos = [round(horas, 1) for horas in horas_por_tipo.values()]
    
    subtareas = list(horas_por_subtarea.keys())
    horas_subtareas = [round(horas, 1) for horas in horas_por_subtarea.values()]
    
    estados = list(horas_por_estado.keys())
    horas_estados = [round(horas, 1) for horas in horas_por_estado.values()]
    
    # Ordenar resumen por fecha más reciente
    resumen_tareas.sort(key=lambda x: x['fecha'], reverse=True)
    
    context.update({
        'semanas': semanas,
        'horas_por_semana': horas_por_semana,
        'meses': meses,
        'horas_por_mes': horas_por_mes,
        'tipos_tarea': tipos_tarea,
        'horas_tipos': horas_tipos,
        'subtareas': subtareas,
        'horas_subtareas': horas_subtareas,
        'estados': estados,
        'horas_estados': horas_estados,
        'resumen_tareas': resumen_tareas[:20],  # Últimas 20 tareas
    })
    
    return render(request, 'dashboard.html', context)

@login_required
def profile_view(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Perfil actualizado correctamente')
            return redirect('profile')
    else:
        form = ProfileForm(instance=request.user)
    
    # Obtener dispositivo TOTP
    totp_device = request.user.totpdevice_set.filter(confirmed=True).first()
    
    context = {
        'form': form,
        'totp_device': totp_device,
        'is_2fa_enabled': request.user.is_2fa_enabled,
    }
    return render(request, 'accounts/profile.html', context)

@login_required
def setup_2fa(request):
    # Crear o obtener dispositivo TOTP
    device, created = TOTPDevice.objects.get_or_create(
        user=request.user,
        name='default',
        defaults={'confirmed': False}
    )
    
    if not device.confirmed:
        # Generar QR code
        qr_code_url = device.config_url
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_code_url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        qr_code_data = base64.b64encode(buffer.getvalue()).decode()
        
        if request.method == 'POST':
            token = request.POST.get('token')
            if device.verify_token(token):
                device.confirmed = True
                device.save()
                request.user.is_2fa_enabled = True
                request.user.save()
                messages.success(request, '2FA configurado correctamente')
                return redirect('profile')
            else:
                messages.error(request, 'Código inválido')
        
        context = {
            'qr_code_data': qr_code_data,
            'secret_key': device.key, # La clave secreta es útil para depuración o si el usuario no puede escanear el QR
        }
        return render(request, 'accounts/setup_2fa.html', context)
    else:
        messages.info(request, '2FA ya está configurado')
        return redirect('profile')

@login_required
def disable_2fa(request):
    if request.method == 'POST':
        request.user.totpdevice_set.all().delete() # Elimina todos los dispositivos 2FA del usuario
        request.user.is_2fa_enabled = False
        request.user.save()
        messages.success(request, '2FA deshabilitado correctamente')
    return redirect('profile')

# Función de ayuda para verificar si el usuario es administrador
def is_admin(user):
    return user.is_authenticated and user.can_manage_users()

@user_passes_test(is_admin) # Decorador para restringir el acceso solo a administradores
def user_list(request):
    users = CustomUser.objects.all().order_by('-date_joined')
    paginator = Paginator(users, 10) # Paginación de 10 usuarios por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'accounts/user_list.html', {'page_obj': page_obj})

@user_passes_test(is_admin)
def user_create(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'Usuario {user.username} creado correctamente')
            return redirect('user_list')
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'accounts/user_form.html', {'form': form, 'title': 'Crear Usuario'})

@user_passes_test(is_admin)
def user_edit(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id)
    
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=user)
        user_type = request.POST.get('user_type')
        is_active = request.POST.get('is_active') == 'on' # Los checkboxes envían 'on' o nada
        
        if form.is_valid():
            user = form.save(commit=False) # Guarda el formulario pero no en la BD aún
            user.user_type = user_type
            user.is_active = is_active
            user.save() # Ahora guarda en la BD
            messages.success(request, f'Usuario {user.username} actualizado correctamente')
            return redirect('user_list')
    else:
        form = ProfileForm(instance=user)
    
    context = {
        'form': form,
        'user_obj': user,
        'user_types': CustomUser.USER_TYPES, # Pasa los tipos de usuario para el select
        'title': f'Editar Usuario: {user.username}'
    }
    return render(request, 'accounts/user_edit.html', context)

@user_passes_test(is_admin)
@require_http_methods(["POST"]) # Solo permite peticiones POST para eliminar
def user_delete(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id)
    
    if user == request.user:
        messages.error(request, 'No puedes eliminar tu propia cuenta')
    else:
        username = user.username
        user.delete()
        messages.success(request, f'Usuario {username} eliminado correctamente')
    
    return redirect('user_list')

@login_required
def change_password(request):
    if request.method == 'POST':
        # El PasswordChangeForm requiere la instancia del usuario
        form = ChangePasswordForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # Importante: Esto actualiza el hash de autenticación de la sesión del usuario
            # para evitar que se cierre la sesión después de cambiar la contraseña.
            update_session_auth_hash(request, user)
            messages.success(request, 'Tu contraseña ha sido actualizada correctamente.')
            return redirect('profile') # Redirige al perfil o a una página de éxito
        else:
            messages.error(request, 'Por favor, corrige los errores a continuación.')
    else:
        form = ChangePasswordForm(request.user)
    
    return render(request, 'accounts/change_password.html', {'form': form, 'title': 'Cambiar Contraseña'})
