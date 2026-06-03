import re
from datetime import date, datetime, time

import pandas as pd
from django.contrib.auth.models import User
from django.db import transaction

from attendance.models import Attendance, BatchAttendance, WorkRecords
from base.models import (
    Company,
    Department,
    EmployeeShift,
    EmployeeShiftDay,
    EmployeeType,
    JobPosition,
    JobRole,
    WorkType,
)
from employee.models import Employee, EmployeeWorkInformation


EMPLOYEE_IMPORT_HEADERS = [
    "Badge ID",
    "First Name",
    "Last Name",
    "Email",
    "Phone",
    "Gender",
    "Department",
    "Job Position",
    "Job Role",
    "Shift",
    "Work Type",
    "Reporting Manager",
    "Employee Type",
    "Location",
    "Date Joining",
    "Basic Salary",
    "Salary Hour",
    "Contract End Date",
    "Company",
]

ATTENDANCE_IMPORT_HEADERS = [
    "Employee",
    "Attendance date",
    "Shift",
    "Work Type",
    "Attendance day",
    "Check-In Date",
    "Check-In",
    "Check-Out Date",
    "Check-Out",
    "Worked Hours",
    "Minimum hour",
    "Batch Attendance",
    "Overtime",
    "Overtime Approve",
    "Attendance Validate",
    "Overtime In Second",
    "is bulk request",
    "is holiday",
]

WORK_RECORD_ALLOWED_TYPES = {choice[0] for choice in WorkRecords.choices}


def read_import_file(uploaded_file):
    extension = uploaded_file.name.split(".")[-1].lower()
    if extension == "csv":
        return pd.read_csv(uploaded_file)
    if extension in ["xls", "xlsx"]:
        return pd.read_excel(uploaded_file)
    raise ValueError("Unsupported file format. Please upload a CSV or Excel file.")


def validate_headers(data_frame, required_headers):
    if data_frame.empty:
        return False, "The uploaded file is empty."
    missing = [header for header in required_headers if header not in data_frame.columns]
    if missing:
        return False, f"Missing required headers: {', '.join(missing)}"
    return True, ""


def normalize_text(value):
    if pd.isna(value) or value is None:
        return ""
    return str(value).strip()


def parse_bool(value, default=False):
    if pd.isna(value) or value is None or str(value).strip() == "":
        return default
    normalized = str(value).strip().lower()
    if normalized in {"yes", "true", "1", "y"}:
        return True
    if normalized in {"no", "false", "0", "n"}:
        return False
    return default


def parse_date_value(value):
    if pd.isna(value) or value is None or str(value).strip() == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    value = str(value).strip()
    for fmt in (
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%Y/%m/%d",
        "%d.%m.%Y",
    ):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    parsed = pd.to_datetime(value, errors="coerce", dayfirst=True)
    if pd.isna(parsed):
        raise ValueError(f"Invalid date value '{value}'")
    return parsed.date()


def parse_time_value(value):
    if pd.isna(value) or value is None or str(value).strip() == "":
        return None
    if isinstance(value, datetime):
        return value.time().replace(microsecond=0)
    if isinstance(value, time):
        return value.replace(microsecond=0)

    value = str(value).strip()
    for fmt in ("%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M:%S %p"):
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue

    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        raise ValueError(f"Invalid time value '{value}'")
    return parsed.time().replace(microsecond=0)


