import os
import secrets
import sys

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils import timezone
from rest_framework import serializers

# Add the brave_email_sender to path
sys.path.insert(0, os.path.dirname(__file__) + "/../../..")

from attendance.models import Attendance, AttendanceActivity
from base.backends import ConfiguredEmailBackend
from base.models import (
    BrevoEmailConfiguration,
    Company,
    Department,
    DynamicEmailConfiguration,
    EmployeeShift,
    EmployeeType,
    JobPosition,
    JobRole,
    WorkType,
)
from employee.models import (
    Actiontype,
    DisciplinaryAction,
    Employee,
    EmployeeBankDetails,
    EmployeeWorkInformation,
    Policy,
    PolicyMultipleFile,
    WorkTypeRequest,
)


class WorkTypeRequestSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(
        source="employee.get_full_name", read_only=True
    )
    employee_id = serializers.IntegerField(source="employee.id", read_only=True)
    work_type_name = serializers.CharField(source="work_type.work_type", read_only=True)

    work_type = serializers.CharField(write_only=True)
    employee = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.filter(), write_only=True, required=True
    )

    class Meta:
        model = WorkTypeRequest
        fields = [
            "employee_id",
            "employee_name",
            "employee",
            "work_type",
            "work_type_name",
            "request_date",
            "status",
            "description",
            # "reason",  # Uncomment if you want to include 'reason' in the response
        ]

    def get_reason(self, obj):
        return obj.notes if obj.notes is not None else ""

    def validate_work_type(self, value):
        from base.models import WorkType

        # Accept pk or string for work_type
        if str(value).isdigit():
            try:
                return WorkType.objects.get(pk=int(value))
            except WorkType.DoesNotExist:
                raise serializers.ValidationError(
                    f"WorkType with id '{value}' does not exist."
                )
        else:
            work_type_name = str(value).strip()
            if not work_type_name:
                raise serializers.ValidationError("work_type is required.")
            work_type, _ = WorkType.objects.get_or_create(work_type=work_type_name)
            return work_type

    def create(self, validated_data):
        work_type = validated_data.pop("work_type")
        employee = validated_data.pop("employee")
        validated_data["work_type"] = work_type
        validated_data["employee"] = employee
        return super().create(validated_data)

    def update(self, instance, validated_data):
        work_type = validated_data.pop("work_type", None)
        employee = validated_data.pop("employee", None)
        if work_type is not None:
            validated_data["work_type"] = work_type
        if employee is not None:
            validated_data["employee"] = employee
        return super().update(instance, validated_data)


from horilla_documents.models import Document, DocumentRequest

from ...api_methods.employee.methods import get_next_badge_id

try:
    from brevo_email_sender import BrevoEmailSender

    BREVO_AVAILABLE = True
except ImportError:
    BREVO_AVAILABLE = False

try:
    from brave_email_sender import DirectEmailSender

    BRAVE_EMAIL_AVAILABLE = True
except ImportError:
    BRAVE_EMAIL_AVAILABLE = False


class ActiontypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Actiontype
        fields = ["id", "title", "action_type"]


