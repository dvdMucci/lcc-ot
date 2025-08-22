from rest_framework import serializers
from .models import WorkOrder, WorkOrderAttachment


class WorkOrderAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkOrderAttachment
        fields = ['id', 'archivo', 'descripcion', 'subido_por', 'subido_en']


class WorkOrderSerializer(serializers.ModelSerializer):
    adjuntos = WorkOrderAttachmentSerializer(many=True, read_only=True)
    cliente_nombre = serializers.CharField(source='cliente.razon_social', read_only=True)
    asignado_a_nombre = serializers.CharField(source='asignado_a.get_full_name', read_only=True)
    creado_por_nombre = serializers.CharField(source='creado_por.get_full_name', read_only=True)
    
    class Meta:
        model = WorkOrder
        fields = [
            'id', 'numero', 'cliente', 'cliente_nombre', 'titulo', 'descripcion',
            'prioridad', 'estado', 'asignado_a', 'asignado_a_nombre',
            'fecha_creacion', 'fecha_limite', 'fecha_cierre',
            'creado_por', 'creado_por_nombre', 'actualizado_por', 'actualizado_en',
            'adjuntos'
        ]
        read_only_fields = [
            'id', 'numero', 'fecha_creacion', 'fecha_cierre',
            'creado_por', 'actualizado_por', 'actualizado_en'
        ]
    
    def create(self, validated_data):
        # Asignar el usuario actual como creador
        validated_data['creado_por'] = self.context['request'].user
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        # Asignar el usuario actual como actualizador
        validated_data['actualizado_por'] = self.context['request'].user
        return super().update(instance, validated_data)
