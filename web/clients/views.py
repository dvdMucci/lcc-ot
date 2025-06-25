from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods

from .models import Client
from .forms import ClientForm

# Importa CustomUser para acceder a los tipos de usuario
from accounts.models import CustomUser 

# --- Funciones de ayuda para permisos ---
def can_manage_clients(user):
    # Administrador, Supervisor, Operador pueden crear/editar
    return user.user_type in ['admin', 'supervisor', 'operador']

def can_delete_client(user):
    # Solo Administrador puede eliminar
    return user.user_type == 'admin'

# --- Vistas del CRUD de Clientes ---

@login_required
def client_list(request):
    clients = Client.objects.all().order_by('razon_social')
    paginator = Paginator(clients, 10) # 10 clientes por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'clients/client_list.html', {'page_obj': page_obj})

@login_required
def dashboard(request):
    context = {
        'client_count': Client.objects.count(),
    }
    return render(request, 'dashboard.html', context)

@login_required
@user_passes_test(can_manage_clients)
def client_create(request):
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            client = form.save()
            messages.success(request, f'Cliente "{client.razon_social}" creado exitosamente.')
            return redirect('client_list')
        else:
            messages.error(request, 'Por favor, corrige los errores en el formulario.')
    else:
        form = ClientForm()
    
    return render(request, 'clients/client_form.html', {'form': form, 'title': 'Crear Nuevo Cliente'})

@login_required
def client_detail(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    # Para la vista de detalle, el formulario será de solo lectura si el usuario no puede editar
    if not can_manage_clients(request.user):
        form = ClientForm(instance=client)
        for field_name in form.fields:
            form.fields[field_name].widget.attrs['readonly'] = True
            form.fields[field_name].widget.attrs['disabled'] = True
    else:
        form = ClientForm(instance=client) # Si puede editar, muestra el formulario normalmente para edición
        
    return render(request, 'clients/client_detail.html', {
        'client': client,
        'form': form,
        'can_edit': can_manage_clients(request.user), # Pasa el permiso para mostrar botones
        'title': f'Detalle del Cliente: {client.razon_social}'
    })


@login_required
@user_passes_test(can_manage_clients)
def client_edit(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    
    if request.method == 'POST':
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            form.save()
            messages.success(request, f'Cliente "{client.razon_social}" actualizado exitosamente.')
            return redirect('client_list')
        else:
            messages.error(request, 'Por favor, corrige los errores en el formulario.')
    else:
        form = ClientForm(instance=client)
        
    return render(request, 'clients/client_form.html', {'form': form, 'title': f'Editar Cliente: {client.razon_social}'})

@login_required
@user_passes_test(can_delete_client)
@require_http_methods(["POST"]) # Solo permite eliminar con peticiones POST
def client_delete(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    client_name = client.razon_social
    try:
        client.delete()
        messages.success(request, f'Cliente "{client_name}" eliminado correctamente.')
    except Exception as e:
        messages.error(request, f'No se pudo eliminar el cliente "{client_name}": {e}')
    
    return redirect('client_list')