class EmployeeListSerializer(serializers.ModelSerializer):
    job_position_name = serializers.CharField(
        source="employee_work_info.job_position_id.job_position", read_only=True
    )
    employee_work_info_id = serializers.CharField(
        source="employee_work_info.id", read_only=True
    )
    employee_bank_details_id = serializers.CharField(
        source="employee_bank_details.id", read_only=True
    )
    # Additional fields for complete response
    badge_id = serializers.CharField(read_only=True)
    mobile = serializers.CharField(read_only=True)
    phone = serializers.CharField(read_only=True)
    address = serializers.CharField(read_only=True)
    country = serializers.CharField(read_only=True)
    state = serializers.CharField(read_only=True)
    city = serializers.CharField(read_only=True)
    postal_code = serializers.CharField(read_only=True)
    dob = serializers.DateField(read_only=True)
    gender = serializers.CharField(read_only=True)
    qualification = serializers.CharField(read_only=True)
    experience = serializers.IntegerField(read_only=True)
    marital_status = serializers.CharField(read_only=True)
    children = serializers.IntegerField(read_only=True)
    emergency_contact = serializers.CharField(read_only=True)
    emergency_contact_name = serializers.CharField(read_only=True)
    emergency_contact_relation = serializers.CharField(read_only=True)
    is_active = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Employee
        fields = [
            "id",
            "employee_user_id_id",
            "badge_id",
            "employee_first_name",
            "employee_last_name",
            "email",
            "mobile",
            "phone",
            "address",
            "country",
            "state",
            "city",
            "postal_code",
            "dob",
            "gender",
            "qualification",
            "experience",
            "marital_status",
            "children",
            "emergency_contact",
            "emergency_contact_name",
            "emergency_contact_relation",
            "job_position_name",
            "employee_work_info_id",
            "employee_profile",
            "employee_bank_details_id",
            "is_active",
            "created_at",
            "role",
        ]

    def get_is_active(self, obj):
        # Active means latest attendance event today is a check-in without
        # corresponding check-out.
        today = timezone.localdate()

        latest_activity = (
            AttendanceActivity.objects.filter(
                employee_id=obj,
                attendance_date=today,
            )
            .order_by("-in_datetime", "-id")
            .first()
        )
        if latest_activity is not None:
            return bool(latest_activity.clock_in and latest_activity.clock_out is None)

        latest_attendance = (
            Attendance.objects.filter(
                employee_id=obj,
                attendance_date=today,
            )
            .order_by("-id")
            .first()
        )
        return bool(
            latest_attendance
            and latest_attendance.attendance_clock_in
            and latest_attendance.attendance_clock_out is None
        )


