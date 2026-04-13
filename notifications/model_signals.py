from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from notifications.models import Notification
from notifications.realtime import (
    schedule_notification_snapshot_broadcast,
    serialize_notification,
)


@receiver(post_save, sender=Notification)
def push_notification_update(sender, instance, created, **kwargs):
    user = instance.recipient
    if user is None:
        return

    event_type = "notification_created" if created else "notification_updated"
    schedule_notification_snapshot_broadcast(
        user.id,
        event={
            "type": event_type,
            "notification": serialize_notification(instance),
        },
    )


@receiver(post_delete, sender=Notification)
def push_notification_delete(sender, instance, **kwargs):
    user = instance.recipient
    if user is None:
        return

    schedule_notification_snapshot_broadcast(
        user.id,
        event={
            "type": "notification_deleted",
            "notification_id": instance.id,
        },
    )
