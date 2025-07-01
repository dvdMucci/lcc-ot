from django.urls import path
from .views import WorkLogCreateView, WorkLogListView

urlpatterns = [
    path('', WorkLogListView.as_view(), name='worklog-list'),
    path('nuevo/', WorkLogCreateView.as_view(), name='worklog-create'),
]