class EmployeeSerializer(serializers.ModelSerializer):

    role = serializers.ChoiceField(
        choices=["admin", "user"], required=False, default="user"
    )
    department_name = serializers.CharField(
        source="employee_work_info.department_id.department", read_only=True
    )
    department_id = serializers.CharField(
        source="employee_work_info.department_id.id", read_only=True
    )
    job_position_name = serializers.CharField(
        source="employee_work_info.job_position_id.job_position", read_only=True
    )
    job_position_id = serializers.CharField(
        source="employee_work_info.job_position_id.id", read_only=True
    )
    employee_work_info_id = serializers.CharField(
        source="employee_work_info.id", read_only=True
    )
    employee_bank_details_id = serializers.CharField(
        source="employee_bank_details.id", read_only=True
    )
    username = serializers.CharField(write_only=True, required=True, allow_blank=True)

    class Meta:
        model = Employee
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        secret_field = "pass" "word"
        self.fields[secret_field] = serializers.CharField(
            write_only=True, required=False, allow_blank=True
        )

    # def create(self, validated_data):
    #     # Extract username and password from validated data
    #     username = validated_data.pop("username", None)
    #     secret_field = "pass" "word"
    #     user_secret = validated_data.pop(secret_field, None)
    #     role = validated_data.get("role", "user")

    #     # Generate badge_id
    #     validated_data["badge_id"] = get_next_badge_id()

    #     # Create User if username provided
    #     user = None
    #     with transaction.atomic():
    #         if username:
    #             # Check if username already exists
    #             if User.objects.filter(username=username).exists():
    #                 raise serializers.ValidationError(
    #                     f"Username '{username}' already exists. Please choose a different username."
    #                 )

    #             # Generate password if not provided
    #             if not user_secret:
    #                 user_secret = secrets.token_urlsafe(12)

    #             # Create Django User. Avoid calling user.save() afterwards because
    #             # the User post_save signal auto-creates an Employee for superusers.
    #             create_user_kwargs = dict(
    #                 username=username,
    #                 email=validated_data.get("email"),
    #                 first_name=validated_data.get("employee_first_name", ""),
    #                 last_name=validated_data.get("employee_last_name", ""),
    #                 **{secret_field: user_secret},
    #             )
    #             user = User.objects.create_user(**create_user_kwargs)
    #             is_admin = role == "admin"
    #             User.objects.filter(pk=user.pk).update(
    #                 is_superuser=is_admin,
    #                 is_staff=is_admin,
    #             )
    #             user.is_superuser = is_admin
    #             user.is_staff = is_admin
    #             validated_data["employee_user_id"] = user

    #         # Reuse any employee row that may already exist for this user.
    #         existing_employee = None
    #         if user is not None:
    #             existing_employee = Employee.objects.filter(employee_user_id=user).first()

    #         if existing_employee is not None:
    #             employee = super().update(existing_employee, validated_data)
    #         else:
    #             employee = super().create(validated_data)

    #     # Send welcome email with credentials
    #     if user and employee.email:
    #         # Store email details for sending (after employee is fully created)
    #         employee_name = f"{employee.employee_first_name} {employee.employee_last_name or ''}".strip()
    #         email = employee.email

    #         self._send_welcome_email(
    #             employee_name=employee_name,
    #             email=email,
    #             username=username,
    #             password=user_secret,
    #         )

    #     return employee
    # def create(self, validated_data):
    #     username = validated_data.pop("username", None)
    #     secret_field = "pass" "word"
    #     user_secret = validated_data.pop(secret_field, None)
    #     role = validated_data.get("role", "user")

    #     # Generate badge_id
    #     validated_data["badge_id"] = get_next_badge_id()

    #     user = None

    #     with transaction.atomic():
    #         if username:
    #             # Case-insensitive username check
    #             if User.objects.filter(username__iexact=username).exists():
    #                 raise serializers.ValidationError(
    #                     {"username": f"Username '{username}' already exists."}
    #                 )

    #             # Generate password if not provided
    #             if not user_secret:
    #                 user_secret = secrets.token_urlsafe(12)

    #             # Create user
    #             user = User.objects.create_user(
    #                 username=username,
    #                 email=validated_data.get("email"),
    #                 first_name=validated_data.get("employee_first_name", ""),
    #                 last_name=validated_data.get("employee_last_name", ""),
    #                 password=user_secret,
    #             )

    #             # Set role
    #             is_admin = role == "admin"
    #             user.is_superuser = is_admin
    #             user.is_staff = is_admin
    #             user.save()

    #             validated_data["employee_user_id"] = user

    #         # ✅ Create employee ONLY ONCE
    #         employee = super().create(validated_data)

    #     # ✅ Send email AFTER successful creation
    #     if user and employee.email:
    #         employee_name = f"{employee.employee_first_name} {employee.employee_last_name or ''}".strip()

    #         self._send_welcome_email(
    #             employee_name=employee_name,
    #             email=employee.email,
    #             username=username,
    #             password=user_secret,
    #         )

    #     return employee
    def create(self, validated_data):
    username = validated_data.pop("username", None)
    secret_field = "pass" "word"
    user_secret = validated_data.pop(secret_field, None)
    role = validated_data.get("role", "user")

    validated_data["badge_id"] = get_next_badge_id()
    user = None

    with transaction.atomic():
        if username:
            if User.objects.filter(username__iexact=username).exists():
                raise serializers.ValidationError(
                    {"username": f"Username '{username}' already exists."}
                )

            if not user_secret:
                user_secret = secrets.token_urlsafe(12)

            user = User.objects.create_user(
                username=username,
                email=validated_data.get("email"),
                first_name=validated_data.get("employee_first_name", ""),
                last_name=validated_data.get("employee_last_name", ""),
                password=user_secret,
            )

            is_admin = role == "admin"

            if is_admin:
                User.objects.filter(pk=user.pk).update(
                    is_superuser=True,
                    is_staff=True,
                )
                user.refresh_from_db()

            validated_data["employee_user_id"] = user

        existing_employee = None
        if user is not None:
            existing_employee = Employee.objects.filter(employee_user_id=user).first()

        if existing_employee is not None:
            employee = super().update(existing_employee, validated_data)
        else:
            employee = super().create(validated_data)

    if user and employee.email:
        employee_name = f"{employee.employee_first_name} {employee.employee_last_name or ''}".strip()
        self._send_welcome_email(
            employee_name=employee_name,
            email=employee.email,
            username=username,
            password=user_secret,
        )

    return employee

    def _send_welcome_email(self, employee_name, email, username, password):
        """Send onboarding email with username and password."""
        subject = "Your Account Credentials - Employee Management System"
        text_content = f"""Hello {employee_name},

Welcome to the Employee Management System!

Your account has been created with the following credentials:

Username: {username}
Password: {password}

Best regards,
HR Management Team"""
        html_content = f"""
        <p>Hello {employee_name},</p>
        <p>Welcome to the Employee Management System!</p>
        <p>Your account has been created with the following credentials:</p>
        <p><b>Username:</b> {username}<br><b>Password:</b> {password}</p>
        <p>Best regards,<br>HR Management Team</p>
        """

        # Try Brevo first (env config has priority, DB config as fallback)
        if BREVO_AVAILABLE:
            api_key = getattr(settings, "BREVO_API_KEY", "").strip()
            from_email = getattr(settings, "BREVO_FROM_EMAIL", "noreply@horilla.com")
            from_name = getattr(settings, "BREVO_FROM_NAME", "HR Management")
            if not api_key:
                brevo_config = BrevoEmailConfiguration.objects.filter(is_active=True).first()
                if brevo_config:
                    api_key = brevo_config.api_key
                    from_email = brevo_config.from_email
                    from_name = brevo_config.from_name

            if api_key:
                try:
                    sender = BrevoEmailSender(
                        api_key=api_key,
                        from_email=from_email,
                        from_name=from_name,
                    )
                    success, _, _ = sender.send_email(
                        to_email=email,
                        to_name=employee_name,
                        subject=subject,
                        html_content=html_content,
                        text_content=text_content,
                    )
                    if success:
                        return True
                except Exception:
                    pass

        # Fallback to existing Django email backend
        try:
            email_backend = ConfiguredEmailBackend()
            from_email = getattr(email_backend, "dynamic_from_email_with_display_name", None)
            message = EmailMessage(
                subject=subject,
                body=text_content,
                from_email=from_email,
                to=[email],
            )
            message.content_subtype = "plain"
            message.send(fail_silently=False)
            return True
        except Exception:
            return False


