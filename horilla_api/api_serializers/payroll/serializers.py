from rest_framework import serializers

from employee.models import BonusPoint, Employee
from leave.models import LeaveType
from payroll.models.models import (
    Allowance,
    Contract,
    Deduction,
    LoanAccount,
    MultipleCondition,
    Payslip,
    Reimbursement,
    ReimbursementMultipleAttachment,
)
from payroll.models.tax_models import TaxBracket


class PayslipSerializer(serializers.ModelSerializer):
    employee_first_name = serializers.CharField(
        source="employee_id.employee_first_name", read_only=True
    )
    employee_last_name = serializers.CharField(
        source="employee_id.employee_last_name", read_only=True
    )
    shift_name = serializers.CharField(source="shift_id.employee_shift", read_only=True)
    badge_id = serializers.CharField(source="employee_id.badge_id", read_only=True)
    employee_profile_url = serializers.SerializerMethodField(read_only=True)
    department_name = serializers.CharField(
        source="employee_id.employee_work_info.department_id.department", read_only=True
    )
    bank_account_check_number = serializers.CharField(
        source="employee_id.employee_bank_details.account_number", read_only=True
    )

    class Meta:
        model = Payslip
        fields = "__all__"
        # exclude = ['reference',
        #            'sent_to_employee',
        #            'installment_ids', 'created_at']

    def get_employee_profile_url(self, obj):
        try:
            employee_profile = obj.employee_id.employee_profile
            return employee_profile.url
        except:
            return None


#######################
#  COntract starts here
#
from rest_framework import serializers

from employee.models import Employee, EmployeeWorkInformation
from payroll.models.models import Contract, EmployeeContract

# class ContractCreateSerializer(serializers.ModelSerializer):
#     employee_id = serializers.IntegerField(write_only=True)
#     class Meta:
#         model = Contract
#         fields = [
#             "contract_name",
#             "employee_id",
#             "wage_type",
#             "pay_frequency",
#             "notice_period_in_days",
#             "contract_document",
#         ]

#     def create(self, validated_data):
#         employee = validated_data["employee_id"]

#         try:
#             work_info = EmployeeWorkInformation.objects.get(
#                 employee_id=employee
#             )
#         except EmployeeWorkInformation.DoesNotExist:
#             raise serializers.ValidationError(
#                 {"employee_id": "Employee work information not found"}
#             )

#         # 🔹 Pull values from work table
#         validated_data.update({
#             "job_position_id": work_info.job_position_id,
#             "job_role_id": work_info.job_role_id,
#             "shift_id": work_info.shift_id,
#             "start_date": work_info.date_joining,
#             "end_date": work_info.contract_end_date,
#             "status": "active",
#         })

#         return super().create(validated_data)


class ContractCreateSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField()
    contract_name = serializers.CharField(max_length=250)
    wage_type = serializers.ChoiceField(choices=["monthly", "daily", "hourly"])
    pay_frequency = serializers.ChoiceField(
        choices=["monthly", "weekly", "semi_monthly"]
    )
    notice_period_in_days = serializers.IntegerField(required=False, default=30)


class ContractSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contract
        fields = "__all__"


class ContractAdminCreateSerializer(serializers.ModelSerializer):
    employee_id = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all())

    class Meta:
        model = Contract
        fields = [
            "id",
            "contract_name",
            "employee_id",
            "wage_type",
            "pay_frequency",
            "notice_period_in_days",
            "contract_document",
        ]

    def create(self, validated_data):
        employee = validated_data["employee_id"]

        try:
            work_info = EmployeeWorkInformation.objects.get(employee_id=employee)
        except EmployeeWorkInformation.DoesNotExist:
            raise serializers.ValidationError(
                {"employee_id": "Employee work information not found"}
            )

        validated_data.update(
            {
                "contract_start_date": work_info.date_joining,
                "contract_end_date": work_info.contract_end_date,
                "contract_status": "active",
                "wage": work_info.basic_salary or 0,
            }
        )

        return super().create(validated_data)


class ContractStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contract
        fields = ["contract_status"]

    def validate_contract_status(self, value):
        allowed = ["draft", "expired", "terminated"]
        if value not in allowed:
            raise serializers.ValidationError("Invalid contract status")
        return value


from rest_framework import serializers

from payroll.models.models import EmployeeContract


class EmployeeContractCreateSerializer(serializers.ModelSerializer):
    employee_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = EmployeeContract
        fields = [
            "employee_id",
            "contract_type",
            "wage_type",
            "pay_frequency",
            "notice_period_days",
            "contract_document",
        ]


