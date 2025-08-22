from django.contrib import admin
from .models import WorkOrder, WorkOrderAttachment

@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin):
    list_display = ("numero", "cliente", "titulo", "prioridad", "estado", "asignado_a", "fecha_creacion")
    list_filter = ("estado", "prioridad", "cliente")
    search_fields = ("numero", "titulo", "descripcion", "cliente__razon_social")
    readonly_fields = ("fecha_creacion", "actualizado_en")

@admin.register(WorkOrderAttachment)
class WorkOrderAttachmentAdmin(admin.ModelAdmin):
    list_display = ("orden", "descripcion", "subido_por", "subido_en")
