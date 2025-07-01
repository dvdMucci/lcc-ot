from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, CreateView
from django.urls import reverse_lazy
from .models import WorkLog
from .forms import WorkLogForm
import datetime
from django.http import HttpResponse
from openpyxl import Workbook

# al final de views.py
def export_worklogs_excel(request):
    user = request.user

    if not user.is_authenticated:
        return HttpResponse(status=403)

    if not (user.is_staff or user.user_type in ['admin', 'supervisor', 'tecnico']):
        return HttpResponse(status=403)

    # Filtrar datos
    if user.is_staff or user.user_type in ['admin', 'supervisor']:
        logs = WorkLog.objects.all().order_by('-start')
    else:
        logs = WorkLog.objects.filter(technician=user).order_by('-start')

    # Crear workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Horas Técnicas"

    # Encabezados
    ws.append([
        "Técnico", "Colaborador", "Inicio", "Fin", "Duración (hs)", 
        "Tipo", "Otro tipo", "Descripción", "Orden de trabajo"
    ])

    for log in logs:
        ws.append([
            str(log.technician),
            str(log.collaborator) if log.collaborator else '',
            log.start.strftime("%Y-%m-%d %H:%M"),
            log.end.strftime("%Y-%m-%d %H:%M"),
            log.duration(),
            log.task_type,
            log.other_task_type or '',
            log.description,
            log.work_order or ''
        ])

    # Preparar respuesta
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = f"horas_tecnicos_{datetime.date.today()}.xlsx"
    response['Content-Disposition'] = f'attachment; filename={filename}'

    wb.save(response)
    return response


class IsStaffMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser

class WorkLogCreateView(LoginRequiredMixin, CreateView):
    model = WorkLog
    form_class = WorkLogForm
    template_name = 'worklog/worklog_form.html'
    success_url = reverse_lazy('worklog-list')

    def form_valid(self, form):
        form.instance.technician = self.request.user
        response = super().form_valid(form)

        # Crear copia para colaborador, si existe
        collaborator = form.cleaned_data.get('collaborator')
        if collaborator:
            # Clonamos los datos para el colaborador
            WorkLog.objects.create(
                technician=collaborator,
                collaborator=self.request.user,  # opcional: registrar quién lo cargó
                start=form.instance.start,
                end=form.instance.end,
                task_type=form.instance.task_type,
                other_task_type=form.instance.other_task_type,
                description=form.instance.description,
                work_order=form.instance.work_order,
            )

        return response


class WorkLogListView(LoginRequiredMixin, ListView):
    model = WorkLog
    template_name = 'worklog/worklog_list.html'
    context_object_name = 'worklogs'

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return WorkLog.objects.all().order_by('-start')
        return WorkLog.objects.filter(technician=user).order_by('-start')
    
def export_worklogs_excel(request):
    user = request.user

    if not user.is_authenticated:
        return HttpResponse(status=403)

    if not (user.is_staff or user.user_type in ['admin', 'supervisor', 'tecnico']):
        return HttpResponse(status=403)

    # Filtrar datos
    if user.is_staff or user.user_type in ['admin', 'supervisor']:
        logs = WorkLog.objects.all().order_by('-start')
    else:
        logs = WorkLog.objects.filter(technician=user).order_by('-start')

    # Crear workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Horas Técnicas"

    # Encabezados
    ws.append([
        "Técnico", "Colaborador", "Inicio", "Fin", "Duración (hs)", 
        "Tipo", "Otro tipo", "Descripción", "Orden de trabajo"
    ])

    for log in logs:
        ws.append([
            str(log.technician),
            str(log.collaborator) if log.collaborator else '',
            log.start.strftime("%Y-%m-%d %H:%M"),
            log.end.strftime("%Y-%m-%d %H:%M"),
            log.duration(),
            log.task_type,
            log.other_task_type or '',
            log.description,
            log.work_order or ''
        ])

    # Preparar respuesta
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = f"horas_tecnicos_{datetime.date.today()}.xlsx"
    response['Content-Disposition'] = f'attachment; filename={filename}'

    wb.save(response)
    return response