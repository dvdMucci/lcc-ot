from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.db.models import Prefetch, Q
from .models import WorkOrder
from .forms import WorkOrderForm
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
        queryset = super().get_queryset()
        
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
        
        return queryset

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



