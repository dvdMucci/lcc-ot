from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from .models import WorkLog, WorkLogHistory
from .forms import WorkLogForm, WorkLogFilterForm, WorkLogEditForm
from datetime import timedelta, date
from openpyxl import Workbook
import json


class IsStaffMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser


class CanEditWorkLogMixin(UserPassesTestMixin):
    """Mixin para verificar si el usuario puede editar una tarea específica"""
    def test_func(self):
        worklog = self.get_object()
        user = self.request.user
        
        # Administradores y supervisores pueden editar cualquier tarea
        if user.is_staff or user.user_type in ['admin', 'supervisor']:
            return True
        
        # El técnico que creó la tarea puede editarla
        if worklog.created_by == user:
            return True
        
        # El técnico asignado puede editarla
        if worklog.technician == user:
            return True
        
        return False


class WorkLogCreateView(LoginRequiredMixin, CreateView):
    model = WorkLog
    form_class = WorkLogForm
    template_name = 'worklog/worklog_form.html'
    success_url = reverse_lazy('worklog-list')

    def form_valid(self, form):
        form.instance.technician = self.request.user
        form.instance.created_by = self.request.user
        response = super().form_valid(form)

        # Crear copia para colaborador, si existe
        collaborator = form.cleaned_data.get('collaborator')
        if collaborator:
            collaborator_worklog = WorkLog.objects.create(
                technician=collaborator,
                collaborator=self.request.user,
                start=form.instance.start,
                end=form.instance.end,
                task_type=form.instance.task_type,
                other_task_type=form.instance.other_task_type,
                description=form.instance.description,
                work_order=form.instance.work_order,
                status=form.instance.status,
                created_by=self.request.user,
            )
            
            # Registrar en el historial
            WorkLogHistory.objects.create(
                worklog=collaborator_worklog,
                user=self.request.user,
                action='created',
                ip_address=self.get_client_ip(),
                user_agent=self.request.META.get('HTTP_USER_AGENT', '')
            )

        # Registrar en el historial
        WorkLogHistory.objects.create(
            worklog=form.instance,
            user=self.request.user,
            action='created',
            ip_address=self.get_client_ip(),
            user_agent=self.request.META.get('HTTP_USER_AGENT', '')
        )

        messages.success(self.request, 'Tarea creada exitosamente.')
        return response

    def get_client_ip(self):
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip


