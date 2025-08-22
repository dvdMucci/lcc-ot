from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.db.models import Prefetch
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
        ctx = super().get_context_data(**kwargs)
        if WorkLog:
            # Buscar WorkLog que tengan el número de esta orden de trabajo
            ctx["tareas"] = WorkLog.objects.filter(work_order=self.object.numero)
        else:
            ctx["tareas"] = []
        return ctx

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