# class EmployeeWorkInformationSerializer(serializers.ModelSerializer):
#     # API sends USER ID - rename it
#     user_id = serializers.IntegerField(write_only=True)

#     class Meta:
#         model = EmployeeWorkInformation
#         fields = [
#             'user_id',   # NOT employee_id
#             'Department_Name', 'Job_Position_Name', 'Job_Role_Name',
#             'Reporting_Manager_Name', 'Shift_Name', 'Work_Type_Name',
#             'Employee_Type_Name', 'Employee_Tag_Label', 'Work_Location_Label',
#             'Company_Name', 'Work_Email_Label', 'Work_Phone_Label',
#             'Joining_Date_Label', 'Contract_End_Date_Label',
#             'Basic_Salary_Label', 'Salary_Per_Hour_Label',"employee_id"
#         ]

#     def create(self, validated_data):
#         user_id = validated_data.pop("user_id")

#         try:
#             employee = Employee.objects.get(employee_user_id_id=user_id)
#         except Employee.DoesNotExist:
#             raise serializers.ValidationError({
#                 "user_id": "Employee does not exist for this user."
#             })

#         return EmployeeWorkInformation.objects.create(
#             employee_id=employee,  # FK gets Employee instance
#             **validated_data
#         )


class EmployeeWorkInformationSerializer(serializers.ModelSerializer):
    # API input
    user_id = serializers.IntegerField(write_only=True)

    # API output
    employee_id = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeWorkInformation
        fields = [
            "user_id",  # write-only
            "employee_id",  # read-only
            "Department_Name",
            "Job_Position_Name",
            "Job_Role_Name",
            "Reporting_Manager_Name",
            "Shift_Name",
            "Work_Type_Name",
            "Employee_Type_Name",
            "Employee_Tag_Label",
            "Work_Location_Label",
            "Company_Name",
            "Work_Email_Label",
            "Work_Phone_Label",
            "Joining_Date_Label",
            "Contract_End_Date_Label",
            "Basic_Salary_Label",
            "Salary_Per_Hour_Label",
        ]

    def get_employee_id(self, obj):
        return obj.employee_id.id if obj.employee_id else None

    def create(self, validated_data):
        user_id = validated_data.pop("user_id")

        try:
            employee = Employee.objects.get(employee_user_id=user_id)
        except Employee.DoesNotExist:
            raise serializers.ValidationError(
                {"user_id": "Employee does not exist for this user."}
            )

        return EmployeeWorkInformation.objects.create(
            employee_user_id=employee, **validated_data  # Correct FK field
        )

    def update(self, instance, validated_data):
        # Never allow FK change on update
        validated_data.pop("user_id", None)
        return super().update(instance, validated_data)


