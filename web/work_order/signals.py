from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import WorkOrder
import logging


@receiver(pre_save, sender=WorkOrder)
def work_order_pre_save(sender, instance, **kwargs):
    """
    Señal que se ejecuta antes de guardar una orden de trabajo
    """
    # Si el estado cambia a CERRADA, establecer fecha de cierre
    if instance.pk:  # Solo para actualizaciones
        try:
            old_instance = WorkOrder.objects.get(pk=instance.pk)
            if old_instance.estado != instance.estado and instance.estado == WorkOrder.Estado.CERRADA:
                instance.fecha_cierre = timezone.now()
        except WorkOrder.DoesNotExist:
            pass


@receiver(post_save, sender=WorkOrder)
def work_order_post_save(sender, instance, created, **kwargs):
    """
    Señal que se ejecuta después de guardar una orden de trabajo
    """
    if created:
        # Lógica para cuando se crea una nueva orden
        pass
    else:
        # Lógica para cuando se actualiza una orden existente
        pass


@receiver(post_save, sender=WorkOrder)
def notificar_bot(sender, instance: WorkOrder, created, **kwargs):
    try:
        if created:
            logging.getLogger(__name__).info(f"[BOT] Nueva OT {instance.numero}: {instance.titulo}")
        else:
            logging.getLogger(__name__).info(f"[BOT] OT actualizada {instance.numero} – estado={instance.estado}")
    except Exception as e:
        logging.getLogger(__name__).error(f"No se pudo notificar: {e}")