from rest_framework import serializers

from payroll.models.models import EmployeeContract

# class EmployeeContractReadSerializer(serializers.ModelSerializer):
#     employee_name = serializers.SerializerMethodField()
#     employee_id = serializers.IntegerField(source="employee.id", read_only=True)

#     class Meta:
#         model = EmployeeContract
#         fields = [
#             "id",
#             "employee_name",
#             "employee_id",
#             "contract_type",
#             "contract_start_date",
#             "contract_end_date",
#             "wage_type",
#             "basic_salary",
#             "status",
#         ]

#     def get_employee_name(self, obj):
#         return f"{obj.employee.employee_first_name} {obj.employee.employee_last_name}"


class EmployeeContractReadSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    employee_id = serializers.IntegerField(source="employee.id", read_only=True)

    class Meta:
        model = EmployeeContract
        fields = "__all__"

    def get_employee_name(self, obj):
        return f"{obj.employee.employee_first_name} {obj.employee.employee_last_name}"


from rest_framework import serializers


class EmployeeContractStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeContract
        fields = ["status"]

    def validate_status(self, value):
        allowed = ["draft", "active", "expired", "terminated"]
        if value not in allowed:
            raise serializers.ValidationError("Invalid contract status")
        return value


class MultipleConditionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MultipleCondition
        fields = "__all__"


class AllowanceSerializer(serializers.ModelSerializer):
    specific_employees = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(), many=True, required=False
    )
    exclude_employees = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(), many=True, required=False
    )
    other_conditions = serializers.PrimaryKeyRelatedField(
        queryset=MultipleCondition.objects.all(), many=True, required=False
    )

    class Meta:
        model = Allowance
        fields = "__all__"
        read_only_fields = ["id", "company_id", "only_show_under_employee", "is_loan"]

    def create(self, validated_data):
        specific_employees = validated_data.pop("specific_employees", [])
        exclude_employees = validated_data.pop("exclude_employees", [])
        other_conditions = validated_data.pop("other_conditions", [])

        allowance = Allowance.objects.create(**validated_data)

        # Set the ManyToMany relationships after the instance is created
        allowance.specific_employees.set(specific_employees)
        allowance.exclude_employees.set(exclude_employees)
        allowance.other_conditions.set(other_conditions)

        return allowance

    def validate(self, data):
        is_fixed = data.get("is_fixed")
        amount = data.get("amount")
        based_on = data.get("based_on")
        per_attendance_fixed_amount = data.get("per_attendance_fixed_amount")
        shift_id = data.get("shift_id")
        work_type_id = data.get("work_type_id")
        is_condition_based = data.get("is_condition_based")
        field = data.get("field")
        condition = data.get("condition")
        value = data.get("value")
        has_max_limit = data.get("has_max_limit")
        maximum_amount = data.get("maximum_amount")

        if is_fixed and (amount is None or amount < 0):
            raise serializers.ValidationError(
                "If 'is_fixed' is True, 'amount' must be a positive number."
            )

        if not is_fixed and not based_on:
            raise serializers.ValidationError(
                "If 'is_fixed' is False, 'based_on' is required."
            )

        if based_on == "attendance" and not per_attendance_fixed_amount:
            raise serializers.ValidationError(
                "If 'based_on' is 'attendance', 'per_attendance_fixed_amount' is required."
            )

        if based_on == "shift_id" and not shift_id:
            raise serializers.ValidationError(
                "If 'based_on' is 'shift_id', 'shift_id' is required."
            )

        if based_on == "work_type_id" and not work_type_id:
            raise serializers.ValidationError(
                "If 'based_on' is 'work_type_id', 'work_type_id' is required."
            )

        if is_condition_based and (not field or not value or not condition):
            raise serializers.ValidationError(
                "If 'is_condition_based' is True, 'field', 'value', and 'condition' are required."
            )

        if has_max_limit and maximum_amount is None:
            raise serializers.ValidationError(
                "If 'has_max_limit' is True, 'maximum_amount' is required."
            )

        return data


class DeductionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Deduction
        fields = "__all__"


class LoanAccountSerializer(serializers.ModelSerializer):
    employee_profile_url = serializers.SerializerMethodField(read_only=True)
    employee_full_name = serializers.CharField(
        source="employee_id.get_full_name", read_only=True
    )
    badge_id = serializers.CharField(source="employee_id.badge_id", read_only=True)
    job_position_name = serializers.CharField(
        source="employee_id.get_job_position", read_only=True
    )

    class Meta:
        model = LoanAccount
        fields = "__all__"

    def get_employee_profile_url(self, obj):
        try:
            employee_profile = obj.employee_id.employee_profile
            return employee_profile.url
        except:
            return None


