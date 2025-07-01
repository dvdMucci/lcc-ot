from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, CreateView
from django.urls import reverse_lazy
from .models import WorkLog
from .forms import WorkLogForm

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
        return super().form_valid(form)

class WorkLogListView(LoginRequiredMixin, ListView):
    model = WorkLog
    template_name = 'worklog/worklog_list.html'
    context_object_name = 'worklogs'

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return WorkLog.objects.all().order_by('-start')
        return WorkLog.objects.filter(technician=user).order_by('-start')