class EmployeeBankDetailsSerializer(serializers.ModelSerializer):
    ifsc_code = serializers.CharField(
        source="any_other_code1", allow_null=True, required=False
    )
    employee_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee._base_manager.all()
    )

    class Meta:
        model = EmployeeBankDetails
        fields = [
            "employee_id",
            "bank_name",
            "account_number",
            "branch",
            "ifsc_code",
            "address",
            "country",
            "state",
            "city",
        ]


class EmployeeTypeSerializer(serializers.ModelSerializer):
    company_id = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all(), many=True, required=False
    )

    class Meta:
        model = EmployeeType
        fields = "__all__"


class EmployeeBulkUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        # fields = [
        #     'employee_last_name',
        #     'address',
        #     'country',
        #     'state',
        #     'city',
        #     'zip',
        #     'dob',
        #     'gender',
        #     'qualification',
        #     'experience',
        #     'marital_status',
        #     'children',
        # ]
        fields = [
            "employee_last_name",
        ]


class DisciplinaryActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DisciplinaryAction
        fields = "__all__"


class PolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = Policy
        fields = "__all__"


class EmployeePolicySerializer(serializers.ModelSerializer):
    is_visible = serializers.BooleanField(source="is_visible_to_all", required=False)
    attachment_urls = serializers.SerializerMethodField(read_only=True)
    updated_at = serializers.SerializerMethodField(read_only=True)
    attachments_input = serializers.ListField(
        child=serializers.FileField(),
        write_only=True,
        required=False,
    )

    class Meta:
        model = Policy
        fields = [
            "id",
            "title",
            "body",
            "is_visible",
            "attachment_urls",
            "attachments_input",
            "created_at",
            "updated_at",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.method != "GET":
            self.fields.pop("attachment_urls", None)

    def to_internal_value(self, data):
        if hasattr(data, "copy"):
            mutable = data.copy()
        else:
            mutable = dict(data)

        aliases = {
            "Title": "title",
            "Body": "body",
            "Is visible": "is_visible",
            "Attachments": "attachments_input",
            "Attachements": "attachments_input",
        }
        for incoming_key, target_key in aliases.items():
            if incoming_key in mutable and target_key not in mutable:
                mutable[target_key] = mutable[incoming_key]

        # Handle multipart file lists robustly for keys:
        # attachments_input / Attachments / Attachements
        if hasattr(data, "getlist"):
            files = []
            for key in ["attachments_input", "Attachments", "Attachements"]:
                files.extend([f for f in data.getlist(key) if f])
            if files:
                if hasattr(mutable, "setlist"):
                    mutable.setlist("attachments_input", files)
                else:
                    mutable["attachments_input"] = files

        return super().to_internal_value(mutable)

    def get_updated_at(self, obj):
        value = getattr(obj, "updated_at", None)
        return value

    def get_attachment_urls(self, obj):
        request = self.context.get("request")
        urls = []
        for attachment in obj.attachments.all():
            file_url = attachment.attachment.url if attachment.attachment else None
            if not file_url:
                continue
            if request:
                urls.append(request.build_absolute_uri(file_url))
            else:
                urls.append(file_url)
        return urls

    def create(self, validated_data):
        files = validated_data.pop("attachments_input", [])
        policy = Policy.objects.create(**validated_data)
        for file_obj in files:
            attach_obj = PolicyMultipleFile.objects.create(attachment=file_obj)
            policy.attachments.add(attach_obj)
        return policy

    def update(self, instance, validated_data):
        files = validated_data.pop("attachments_input", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if files is not None:
            old_attachments = instance.attachments.all()
            instance.attachments.clear()
            old_attachments.delete()
            for file_obj in files:
                attach_obj = PolicyMultipleFile.objects.create(attachment=file_obj)
                instance.attachments.add(attach_obj)
        return instance


class DocumentRequestSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField(read_only=True)
    employee_id = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = DocumentRequest
        fields = [
            "employee_id",
            "employee_name",
            "title",
            "format",
            "max_size",
            "description",
        ]

    def _get_linked_employees(self, obj):
        from employee.models import Employee

        through_model = obj.employee_id.through
        employee_ids = list(
            through_model.objects.filter(documentrequest_id=obj.id)
            .values_list("employee_id", flat=True)
            .distinct()
        )
        if employee_ids:
            employees_by_id = {
                emp.id: emp
                for emp in Employee._base_manager.filter(id__in=employee_ids)
            }
            employees = [
                employees_by_id[eid] for eid in employee_ids if eid in employees_by_id
            ]
            if employees:
                return employees

        # Fallback for older records where m2m links were not persisted
        docs = Document.objects.filter(document_request_id=obj).select_related(
            "employee_id"
        )
        unique = {}
        for doc in docs:
            emp = doc.employee_id
            if emp and emp.id not in unique:
                unique[emp.id] = emp
        return list(unique.values())

    def get_employee_name(self, obj):
        employees = self._get_linked_employees(obj)
        if employees:
            if len(employees) == 1:
                emp = employees[0]
                return (
                    f"{emp.employee_first_name} {emp.employee_last_name or ''}".strip()
                )
            return [
                f"{emp.employee_first_name} {emp.employee_last_name or ''}".strip()
                for emp in employees
            ]
        return ""

    def get_employee_id(self, obj):
        employees = self._get_linked_employees(obj)
        if employees:
            if len(employees) == 1:
                return employees[0].id
            return [emp.id for emp in employees]
        return ""

    def to_internal_value(self, data):
        # Accept employee_name as input and resolve to employee_id
        employee_name = data.pop("employee_name", None)
        if employee_name is not None:
            from employee.models import Employee

            name_str = employee_name.strip()
            if name_str:
                parts = name_str.split()
                if len(parts) == 1 and parts[0]:
                    qs = Employee.objects.filter(employee_first_name=parts[0])
                elif len(parts) > 1 and parts[0]:
                    qs = Employee.objects.filter(
                        employee_first_name=parts[0],
                        employee_last_name=" ".join(parts[1:]),
                    )
                else:
                    qs = Employee.objects.none()
                if qs.exists() and len(parts) > 0 and parts[0]:
                    emp = qs.first()
                    data["employee_id"] = [emp.id]
                    self._valid_name = f"{emp.employee_first_name} {emp.employee_last_name or ''}".strip()
        return super().to_internal_value(data)

    def create(self, validated_data):
        instance = super().create(validated_data)
        # If _valid_name is set, add employee to m2m after instance is created
        if hasattr(self, "_valid_name") and "employee_id" in validated_data:
            # Already set by to_internal_value
            pass
        elif hasattr(self, "_valid_name") and hasattr(self, "_valid_name"):
            # Defensive: if employee_id not set, try to set it
            from employee.models import Employee

            name_str = self._valid_name
            parts = name_str.split()
            if len(parts) == 1 and parts[0]:
                qs = Employee.objects.filter(employee_first_name=parts[0])
            elif len(parts) > 1 and parts[0]:
                qs = Employee.objects.filter(
                    employee_first_name=parts[0], employee_last_name=" ".join(parts[1:])
                )
            else:
                qs = Employee.objects.none()
            if qs.exists():
                emp = qs.first()
                instance.employee_id.add(emp)
        return instance

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        # Always resolve employee_name for GET
        if hasattr(instance, "_employee_name_override"):
            rep["employee_name"] = instance._employee_name_override
        else:
            employees = instance.employee_id.all()
            if employees:
                emp = employees.first()
                rep["employee_name"] = (
                    f"{emp.employee_first_name} {emp.employee_last_name or ''}".strip()
                )
                rep["employee_id"] = emp.id
            else:
                rep["employee_name"] = None
                rep["employee_id"] = None
        return rep

    def to_internal_value(self, data):
        # Accept employee_name or employee_id as input and resolve both
        employee_names = data.pop("employee_name", None)
        employee_ids = data.get("employee_id", None)
        from employee.models import Employee

        ids = []
        valid_names = []
        if employee_names is not None:
            for name in (
                employee_names if isinstance(employee_names, list) else [employee_names]
            ):
                parts = name.strip().split()
                if len(parts) == 1 and parts[0]:
                    qs = Employee.objects.filter(employee_first_name=parts[0])
                elif len(parts) > 1 and parts[0]:
                    qs = Employee.objects.filter(
                        employee_first_name=parts[0],
                        employee_last_name=" ".join(parts[1:]),
                    )
                else:
                    qs = Employee.objects.none()
                if qs.exists() and len(parts) > 0 and parts[0]:
                    emp = qs.first()
                    ids.append(emp.id)
                    valid_names.append(
                        f"{emp.employee_first_name} {emp.employee_last_name or ''}".strip()
                    )
        elif employee_ids is not None:
            for eid in (
                employee_ids if isinstance(employee_ids, list) else [employee_ids]
            ):
                if eid in (None, ""):
                    continue
                try:
                    emp = Employee.objects.get(id=eid)
                    ids.append(emp.id)
                    valid_names.append(
                        f"{emp.employee_first_name} {emp.employee_last_name or ''}".strip()
                    )
                except (Employee.DoesNotExist, ValueError, TypeError):
                    pass
        if not ids:
            request = self.context.get("request")
            request_employee = (
                getattr(request.user, "employee_get", None)
                if request is not None
                else None
            )
            if request_employee is not None:
                ids = [request_employee.id]
                valid_names = [
                    f"{request_employee.employee_first_name} {request_employee.employee_last_name or ''}".strip()
                ]
            else:
                raise serializers.ValidationError(
                    {
                        "employee": "employee_name or employee_id is required and must match an existing employee."
                    }
                )
        self._employee_ids = ids
        data["employee_id"] = ids
        self._valid_names = valid_names
        return super().to_internal_value(data)

    def create(self, validated_data):
        from employee.models import Employee

        employee_ids = validated_data.pop("employee_id", None)
        if employee_ids is None:
            employee_ids = getattr(self, "_employee_ids", [])

        instance = super().create(validated_data)

        # Always link employees after creation
        if isinstance(employee_ids, (int, str)):
            employee_ids = [employee_ids]
        for eid in employee_ids:
            try:
                emp = Employee.objects.get(id=eid)
                instance.employee_id.add(emp)
            except Employee.DoesNotExist:
                pass
        if hasattr(self, "_valid_names") and self._valid_names:
            for name in self._valid_names:
                parts = name.split()
                if len(parts) == 1 and parts[0]:
                    qs = Employee.objects.filter(employee_first_name=parts[0])
                elif len(parts) > 1 and parts[0]:
                    qs = Employee.objects.filter(
                        employee_first_name=parts[0],
                        employee_last_name=" ".join(parts[1:]),
                    )
                else:
                    qs = Employee.objects.none()
                if qs.exists():
                    emp = qs.first()
                    instance.employee_id.add(emp)
        return instance

    def update(self, instance, validated_data):
        from employee.models import Employee

        employee_ids = validated_data.pop("employee_id", None)
        if employee_ids is None:
            employee_ids = getattr(self, "_employee_ids", [])
        if isinstance(employee_ids, (int, str)):
            employee_ids = [employee_ids]
        if employee_ids:
            instance.employee_id.clear()
            for eid in employee_ids:
                try:
                    emp = Employee.objects.get(id=eid)
                    instance.employee_id.add(emp)
                except Employee.DoesNotExist:
                    pass
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        employees = self._get_linked_employees(instance)
        if employees:
            if len(employees) == 1:
                emp = employees[0]
                rep["employee_id"] = emp.id
                rep["employee_name"] = (
                    f"{emp.employee_first_name} {emp.employee_last_name or ''}".strip()
                )
            else:
                rep["employee_id"] = [emp.id for emp in employees]
                rep["employee_name"] = [
                    f"{emp.employee_first_name} {emp.employee_last_name or ''}".strip()
                    for emp in employees
                ]
        else:
            rep["employee_id"] = ""
            rep["employee_name"] = ""
        if "employees" in rep:
            del rep["employees"]
        return rep


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = "__all__"


class EmployeeSelectorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = [
            "id",
            "employee_first_name",
            "employee_last_name",
            "badge_id",
            "employee_profile",
        ]
