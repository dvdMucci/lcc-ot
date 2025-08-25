from django.urls import path
from .views import (
    WorkLogCreateView, WorkLogListView, WorkLogEditView, 
    WorkLogDeleteView, export_worklogs_excel, worklog_detail, serve_audio_file
)

urlpatterns = [
    path('', WorkLogListView.as_view(), name='worklog-list'),
    path('nuevo/', WorkLogCreateView.as_view(), name='worklog-create'),
    path('<int:pk>/', worklog_detail, name='worklog-detail'),
    path('<int:pk>/editar/', WorkLogEditView.as_view(), name='worklog-edit'),
    path('<int:pk>/eliminar/', WorkLogDeleteView.as_view(), name='worklog-delete'),
    path('exportar/', export_worklogs_excel, name='worklog-export'),
    path('<int:worklog_id>/audio/', serve_audio_file, name='worklog-audio'),
]
