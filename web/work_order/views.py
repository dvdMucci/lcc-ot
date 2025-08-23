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

class OrdenDetailView(LoginRequiredMixin, DetailView):
    model = WorkOrder
    template_name = "work_order/detail.html"

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
        return not request.user.groups.filter(name__iregex="^t[eé]cnico$").exists()

class WorkOrderViewSet(viewsets.ModelViewSet):
    queryset = WorkOrder.objects.all().select_related("cliente", "asignado_a")
    serializer_class = WorkOrderSerializer
    permission_classes = [permissions.IsAuthenticated & NotTecnicoWritePermission]



