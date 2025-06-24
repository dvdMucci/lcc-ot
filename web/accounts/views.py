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
    context = {
        'user': request.user,
        'user_count': CustomUser.objects.count() if request.user.can_manage_users() else None,
    }
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