class ReimbursementSerializer(serializers.ModelSerializer):
    other_attachements = serializers.SerializerMethodField()
    leave_type_name = serializers.CharField(source="leave_type_id.name", read_only=True)
    employee_profile_url = serializers.SerializerMethodField(read_only=True)
    badge_id = serializers.CharField(source="employee_id.badge_id")
    employee_full_name = serializers.CharField(source="employee_id.get_full_name")

    def get_employee_profile_url(self, obj):
        try:
            employee_profile = obj.employee_id.employee_profile
            return employee_profile.url
        except:
            return None

    class Meta:
        model = Reimbursement
        fields = "__all__"

    def get_other_attachements(self, obj):
        attachments = []
        for attachment in obj.other_attachments.all():
            try:
                attachments.append(attachment.attachment.url)
            except:
                pass
        return attachments

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        exclude_fields = []
        # Get type from data or instance
        instance_type = getattr(self.instance, "type", None)

        if instance_type == "reimbursement":
            exclude_fields.extend(
                ["leave_type_id", "cfd_to_encash", "ad_to_encash", "bonus_to_encash"]
            )
        elif instance_type == "leave_encashment":
            exclude_fields.extend(["attachment", "amount", "bonus_to_encash"])
        elif instance_type == "bonus_encashment":
            exclude_fields.extend(
                [
                    "attachment",
                    "amount",
                    "leave_type_id",
                    "cfd_to_encash",
                    "ad_to_encash",
                ]
            )

        # Remove excluded fields from serializer fields
        for field in exclude_fields:
            self.fields.pop(field, None)

    def get_encashable_leaves(self, employee):
        leaves = LeaveType.objects.filter(
            employee_available_leave__employee_id=employee,
            employee_available_leave__total_leave_days__gte=1,
            is_encashable=True,
        )
        return leaves

    def validate(self, data):
        try:
            employee_id = self.instance.employee_id
            type = self.instance.type
            leave_type_id = self.instance.leave_type_id
        except:
            employee_id = data["employee_id"]
            type = data["type"]
            leave_type_id = (
                data["leave_type_id"] if data.get("leave_type_id", None) else None
            )

        available_points = BonusPoint.objects.filter(employee_id=employee_id).first()
        if type == "bonus_encashment":
            try:
                bonus_to_encash = self.instance.bonus_to_encash
            except:
                bonus_to_encash = data["bonus_to_encash"]

            if available_points.points < bonus_to_encash:
                raise serializers.ValidationError(
                    {"bonus_to_encash": "Not enough bonus points to redeem"}
                )
            if bonus_to_encash <= 0:
                raise serializers.ValidationError(
                    {"bonus_to_encash": "Points must be greater than zero to redeem."}
                )
        if type == "leave_encashment":
            leave_type_id = leave_type_id
            encashable_leaves = self.get_encashable_leaves(employee_id)
            if (leave_type_id is None) or (leave_type_id not in encashable_leaves):
                raise serializers.ValidationError(
                    {"leave_type_id": "This leave type is not encashable"}
                )

        return data

    def save(self, **kwargs):
        multiple_attachment_ids = []
        request_files = self.context["request"].FILES
        attachments = request_files.getlist("attachment")
        if attachments:
            for attachment in attachments:
                file_instance = ReimbursementMultipleAttachment()
                file_instance.attachment = attachment
                file_instance.save()
                multiple_attachment_ids.append(file_instance.pk)

        instance = super().save()
        instance.other_attachments.add(*multiple_attachment_ids)

        return super().save(**kwargs)


class TaxBracketSerializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = TaxBracket


##################################
#
#  Pay slip new serlizer start  here boy yeah
#
##################################

from rest_framework import serializers

from payroll.models.models import PayslipNew


class PayslipNewCreateSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    status = serializers.ChoiceField(
        choices=["inprocess", "confirmed", "paid"], default="inprocess"
    )


class PayslipNewReadSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()

    class Meta:
        model = PayslipNew
        fields = [
            "id",
            "employee_name",
            "start_date",
            "end_date",
            "department",
            "job_position",
            "job_role",
            "shift",
            "work_type",
            "basic_salary",
            "bank_name",
            "account_number",
            "ifsc_code",
            "status",
            "generated_at",
        ]

    def get_employee_name(self, obj):
        return f"{obj.employee.employee_first_name} {obj.employee.employee_last_name}"
