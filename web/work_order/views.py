from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.db.models import Prefetch, Q
from django.utils import timezone
from datetime import datetime, timedelta
from .models import WorkOrder
from .forms import WorkOrderForm, WorkOrderFilterForm
from .permissions import NotTecnicoRequiredMixin

try:
    from worklog.models import WorkLog
except Exception:  # pragma: no cover
    WorkLog = None

class OrdenListView(LoginRequiredMixin, ListView):
    model = WorkOrder
    paginate_by = 20
    ordering = ["-fecha_creacion"]
    template_name = "work_order/list.html"

    def get_queryset(self):
        queryset = super().get_queryset().select_related('cliente', 'asignado_a')
        
        # Si el usuario es técnico, filtrar solo las órdenes asignadas a él o donde figure como colaborador
        if hasattr(self.request.user, 'user_type'):
            is_tecnico = self.request.user.user_type == 'tecnico'
            if is_tecnico:
                # Obtener órdenes asignadas directamente al técnico
                assigned_orders = queryset.filter(asignado_a=self.request.user)
                
                # Obtener órdenes donde el técnico aparece como colaborador en alguna tarea
                if WorkLog:
                    collaborator_orders = queryset.filter(
                        worklogs__collaborator=self.request.user
                    ).distinct()
                    
                    # Combinar ambos querysets usando union para evitar problemas de unicidad
                    queryset = assigned_orders.union(collaborator_orders)
                else:
                    queryset = assigned_orders
        
        # Aplicar filtros
        form = WorkOrderFilterForm(self.request.GET or None)
        if form.is_valid():
            # Búsqueda general
            search = form.cleaned_data.get('search')
            if search:
                queryset = queryset.filter(
                    Q(cliente__razon_social__icontains=search) |
                    Q(cliente__cuit__icontains=search) |
                    Q(numero__icontains=search) |
                    Q(titulo__icontains=search) |
                    Q(descripcion__icontains=search)
                )
            
            # Filtros específicos
            cliente = form.cleaned_data.get('cliente')
            if cliente and len(cliente) >= 4:  # Mínimo 4 caracteres para búsqueda de cliente
                queryset = queryset.filter(cliente__razon_social__icontains=cliente)
            
            cuit = form.cleaned_data.get('cuit')
            if cuit:
                queryset = queryset.filter(cliente__cuit__icontains=cuit)
            
            numero_ot = form.cleaned_data.get('numero_ot')
            if numero_ot:
                queryset = queryset.filter(numero__icontains=numero_ot)
            
            titulo = form.cleaned_data.get('titulo')
            if titulo:
                queryset = queryset.filter(titulo__icontains=titulo)
            
            prioridad = form.cleaned_data.get('prioridad')
            if prioridad:
                queryset = queryset.filter(prioridad=prioridad)
            
            estado = form.cleaned_data.get('estado')
            if estado:
                queryset = queryset.filter(estado=estado)
            
            asignado_a = form.cleaned_data.get('asignado_a')
            if asignado_a:
                queryset = queryset.filter(asignado_a=asignado_a)
            
            # Filtros de fecha
            fecha_desde = form.cleaned_data.get('fecha_desde')
            if fecha_desde:
                queryset = queryset.filter(fecha_creacion__date__gte=fecha_desde)
            
            fecha_hasta = form.cleaned_data.get('fecha_hasta')
            if fecha_hasta:
                queryset = queryset.filter(fecha_creacion__date__lte=fecha_hasta)
            
            # Estado de vencimiento
            estado_vencimiento = form.cleaned_data.get('estado_vencimiento')
            if estado_vencimiento:
                now = timezone.now()
                if estado_vencimiento == 'vencidas':
                    queryset = queryset.filter(fecha_limite__lt=now)
                elif estado_vencimiento == 'por_vencer':
                    queryset = queryset.filter(fecha_limite__gte=now)
                elif estado_vencimiento == 'sin_limite':
                    queryset = queryset.filter(fecha_limite__isnull=True)
            
            # Ordenamiento
            ordenar_por = form.cleaned_data.get('ordenar_por')
            if ordenar_por:
                # Manejar ordenamiento especial para prioridad
                if ordenar_por in ['prioridad', '-prioridad']:
                    # Crear ordenamiento personalizado para prioridad
                    from django.db.models import Case, When, Value, IntegerField
                    priority_order = Case(
                        When(prioridad='urgente', then=Value(4)),
                        When(prioridad='alta', then=Value(3)),
                        When(prioridad='media', then=Value(2)),
                        When(prioridad='baja', then=Value(1)),
                        default=Value(0),
                        output_field=IntegerField(),
                    )
                    if ordenar_por == 'prioridad':
                        queryset = queryset.annotate(priority_order=priority_order).order_by('priority_order')
                    else:
                        queryset = queryset.annotate(priority_order=priority_order).order_by('-priority_order')
                else:
                    queryset = queryset.order_by(ordenar_por)
        
        self.filter_form = form
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = self.filter_form
        
        # Agregar estadísticas de filtros
        total_ordenes = self.get_queryset().count()
        context['total_ordenes'] = total_ordenes
        
        # Contar por estado
        context['estados_count'] = {
            'abierta': self.get_queryset().filter(estado='abierta').count(),
            'pendiente': self.get_queryset().filter(estado='pendiente').count(),
            'en_proceso': self.get_queryset().filter(estado='en_proceso').count(),
            'completada': self.get_queryset().filter(estado='completada').count(),
            'cerrada': self.get_queryset().filter(estado='cerrada').count(),
        }
        
        # Contar por prioridad
        context['prioridades_count'] = {
            'urgente': self.get_queryset().filter(prioridad='urgente').count(),
            'alta': self.get_queryset().filter(prioridad='alta').count(),
            'media': self.get_queryset().filter(prioridad='media').count(),
            'baja': self.get_queryset().filter(prioridad='baja').count(),
        }
        
        return context

