from django.urls import path
from .views import WorkLogCreateView, WorkLogListView
from .views import WorkLogCreateView, WorkLogListView, export_worklogs_excel

urlpatterns = [
    path('', WorkLogListView.as_view(), name='worklog-list'),
    path('nuevo/', WorkLogCreateView.as_view(), name='worklog-create'),
    path('exportar/', export_worklogs_excel, name='worklog-export'),
]
