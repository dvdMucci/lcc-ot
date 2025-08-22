from django.contrib import admin
from .models import WorkLog, WorkLogHistory

@admin.register(WorkLog)
class WorkLogAdmin(admin.ModelAdmin):
    list_display = ['technician', 'task_type', 'start', 'end', 'duration', 'status', 'created_by', 'created_at']
    list_filter = ['task_type', 'status', 'start', 'technician', 'created_by']
    search_fields = ['description', 'technician__username', 'technician__first_name', 'technician__last_name']
    date_hierarchy = 'start'
    readonly_fields = ['created_by', 'created_at', 'updated_by', 'updated_at', 'duration']
    
    fieldsets = (
        ('Información de la Tarea', {
            'fields': ('technician', 'collaborator', 'task_type', 'other_task_type', 'status')
        }),
        ('Horarios', {
            'fields': ('start', 'end')
        }),
        ('Detalles', {
            'fields': ('description', 'work_order', 'audio_file')
        }),
        ('Auditoría', {
            'fields': ('created_by', 'created_at', 'updated_by', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # Si es una nueva tarea
            obj.created_by = request.user
        else:  # Si se está editando
            obj.updated_by = request.user
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        elif request.user.user_type in ['admin', 'supervisor']:
            return qs
        else:
            return qs.filter(technician=request.user)


@admin.register(WorkLogHistory)
class WorkLogHistoryAdmin(admin.ModelAdmin):
    list_display = ['worklog', 'user', 'action', 'field_name', 'timestamp']
    list_filter = ['action', 'timestamp', 'user']
    search_fields = ['worklog__description', 'user__username', 'field_name']
    date_hierarchy = 'timestamp'
    readonly_fields = ['worklog', 'user', 'action', 'field_name', 'old_value', 'new_value', 'timestamp', 'ip_address', 'user_agent']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