def parse_duration_value(value, default="00:00"):
    if pd.isna(value) or value is None or str(value).strip() == "":
        return default
    if isinstance(value, datetime):
        return value.strftime("%H:%M")
    if isinstance(value, time):
        return value.strftime("%H:%M")
    value = str(value).strip()
    if re.fullmatch(r"\d{1,3}:\d{2}(:\d{2})?", value):
        parts = value.split(":")
        return f"{int(parts[0]):02d}:{int(parts[1]):02d}"
    parsed = pd.to_timedelta(value, errors="coerce")
    if pd.isna(parsed):
        raise ValueError(f"Invalid duration value '{value}'")
    total_seconds = int(parsed.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return f"{hours:02d}:{minutes:02d}"


def parse_int_value(value, default=0):
    if pd.isna(value) or value is None or str(value).strip() == "":
        return default
    return int(float(value))


def parse_employee_badge(employee_label):
    match = re.search(r"\(([^()]+)\)\s*$", normalize_text(employee_label))
    return match.group(1).strip() if match else ""


def full_name(employee):
    return " ".join(
        part
        for part in [employee.employee_first_name, employee.employee_last_name]
        if part
    ).strip()


def resolve_employee(employee_value):
    employee_value = normalize_text(employee_value)
    badge_id = parse_employee_badge(employee_value) or employee_value
    employee = Employee.objects.filter(badge_id=badge_id).first()
    if employee:
        return employee
    return next(
        (
            emp
            for emp in Employee.objects.all()
            if full_name(emp).lower() == employee_value.lower()
        ),
        None,
    )


def resolve_user_by_email(email):
    email = normalize_text(email).lower()
    if not email:
        return None
    user = User.objects.filter(username=email).first()
    if user:
        if user.email != email:
            user.email = email
            user.save(update_fields=["email"])
        return user
    return User.objects.create_user(username=email, email=email, password=email)


def ensure_company(company_name):
    company_name = normalize_text(company_name)
    if not company_name:
        return None
    return Company.objects.filter(company=company_name).first()


def ensure_department(department_name, company=None):
    department_name = normalize_text(department_name)
    if not department_name:
        return None
    department = Department.objects.filter(department=department_name).first()
    if not department:
        department = Department.objects.create(department=department_name)
    if company:
        department.company_id.add(company)
    return department


def ensure_job_position(job_position_name, department=None, company=None):
    job_position_name = normalize_text(job_position_name)
    if not job_position_name or not department:
        return None
    job_position = JobPosition.objects.filter(
        job_position=job_position_name, department_id=department
    ).first()
    if not job_position:
        job_position = JobPosition.objects.create(
            job_position=job_position_name, department_id=department
        )
    if company:
        job_position.company_id.add(company)
    return job_position


def ensure_job_role(job_role_name, job_position=None, company=None):
    job_role_name = normalize_text(job_role_name)
    if not job_role_name or not job_position:
        return None
    job_role = JobRole.objects.filter(
        job_role=job_role_name, job_position_id=job_position
    ).first()
    if not job_role:
        job_role = JobRole.objects.create(
            job_role=job_role_name, job_position_id=job_position
        )
    if company:
        job_role.company_id.add(company)
    return job_role


def ensure_work_type(work_type_name, company=None):
    work_type_name = normalize_text(work_type_name)
    if not work_type_name:
        return None
    work_type = WorkType.objects.filter(work_type=work_type_name).first()
    if not work_type:
        work_type = WorkType.objects.create(work_type=work_type_name)
    if company:
        work_type.company_id.add(company)
    return work_type


def ensure_shift(shift_name, company=None):
    shift_name = normalize_text(shift_name)
    if not shift_name:
        return None
    shift = EmployeeShift.objects.filter(employee_shift=shift_name).first()
    if not shift:
        shift = EmployeeShift.objects.create(employee_shift=shift_name)
    if company:
        shift.company_id.add(company)
    return shift


def ensure_employee_type(employee_type_name):
    employee_type_name = normalize_text(employee_type_name)
    if not employee_type_name:
        return None
    employee_type = EmployeeType.objects.filter(employee_type=employee_type_name).first()
    if not employee_type:
        employee_type = EmployeeType.objects.create(employee_type=employee_type_name)
    return employee_type


def ensure_shift_day(day_name, company=None):
    day_name = normalize_text(day_name).lower()
    if not day_name:
        return None
    shift_day = EmployeeShiftDay.objects.filter(day=day_name).first()
    if not shift_day:
        shift_day = EmployeeShiftDay.objects.create(day=day_name)
    if company:
        shift_day.company_id.add(company)
    return shift_day


def resolve_reporting_manager(value):
    value = normalize_text(value)
    if not value:
        return None
    badge = parse_employee_badge(value)
    if badge:
        manager = Employee.objects.filter(badge_id=badge).first()
        if manager:
            return manager
    parts = value.split()
    if len(parts) >= 2:
        manager = Employee.objects.filter(
            employee_first_name__iexact=parts[0],
            employee_last_name__iexact=" ".join(parts[1:]),
        ).first()
        if manager:
            return manager
    return next(
        (emp for emp in Employee.objects.all() if full_name(emp).lower() == value.lower()),
        None,
    )


def import_employee_dataframe(data_frame):
    success_count = 0
    created_count = 0
    updated_count = 0
    errors = []

    with transaction.atomic():
        for index, row in enumerate(data_frame.to_dict("records"), start=2):
            try:
                badge_id = normalize_text(row.get("Badge ID"))
                email = normalize_text(row.get("Email")).lower()
                first_name = normalize_text(row.get("First Name"))
                if not badge_id or not email or not first_name:
                    raise ValueError("Badge ID, Email and First Name are required.")

                company = ensure_company(row.get("Company"))
                if normalize_text(row.get("Company")) and not company:
                    raise ValueError(
                        f"Company '{normalize_text(row.get('Company'))}' does not exist."
                    )

                user = resolve_user_by_email(email)
                employee = Employee.objects.filter(badge_id=badge_id).first()
                if not employee:
                    employee = Employee.objects.filter(email=email).first()

                is_created = employee is None
                if employee is None:
                    employee = Employee(employee_user_id=user)
                elif not employee.employee_user_id:
                    employee.employee_user_id = user

                employee.badge_id = badge_id
                employee.employee_first_name = first_name
                employee.employee_last_name = normalize_text(row.get("Last Name"))
                employee.email = email
                employee.phone = normalize_text(row.get("Phone"))
                employee.gender = normalize_text(row.get("Gender")).lower() or "male"
                employee.save()

                department = ensure_department(row.get("Department"), company)
                job_position = ensure_job_position(
                    row.get("Job Position"), department, company
                )
                job_role = ensure_job_role(row.get("Job Role"), job_position, company)
                shift = ensure_shift(row.get("Shift"), company)
                work_type = ensure_work_type(row.get("Work Type"), company)
                employee_type = ensure_employee_type(row.get("Employee Type"))
                reporting_manager = resolve_reporting_manager(row.get("Reporting Manager"))

                work_info, _ = EmployeeWorkInformation.objects.get_or_create(
                    employee_id=employee
                )
                work_info.department_id = department
                work_info.job_position_id = job_position
                work_info.job_role_id = job_role
                work_info.shift_id = shift
                work_info.work_type_id = work_type
                work_info.reporting_manager_id = reporting_manager
                work_info.employee_type_id = employee_type
                work_info.location = normalize_text(row.get("Location")) or None
                work_info.company_id = company
                work_info.email = email
                work_info.date_joining = parse_date_value(row.get("Date Joining"))
                work_info.contract_end_date = parse_date_value(
                    row.get("Contract End Date")
                )
                work_info.basic_salary = parse_int_value(row.get("Basic Salary"), 0)
                work_info.salary_hour = parse_int_value(row.get("Salary Hour"), 0)
                work_info.save()

                success_count += 1
                if is_created:
                    created_count += 1
                else:
                    updated_count += 1
            except Exception as exc:
                errors.append({"row": index, "error": str(exc)})

    return {
        "total_rows": len(data_frame.index),
        "success_count": success_count,
        "created_count": created_count,
        "updated_count": updated_count,
        "error_count": len(errors),
        "errors": errors,
    }


def import_attendance_dataframe(data_frame):
    success_count = 0
    created_count = 0
    updated_count = 0
    errors = []

    with transaction.atomic():
        for index, row in enumerate(data_frame.to_dict("records"), start=2):
            try:
                employee = resolve_employee(row.get("Employee"))
                if not employee:
                    raise ValueError(
                        f"Employee '{normalize_text(row.get('Employee'))}' not found."
                    )

                attendance_date = parse_date_value(row.get("Attendance date"))
                if not attendance_date:
                    raise ValueError("Attendance date is required.")

                company = getattr(
                    getattr(employee, "employee_work_info", None), "company_id", None
                )
                shift = ensure_shift(row.get("Shift"), company)
                work_type = ensure_work_type(row.get("Work Type"), company)
                shift_day = ensure_shift_day(row.get("Attendance day"), company)
                batch_title = normalize_text(row.get("Batch Attendance"))
                batch = (
                    BatchAttendance.objects.get_or_create(title=batch_title)[0]
                    if batch_title
                    else None
                )

                attendance = Attendance.objects.filter(
                    employee_id=employee, attendance_date=attendance_date
                ).first()
                is_created = attendance is None
                if attendance is None:
                    attendance = Attendance(employee_id=employee, attendance_date=attendance_date)

                attendance.shift_id = shift
                attendance.work_type_id = work_type
                attendance.attendance_day = shift_day
                attendance.attendance_clock_in_date = parse_date_value(
                    row.get("Check-In Date")
                )
                attendance.attendance_clock_in = parse_time_value(row.get("Check-In"))
                attendance.attendance_clock_out_date = parse_date_value(
                    row.get("Check-Out Date")
                )
                attendance.attendance_clock_out = parse_time_value(row.get("Check-Out"))
                attendance.attendance_worked_hour = parse_duration_value(
                    row.get("Worked Hours")
                )
                attendance.minimum_hour = parse_duration_value(row.get("Minimum hour"))
                attendance.batch_attendance_id = batch
                attendance.attendance_overtime = parse_duration_value(row.get("Overtime"))
                attendance.attendance_overtime_approve = parse_bool(
                    row.get("Overtime Approve")
                )
                attendance.attendance_validated = parse_bool(
                    row.get("Attendance Validate")
                )
                attendance.overtime_second = parse_int_value(
                    row.get("Overtime In Second"), 0
                )
                attendance.is_bulk_request = parse_bool(
                    row.get("is bulk request")
                )
                attendance.is_holiday = parse_bool(row.get("is holiday"))
                attendance.is_active = parse_bool(row.get("Is Active"), True)
                attendance.save()

                created_by_email = normalize_text(row.get("Created By")).lower()
                modified_by_email = normalize_text(row.get("Modified By")).lower()
                created_by = (
                    User.objects.filter(username=created_by_email).first()
                    or User.objects.filter(email=created_by_email).first()
                )
                modified_by = (
                    User.objects.filter(username=modified_by_email).first()
                    or User.objects.filter(email=modified_by_email).first()
                )
                created_at = (
                    pd.to_datetime(row.get("Created At"), errors="coerce").to_pydatetime()
                    if normalize_text(row.get("Created At"))
                    else None
                )
                Attendance.objects.filter(pk=attendance.pk).update(
                    is_active=parse_bool(row.get("Is Active"), True),
                    created_at=created_at or attendance.created_at,
                    created_by=created_by or attendance.created_by,
                    modified_by=modified_by or attendance.modified_by,
                )

                success_count += 1
                if is_created:
                    created_count += 1
                else:
                    updated_count += 1
            except Exception as exc:
                errors.append({"row": index, "error": str(exc)})

    return {
        "total_rows": len(data_frame.index),
        "success_count": success_count,
        "created_count": created_count,
        "updated_count": updated_count,
        "error_count": len(errors),
        "errors": errors,
    }


def import_work_record_dataframe(data_frame):
    success_count = 0
    created_count = 0
    updated_count = 0
    errors = []

    date_columns = [column for column in data_frame.columns if column != "Employee"]

    with transaction.atomic():
        for row_index, row in enumerate(data_frame.to_dict("records"), start=2):
            employee = resolve_employee(row.get("Employee"))
            if not employee:
                errors.append(
                    {
                        "row": row_index,
                        "error": f"Employee '{normalize_text(row.get('Employee'))}' not found.",
                    }
                )
                continue

            for column in date_columns:
                raw_value = normalize_text(row.get(column))
                if not raw_value:
                    continue
                try:
                    work_date = parse_date_value(column)
                    if raw_value not in WORK_RECORD_ALLOWED_TYPES:
                        raise ValueError(
                            f"Invalid work record type '{raw_value}'. Allowed values: {', '.join(sorted(WORK_RECORD_ALLOWED_TYPES))}."
                        )
                    work_record = WorkRecords.objects.filter(
                        employee_id=employee, date=work_date
                    ).first()
                    is_created = work_record is None
                    if work_record is None:
                        work_record = WorkRecords(employee_id=employee, date=work_date)

                    work_record.record_name = f"{employee} - {work_date}"
                    work_record.work_record_type = raw_value
                    work_record.shift_id = employee.get_shift()
                    work_record.note = "Imported from work record export"
                    work_record.message = ""
                    work_record.save()

                    success_count += 1
                    if is_created:
                        created_count += 1
                    else:
                        updated_count += 1
                except Exception as exc:
                    errors.append(
                        {
                            "row": row_index,
                            "column": column,
                            "error": str(exc),
                        }
                    )

    return {
        "total_rows": len(data_frame.index),
        "success_count": success_count,
        "created_count": created_count,
        "updated_count": updated_count,
        "error_count": len(errors),
        "errors": errors,
    }
