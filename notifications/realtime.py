from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from django.db import transaction
from django.forms.models import model_to_dict
from swapper import load_model

from notifications.settings import get_config
from notifications.utils import id2slug

Notification = load_model("notifications", "Notification")


def serialize_notification(notification):
    struct = model_to_dict(notification)
    struct["slug"] = id2slug(notification.id)
    struct["timestamp"] = (
        notification.timestamp.isoformat() if notification.timestamp else None
    )
    if notification.actor:
        struct["actor"] = str(notification.actor)
    if notification.target:
        struct["target"] = str(notification.target)
    if notification.action_object:
        struct["action_object"] = str(notification.action_object)
    if notification.data:
        struct["data"] = notification.data
    return struct


def get_notification_snapshot(user, limit=None):
    limit = limit or get_config()["NUM_TO_FETCH"]
    unread_notifications = list(user.notifications.unread()[:limit])
    all_notifications = list(user.notifications.all()[:limit])
    return {
        "type": "notification_snapshot",
        "unread_count": user.notifications.unread().count(),
        "all_count": user.notifications.count(),
        "unread_list": [
            serialize_notification(notification)
            for notification in unread_notifications
        ],
        "all_list": [
            serialize_notification(notification) for notification in all_notifications
        ],
    }


def notification_group_name(user_id):
    return f"notifications_user_{user_id}"


def _build_channel_event(payload):
    return {
        "type": "notification.snapshot",
        "payload": payload,
    }


def broadcast_notification_snapshot(user, event=None, limit=None):
    if user is None:
        return False

    channel_layer = get_channel_layer()
    if channel_layer is None:
        return False

    payload = get_notification_snapshot(user, limit=limit)
    if event is not None:
        payload["event"] = event

    async_to_sync(channel_layer.group_send)(
        notification_group_name(user.id),
        _build_channel_event(payload),
    )
    return True


def broadcast_notification_snapshot_by_user_id(user_id, event=None, limit=None):
    user = get_user_model().objects.filter(pk=user_id).first()
    if user is None:
        return False
    return broadcast_notification_snapshot(user, event=event, limit=limit)


def schedule_notification_snapshot_broadcast(user_or_user_id, event=None, limit=None):
    user_id = getattr(user_or_user_id, "id", user_or_user_id)
    if user_id is None:
        return False

    transaction.on_commit(
        lambda: broadcast_notification_snapshot_by_user_id(
            user_id,
            event=event,
            limit=limit,
        )
    )
    return True
