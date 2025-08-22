from django.core.management.base import BaseCommand
from work_order.models import WorkOrder
try:
    from worklog.models import WorkLog
except Exception:
    WorkLog = None

class Command(BaseCommand):
    help = "Vincula WorkLog.work_order (texto) con WorkOrder por numero"

    def handle(self, *args, **kwargs):
        if not WorkLog:
            self.stdout.write(self.style.WARNING("WorkLog no disponible. Saltando backfill."))
            return
        count = 0
        qs = WorkLog.objects.exclude(work_order__isnull=True).exclude(work_order__exact="")
        for wl in qs.iterator():
            wo = WorkOrder.objects.filter(numero=wl.work_order).first()
            if wo and getattr(wl, "work_order_ref_id", None) != wo.id:
                wl.work_order_ref = wo
                wl.save(update_fields=["work_order_ref"])
                count += 1
        self.stdout.write(self.style.SUCCESS(f"Vinculados {count} WorkLog→WorkOrder"))
