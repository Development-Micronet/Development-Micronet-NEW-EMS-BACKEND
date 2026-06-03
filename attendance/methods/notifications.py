from django.urls import reverse

from attendance.methods.utils import get_employee_last_name
from notifications.helpers import send_admin_notification, send_employee_notification


def get_attendance_request_notification_actor(user):
    return getattr(user, "employee_get", None) or user


def _attendance_request_redirect(attendance):
    return reverse("request-attendance-view") + f"?id={attendance.id}"


def _attendance_request_api_redirect(attendance):
    return f"/api/attendance/attendance-request/{attendance.id}"


def notify_attendance_request_created(actor, attendance):
    employee = attendance.employee_id
    user_last_name = get_employee_last_name(attendance)

    if attendance.request_type == "create_request":
        verb = f"Attendance regularization requested for {attendance.attendance_date}"
        verb_ar = (
            f"ØªÙ… Ø¥Ù†Ø´Ø§Ø¡ Ø·Ù„Ø¨ Ø­Ø¶ÙˆØ± Ù„Ù€ {employee.employee_first_name} "
            f"{user_last_name} ÙÙŠ {attendance.attendance_date}"
        )
        verb_de = (
            f"Die Anwesenheitsanfrage von {employee.employee_first_name} "
            f"{user_last_name} fur den {attendance.attendance_date} wurde erstellt"
        )
        verb_es = (
            f"Se ha creado la solicitud de asistencia de "
            f"{employee.employee_first_name} {user_last_name} para el "
            f"{attendance.attendance_date}"
        )
        verb_fr = (
            f"La demande de presence de {employee.employee_first_name} "
            f"{user_last_name} pour le {attendance.attendance_date} a ete creee"
        )
    else:
        verb = f"Attendance regularization requested for {attendance.attendance_date}"
        verb_ar = (
            f"ØªÙ… Ø¥Ù†Ø´Ø§Ø¡ Ø·Ù„Ø¨ ØªØ­Ø¯ÙŠØ« Ø§Ù„Ø­Ø¶ÙˆØ± Ù„Ù€ {employee.employee_first_name} "
            f"{user_last_name} ÙÙŠ {attendance.attendance_date}"
        )
        verb_de = (
            f"Die Anfrage zur Aktualisierung der Anwesenheit von "
            f"{employee.employee_first_name} {user_last_name} fur den "
            f"{attendance.attendance_date} wurde erstellt"
        )
        verb_es = (
            f"Se ha creado la solicitud de actualizacion de asistencia de "
            f"{employee.employee_first_name} {user_last_name} para el "
            f"{attendance.attendance_date}"
        )
        verb_fr = (
            f"La demande de mise a jour de presence de "
            f"{employee.employee_first_name} {user_last_name} pour le "
            f"{attendance.attendance_date} a ete creee"
        )

    # NOTIFY
    send_admin_notification(
        actor,
        verb=verb,
        description=(
            f"{employee.employee_first_name} {user_last_name} requested attendance "
            f"regularization for {attendance.attendance_date}."
        ),
        target=attendance,
        level="info",
        verb_ar=verb_ar,
        verb_de=verb_de,
        verb_es=verb_es,
        verb_fr=verb_fr,
        redirect=_attendance_request_redirect(attendance),
        api_redirect=_attendance_request_api_redirect(attendance),
        icon="checkmark-circle-outline",
    )


def notify_attendance_request_approved(actor, attendance):
    employee = attendance.employee_id
    redirect = _attendance_request_redirect(attendance)
    api_redirect = _attendance_request_api_redirect(attendance)

    # NOTIFY
    send_employee_notification(
        actor,
        employee,
        verb=f"Your attendance request for {attendance.attendance_date} is validated",
        description=(
            f"Your attendance regularization request for {attendance.attendance_date} "
            "has been approved."
        ),
        target=attendance,
        level="success",
        verb_ar=f"ØªÙ… Ø§Ù„ØªØ­Ù‚Ù‚ Ù…Ù† Ø·Ù„Ø¨ Ø­Ø¶ÙˆØ±Ùƒ ÙÙŠ ØªØ§Ø±ÙŠØ® {attendance.attendance_date}",
        verb_de=(
            f"Ihr Anwesenheitsantrag fur das Datum {attendance.attendance_date} "
            "wurde bestatigt"
        ),
        verb_es=(
            f"Se ha validado su solicitud de asistencia para la fecha "
            f"{attendance.attendance_date}"
        ),
        verb_fr=(
            f"Votre demande de presence pour la date {attendance.attendance_date} "
            "est validee"
        ),
        redirect=redirect,
        api_redirect=api_redirect,
        icon="checkmark-circle-outline",
    )

    user_last_name = get_employee_last_name(attendance)

    # NOTIFY
    send_admin_notification(
        actor,
        verb=(
            f"{employee.employee_first_name} {user_last_name}'s attendance request "
            f"for {attendance.attendance_date} is validated"
        ),
        description=(
            f"Attendance regularization for {employee.employee_first_name} "
            f"{user_last_name} on {attendance.attendance_date} has been approved."
        ),
        target=attendance,
        level="success",
        verb_ar=(
            f"ØªÙ… Ø§Ù„ØªØ­Ù‚Ù‚ Ù…Ù† Ø·Ù„Ø¨ Ø§Ù„Ø­Ø¶ÙˆØ± Ù„Ù€ {employee.employee_first_name} "
            f"{user_last_name} ÙÙŠ {attendance.attendance_date}"
        ),
        verb_de=(
            f"Die Anwesenheitsanfrage von {employee.employee_first_name} "
            f"{user_last_name} fur den {attendance.attendance_date} wurde validiert"
        ),
        verb_es=(
            f"Se ha validado la solicitud de asistencia de "
            f"{employee.employee_first_name} {user_last_name} para el "
            f"{attendance.attendance_date}"
        ),
        verb_fr=(
            f"La demande de presence de {employee.employee_first_name} "
            f"{user_last_name} pour le {attendance.attendance_date} a ete validee"
        ),
        redirect=redirect,
        api_redirect=api_redirect,
        icon="checkmark-circle-outline",
    )


def notify_attendance_request_rejected(actor, attendance):
    employee = attendance.employee_id

    # NOTIFY
    send_employee_notification(
        actor,
        employee,
        verb=f"Your attendance request for {attendance.attendance_date} is rejected",
        description=(
            f"Your attendance regularization request for {attendance.attendance_date} "
            "has been rejected."
        ),
        target=attendance,
        level="error",
        verb_ar=f"ØªÙ… Ø±ÙØ¶ Ø·Ù„Ø¨Ùƒ Ù„Ù„Ø­Ø¶ÙˆØ± ÙÙŠ ØªØ§Ø±ÙŠØ® {attendance.attendance_date}",
        verb_de=(
            f"Ihre Anwesenheitsanfrage fur {attendance.attendance_date} "
            "wurde abgelehnt"
        ),
        verb_es=(
            f"Tu solicitud de asistencia para el {attendance.attendance_date} "
            "ha sido rechazada"
        ),
        verb_fr=(
            f"Votre demande de presence pour le {attendance.attendance_date} "
            "est rejetee"
        ),
        redirect=_attendance_request_redirect(attendance),
        api_redirect=_attendance_request_api_redirect(attendance),
        icon="close-circle-outline",
    )