class OrdenDetailView(LoginRequiredMixin, DetailView):
    model = WorkOrder
    template_name = "work_order/detail.html"

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        
        # Si el usuario es técnico, verificar que tenga acceso a esta orden
        if hasattr(self.request.user, 'user_type'):
            is_tecnico = self.request.user.user_type == 'tecnico'
            if is_tecnico:
                # Verificar si está asignado directamente o es colaborador
                has_access = False
                
                # Verificar asignación directa
                if obj.asignado_a == self.request.user:
                    has_access = True
                
                # Verificar si es colaborador en alguna tarea
                if not has_access and WorkLog:
                    has_access = WorkLog.objects.filter(
                        work_order_ref=obj,
                        collaborator=self.request.user
                    ).exists()
                
                # Si no tiene acceso, lanzar error 403
                if not has_access:
                    from django.http import Http404
                    raise Http404("Orden de trabajo no encontrada o acceso denegado.")
        
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Cargar las tareas asociadas
        if WorkLog:
            # Buscar WorkLog que tengan el número de esta orden de trabajo
            # Verificar tanto work_order (CharField) como work_order_ref (ForeignKey)
            context["tareas"] = WorkLog.objects.filter(
                Q(work_order=self.object.numero) | 
                Q(work_order_ref=self.object)
            )
        else:
            context["tareas"] = []
        
        # Calcular el total de horas
        tareas = context.get("tareas")
        total_horas = 0

        if tareas:
            for t in tareas:
                # Usar el método duration() del modelo WorkLog
                try:
                    horas = t.duration()
                    total_horas += horas
                except (AttributeError, TypeError, ValueError):
                    # Fallback: intentar calcular manualmente
                    try:
                        if hasattr(t, 'start') and hasattr(t, 'end') and t.start and t.end:
                            duration = (t.end - t.start).total_seconds() / 3600
                            total_horas += round(duration, 2)
                    except:
                        pass

        context["total_horas"] = round(total_horas, 2)
        return context
    
    

class OrdenCreateView(LoginRequiredMixin, NotTecnicoRequiredMixin, CreateView):
    model = WorkOrder
    form_class = WorkOrderForm
    template_name = "work_order/form.html"
    success_url = reverse_lazy("work_order:list")

    def form_valid(self, form):
        form.instance.creado_por = self.request.user
        return super().form_valid(form)

class OrdenUpdateView(LoginRequiredMixin, NotTecnicoRequiredMixin, UpdateView):
    model = WorkOrder
    form_class = WorkOrderForm
    template_name = "work_order/form.html"
    success_url = reverse_lazy("work_order:list")

from rest_framework import viewsets, permissions
from .serializers import WorkOrderSerializer

class NotTecnicoWritePermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        if not request.user or not request.user.is_authenticated:
            return False
        return getattr(request.user, 'user_type', '') != 'tecnico'

class WorkOrderViewSet(viewsets.ModelViewSet):
    queryset = WorkOrder.objects.all().select_related("cliente", "asignado_a")
    serializer_class = WorkOrderSerializer
    permission_classes = [permissions.IsAuthenticated & NotTecnicoWritePermission]



