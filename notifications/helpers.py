from contextlib import suppress

from django.contrib.auth import get_user_model
from django.db.models import Q

from notifications.signals import notify


def get_notification_actor(actor):
    if actor is None:
        return None
    return getattr(actor, "employee_get", None) or actor


def get_admin_users():
    User = get_user_model()
    return (
        User.objects.filter(
            Q(is_superuser=True)
            | Q(is_staff=True)
            | Q(groups__name="Admin User")
            | Q(employee_get__role="admin")
        )
        .distinct()
        .only("id")
    )


def get_employee_user(employee):
    if employee is None:
        return None
    return getattr(employee, "employee_user_id", None)


def _normalize_recipients(recipients):
    if recipients is None:
        return []
    if hasattr(recipients, "all") and not hasattr(recipients, "pk"):
        recipients = list(recipients)
    elif not isinstance(recipients, (list, tuple, set)):
        recipients = [recipients]

    normalized = []
    seen = set()
    for recipient in recipients:
        if recipient is None:
            continue
        pk = getattr(recipient, "pk", None)
        if pk is None or pk in seen:
            continue
        seen.add(pk)
        normalized.append(recipient)
    return normalized


def send_notification(
    actor,
    recipients,
    *,
    verb,
    description,
    target,
    level,
    **kwargs,
):
    import logging
    from notifications.realtime import schedule_notification_snapshot_broadcast

    actor = get_notification_actor(actor)
    recipients = _normalize_recipients(recipients)
    if actor is None or not recipients:
        logging.warning("[NOTIFY-DEBUG] send_notification: No actor or recipients, skipping notification.")
        return

    try:
        notify.send(
            actor,
            recipient=recipients if len(recipients) > 1 else recipients[0],
            verb=verb,
            description=description,
            target=target,
            level=level,
            **kwargs,
        )
        logging.info(f"[NOTIFY-DEBUG] Notification sent: actor={actor}, recipients={recipients}, verb={verb}, target={target}, level={level}")
        # Schedule websocket notification for all recipients
        for user in recipients:
            schedule_notification_snapshot_broadcast(user)
            logging.info(f"[NOTIFY-DEBUG] Websocket notification scheduled for user {user}")
    except Exception as e:
        logging.error(f"[NOTIFY-DEBUG] send_notification error: {e}")


def send_admin_notification(
    actor,
    *,
    verb,
    description,
    target,
    level="info",
    **kwargs,
):
    admin_users = list(get_admin_users())
    import logging
    logging.warning(f"[NOTIFY-DEBUG] send_admin_notification: actor={actor}, admins={admin_users}, verb={verb}, target={target}, level={level}")
    if not admin_users:
        logging.error("[NOTIFY-DEBUG] No admin users found for notification!")
    send_notification(
        actor,
        admin_users,
        verb=verb,
        description=description,
        target=target,
        level=level,
        **kwargs,
    )


def send_employee_notification(
    actor,
    employee,
    *,
    verb,
    description,
    target,
    level="info",
    **kwargs,
):
    send_notification(
        actor,
        get_employee_user(employee),
        verb=verb,
        description=description,
        target=target,
        level=level,
        **kwargs,
    )
