from contextlib import suppress

from employee.models import Employee
from notifications.signals import notify


def get_performance_notification_actor(user):
    return getattr(user, "employee_get", None) or user


def _user_for_employee(employee):
    return getattr(employee, "employee_user_id", None)


def _actor_user(actor):
    if actor is None:
        return None
    return getattr(actor, "employee_user_id", None) or actor


def _normalize_recipients(recipients, exclude_user=None):
    unique_recipients = []
    seen_user_ids = set()
    excluded_user_id = getattr(exclude_user, "id", None)

    for recipient in recipients:
        if recipient is None or not getattr(recipient, "pk", None):
            continue
        if excluded_user_id is not None and recipient.id == excluded_user_id:
            continue
        if recipient.id in seen_user_ids:
            continue
        seen_user_ids.add(recipient.id)
        unique_recipients.append(recipient)

    return unique_recipients


def _send_performance_notification(actor, recipients, **kwargs):
    recipients = _normalize_recipients(recipients, exclude_user=_actor_user(actor))
    if not recipients:
        return

    recipient = recipients[0] if len(recipients) == 1 else recipients
    with suppress(Exception):
        notify.send(actor, recipient=recipient, **kwargs)


def _performance_admin_users():
    return [
        employee.employee_user_id
        for employee in Employee.objects.filter(role="admin").select_related(
            "employee_user_id"
        )
        if employee.employee_user_id_id
    ]


def notify_objective_created(actor, objective):
    objective_url = f"/api/performance/objectives/{objective.id}/"
    employee_name = objective.employee.get_full_name()

    _send_performance_notification(
        actor,
        [_user_for_employee(objective.employee)],
        verb=f"A performance objective '{objective.title}' was assigned to you",
        icon="flag-outline",
        api_redirect=objective_url,
    )
    _send_performance_notification(
        actor,
        [_user_for_employee(manager) for manager in objective.managers.all()],
        verb=f"You were assigned to manage the objective '{objective.title}' for {employee_name}",
        icon="briefcase-outline",
        api_redirect=objective_url,
    )


def notify_objective_updated(actor, objective):
    objective_url = f"/api/performance/objectives/{objective.id}/"
    employee_name = objective.employee.get_full_name()

    _send_performance_notification(
        actor,
        [_user_for_employee(objective.employee)],
        verb=f"Your performance objective '{objective.title}' was updated",
        icon="create-outline",
        api_redirect=objective_url,
    )
    _send_performance_notification(
        actor,
        [_user_for_employee(manager) for manager in objective.managers.all()],
        verb=f"The objective '{objective.title}' for {employee_name} was updated",
        icon="create-outline",
        api_redirect=objective_url,
    )


def notify_meeting_created(actor, meeting):
    meeting_url = f"/api/performance/meetings/{meeting.id}/"

    _send_performance_notification(
        actor,
        [_user_for_employee(employee) for employee in meeting.employees.all()],
        verb=f"A performance meeting '{meeting.title}' is scheduled for {meeting.date}",
        icon="calendar-outline",
        api_redirect=meeting_url,
    )
    _send_performance_notification(
        actor,
        [_user_for_employee(employee) for employee in meeting.answerable_employees.all()],
        verb=f"You were marked as answerable for the performance meeting '{meeting.title}' on {meeting.date}",
        icon="help-circle-outline",
        api_redirect=meeting_url,
    )
    _send_performance_notification(
        actor,
        [_user_for_employee(meeting.manager)],
        verb=f"You were assigned as manager for the performance meeting '{meeting.title}' on {meeting.date}",
        icon="people-outline",
        api_redirect=meeting_url,
    )


def notify_meeting_updated(actor, meeting):
    meeting_url = f"/api/performance/meetings/{meeting.id}/"
    participant_users = [_user_for_employee(employee) for employee in meeting.employees.all()]
    participant_users.extend(
        _user_for_employee(employee) for employee in meeting.answerable_employees.all()
    )
    participant_users.append(_user_for_employee(meeting.manager))

    _send_performance_notification(
        actor,
        participant_users,
        verb=f"The performance meeting '{meeting.title}' scheduled for {meeting.date} was updated",
        icon="create-outline",
        api_redirect=meeting_url,
    )


def notify_feedback_created(actor, feedback):
    feedback_url = f"/api/performance/feedbacks/{feedback.id}/"

    _send_performance_notification(
        actor,
        [_user_for_employee(feedback.employee)],
        verb=f"A performance feedback '{feedback.title}' was assigned to you",
        icon="chatbox-ellipses-outline",
        api_redirect=feedback_url,
    )


def notify_feedback_updated(actor, feedback):
    feedback_url = f"/api/performance/feedbacks/{feedback.id}/"

    _send_performance_notification(
        actor,
        [_user_for_employee(feedback.employee)],
        verb=f"Your performance feedback '{feedback.title}' was updated",
        icon="create-outline",
        api_redirect=feedback_url,
    )


def notify_feedback_submitted(actor, feedback):
    feedback_url = f"/api/performance/feedback/admin/{feedback.id}/"

    _send_performance_notification(
        actor,
        _performance_admin_users(),
        verb=f"{feedback.employee.get_full_name()} submitted the performance feedback '{feedback.title}'",
        icon="checkmark-done-outline",
        api_redirect=feedback_url,
    )


def notify_bonus_created(actor, bonus):
    bonus_url = f"/api/performance/bonus/{bonus.id}/"

    _send_performance_notification(
        actor,
        [_user_for_employee(bonus.employee)],
        verb=(
            f"You received {bonus.bonus_points} bonus points for "
            f"{bonus.get_bonus_category_display().lower()}"
        ),
        icon="trophy-outline",
        api_redirect=bonus_url,
    )


def notify_bonus_updated(actor, bonus):
    bonus_url = f"/api/performance/bonus/{bonus.id}/"

    _send_performance_notification(
        actor,
        [_user_for_employee(bonus.employee)],
        verb=(
            f"Your bonus record for {bonus.get_bonus_category_display().lower()} "
            f"was updated"
        ),
        icon="create-outline",
        api_redirect=bonus_url,
    )