class WorkLogEditView(LoginRequiredMixin, CanEditWorkLogMixin, UpdateView):
    model = WorkLog
    form_class = WorkLogEditForm
    template_name = 'worklog/worklog_edit.html'
    success_url = reverse_lazy('worklog-list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        # Guardar valores anteriores para el historial
        old_instance = WorkLog.objects.get(pk=self.object.pk)
        
        # Actualizar campos de auditoría
        form.instance.updated_by = self.request.user
        
        response = super().form_valid(form)
        
        # Registrar cambios en el historial
        self.record_changes(old_instance, form.instance)
        
        messages.success(self.request, 'Tarea actualizada exitosamente.')
        return response

    def record_changes(self, old_instance, new_instance):
        """Registra los cambios en el historial"""
        fields_to_track = ['start', 'end', 'task_type', 'other_task_type', 'description', 'work_order', 'status']
        
        for field in fields_to_track:
            old_value = getattr(old_instance, field)
            new_value = getattr(new_instance, field)
            
            if old_value != new_value:
                WorkLogHistory.objects.create(
                    worklog=new_instance,
                    user=self.request.user,
                    action='updated',
                    field_name=field,
                    old_value=str(old_value) if old_value is not None else '',
                    new_value=str(new_value) if new_value is not None else '',
                    ip_address=self.get_client_ip(),
                    user_agent=self.request.META.get('HTTP_USER_AGENT', '')
                )

    def get_client_ip(self):
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip


class WorkLogDeleteView(LoginRequiredMixin, IsStaffMixin, DeleteView):
    model = WorkLog
    template_name = 'worklog/worklog_confirm_delete.html'
    success_url = reverse_lazy('worklog-list')

    def delete(self, request, *args, **kwargs):
        worklog = self.get_object()
        
        # Registrar eliminación en el historial
        WorkLogHistory.objects.create(
            worklog=worklog,
            user=request.user,
            action='deleted',
            ip_address=self.get_client_ip(),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        messages.success(request, 'Tarea eliminada exitosamente.')
        return super().delete(request, *args, **kwargs)

    def get_client_ip(self):
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip


class WorkLogListView(LoginRequiredMixin, ListView):
    model = WorkLog
    template_name = 'worklog/worklog_list.html'
    context_object_name = 'worklogs'

    def get_queryset(self):
        user = self.request.user
        queryset = WorkLog.objects.all() if user.is_staff or user.user_type in ['admin', 'supervisor'] else WorkLog.objects.filter(technician=user)

        form = WorkLogFilterForm(self.request.GET or None)

        if form.is_valid():
            technician = form.cleaned_data.get('technician')
            task_type = form.cleaned_data.get('task_type')
            status = form.cleaned_data.get('status')
            date_exact = form.cleaned_data.get('date')
            week = form.cleaned_data.get('week')
            month = form.cleaned_data.get('month')
            start_date = form.cleaned_data.get('start_date')
            end_date = form.cleaned_data.get('end_date')

            if technician:
                queryset = queryset.filter(technician=technician)
            if task_type:
                queryset = queryset.filter(task_type=task_type)
            if status:
                queryset = queryset.filter(status=status)
            if date_exact:
                queryset = queryset.filter(start__date=date_exact)
            if week:
                queryset = queryset.filter(start__date__range=(week, week + timedelta(days=6)))
            if month:
                queryset = queryset.filter(start__year=month.year, start__month=month.month)
            if start_date and end_date:
                queryset = queryset.filter(start__date__range=(start_date, end_date))

        self.filter_form = form
        self.filtered_queryset = queryset.order_by('-start')
        return self.filtered_queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = self.filter_form
        total_horas = sum([log.duration() for log in self.filtered_queryset])
        context['total_horas'] = round(total_horas, 2)
        return context


def export_worklogs_excel(request):
    user = request.user

    if not user.is_authenticated:
        return HttpResponse(status=403)

    if not (user.is_staff or user.user_type in ['admin', 'supervisor', 'tecnico']):
        return HttpResponse(status=403)

    # Base queryset
    logs = WorkLog.objects.all() if user.is_staff or user.user_type in ['admin', 'supervisor'] else WorkLog.objects.filter(technician=user)

    # Aplicar filtros si vienen en la URL
    form = WorkLogFilterForm(request.GET or None)
    if form.is_valid():
        technician = form.cleaned_data.get('technician')
        task_type = form.cleaned_data.get('task_type')
        status = form.cleaned_data.get('status')
        date_exact = form.cleaned_data.get('date')
        week = form.cleaned_data.get('week')
        month = form.cleaned_data.get('month')
        start_date = form.cleaned_data.get('start_date')
        end_date = form.cleaned_data.get('end_date')

        if technician:
            logs = logs.filter(technician=technician)
        if task_type:
            logs = logs.filter(task_type=task_type)
        if status:
            logs = logs.filter(status=status)
        if date_exact:
            logs = logs.filter(start__date=date_exact)
        if week:
            logs = logs.filter(start__date__range=(week, week + timedelta(days=6)))
        if month:
            logs = logs.filter(start__year=month.year, start__month=month.month)
        if start_date and end_date:
            logs = logs.filter(start__date__range=(start_date, end_date))

    logs = logs.order_by('-start')

    # Crear archivo Excel
    wb = Workbook()
    ws = wb.active
    ws.title = "Horas Técnicas"

    ws.append([
        "Técnico", "Colaborador", "Inicio", "Fin", "Duración (hs)",
        "Tipo", "Otro tipo", "Descripción", "Orden de trabajo", "Estado"
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
            log.work_order or '',
            log.get_status_display()
        ])

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = f"horas_tecnicos_{date.today()}.xlsx"
    response['Content-Disposition'] = f'attachment; filename={filename}'

    wb.save(response)
    return response


@login_required
def worklog_detail(request, pk):
    """Vista para mostrar detalles de una tarea"""
    worklog = get_object_or_404(WorkLog, pk=pk)
    
    # Verificar permisos
    user = request.user
    if not (user.is_staff or user.user_type in ['admin', 'supervisor'] or 
            worklog.created_by == user or worklog.technician == user):
        messages.error(request, 'No tienes permisos para ver esta tarea.')
        return redirect('worklog-list')
    
    context = {
        'worklog': worklog,
        'history': worklog.history.all()[:10]  # Últimos 10 cambios
    }
    return render(request, 'worklog/worklog_detail.html', context)
