from django.urls import path, include
from .views import (
    OrdenListView, OrdenDetailView, OrdenCreateView, OrdenUpdateView,
    WorkOrderViewSet,
)
from rest_framework.routers import DefaultRouter

app_name = "work_order"

router = DefaultRouter()
router.register(r"workorders", WorkOrderViewSet, basename="workorder")

urlpatterns = [
    path("", OrdenListView.as_view(), name="list"),
    path("crear/", OrdenCreateView.as_view(), name="create"),
    path("<int:pk>/", OrdenDetailView.as_view(), name="detail"),
    path("<int:pk>/editar/", OrdenUpdateView.as_view(), name="update"),
    path("api/", include(router.urls)),
]
