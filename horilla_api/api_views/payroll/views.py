import gettext
from collections import defaultdict

from django.contrib.auth.decorators import permission_required
from django.shortcuts import render
from django.utils.decorators import method_decorator
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from base.backends import ConfiguredEmailBackend
from base.methods import eval_validate
from payroll.filters import (
    AllowanceFilter,
    ContractFilter,
    DeductionFilter,
    PayslipFilter,
)
from payroll.models.models import (
    Allowance,
    Contract,
    Deduction,
    LoanAccount,
    Payslip,
    Reimbursement,
)
from payroll.models.tax_models import TaxBracket
from payroll.threadings.mail import MailSendThread
from payroll.views.views import payslip_pdf

from ...api_methods.base.methods import groupby_queryset
from ...api_serializers.payroll.serializers import (
    AllowanceSerializer,
    ContractSerializer,
    DeductionSerializer,
    LoanAccountSerializer,
    PayslipSerializer,
    ReimbursementSerializer,
    TaxBracketSerializer,
)


class PayslipView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id=None):
        if id:
            payslip = Payslip.objects.filter(id=id).first()
            if (
                request.user.has_perm("payroll.view_payslip")
                or payslip.employee_id == request.user.employee_get
            ):
                serializer = PayslipSerializer(payslip)
            return Response(serializer.data, status=200)
        if request.user.has_perm("payroll.view_payslip"):
            payslips = Payslip.objects.all()
        else:
            payslips = Payslip.objects.filter(
                employee_id__employee_user_id=request.user
            )

        payslip_filter_queryset = PayslipFilter(request.GET, payslips).qs
        # groupby workflow
        field_name = request.GET.get("groupby_field", None)
        if field_name:
            url = request.build_absolute_uri()
            return groupby_queryset(request, url, field_name, payslip_filter_queryset)
        pagination = PageNumberPagination()
        page = pagination.paginate_queryset(payslip_filter_queryset, request)
        serializer = PayslipSerializer(page, many=True)
        return pagination.get_paginated_response(serializer.data)


class PayslipDownloadView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        if request.user.has_perm("payroll.view_payslip"):
            return payslip_pdf(request, id)

        if Payslip.objects.filter(id=id, employee_id=request.user.employee_get):
            return payslip_pdf(request, id)
        else:
            raise Response({"error": "You don't have permission"})


class PayslipSendMailView(APIView):
    permission_classes = [IsAuthenticated]

    @method_decorator(permission_required("payroll.add_payslip"))
    def post(self, request):
        email_backend = ConfiguredEmailBackend()
        if not getattr(
            email_backend, "dynamic_username_with_display_name", None
        ) or not len(email_backend.dynamic_username_with_display_name):
            return Response({"error": "Email server is not configured"}, status=400)

        payslip_ids = request.data.get("id", [])
        payslips = Payslip.objects.filter(id__in=payslip_ids)
        result_dict = defaultdict(
            lambda: {"employee_id": None, "instances": [], "count": 0}
        )

        for payslip in payslips:
            employee_id = payslip.employee_id
            result_dict[employee_id]["employee_id"] = employee_id
            result_dict[employee_id]["instances"].append(payslip)
            result_dict[employee_id]["count"] += 1
        mail_thread = MailSendThread(request, result_dict=result_dict, ids=payslip_ids)
        mail_thread.start()
        return Response({"status": "success"}, status=200)


class ContractView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id=None):
        if id:
            contract = Contract.objects.filter(id=id).first()
            serializer = ContractSerializer(contract)
            return Response(serializer.data, status=200)
        if request.user.has_perm("payroll.view_contract"):
            contracts = Contract.objects.all()
        else:
            contracts = Contract.objects.filter(employee_id=request.user.employee_get)
        filter_queryset = ContractFilter(request.GET, contracts).qs
        # groupby workflow
        field_name = request.GET.get("groupby_field", None)
        if field_name:
            url = request.build_absolute_uri()
            return groupby_queryset(request, url, field_name, filter_queryset)
        pagination = PageNumberPagination()
        page = pagination.paginate_queryset(filter_queryset, request)
        serializer = ContractSerializer(page, many=True)
        return pagination.get_paginated_response(serializer.data)

    @method_decorator(permission_required("payroll.add_contract"))
    def post(self, request):
        serializer = ContractSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=200)
        return Response(serializer.errors, status=400)

    @method_decorator(permission_required("payroll.change_contract"))
    def put(self, request, pk):
        contract = Contract.objects.get(id=pk)
        serializer = ContractSerializer(instance=contract, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=200)
        return Response(serializer.errors, status=400)

    @method_decorator(permission_required("payroll.delete_contract"))
    def delete(self, request, pk):
        contract = Contract.objects.get(id=pk)
        contract.delete()
        return Response({"status": "deleted"}, status=200)


class AllowanceView(APIView):
    permission_classes = [IsAuthenticated]

    @method_decorator(permission_required("payroll.view_allowance"))
    def get(self, request, pk=None):
        if pk:
            allowance = Allowance.objects.get(id=pk)
            serializer = AllowanceSerializer(instance=allowance)
            return Response(serializer.data, status=200)
        allowance = Allowance.objects.all()
        filter_queryset = AllowanceFilter(request.GET, allowance).qs
        pagination = PageNumberPagination()
        page = pagination.paginate_queryset(filter_queryset, request)
        serializer = AllowanceSerializer(page, many=True)
        return pagination.get_paginated_response(serializer.data)

    @method_decorator(permission_required("payroll.add_allowance"))
    def post(self, request):
        serializer = AllowanceSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=200)
        return Response(serializer.errors, status=400)

    @method_decorator(permission_required("payroll.change_allowance"))
    def put(self, request, pk):
        contract = Allowance.objects.get(id=pk)
        serializer = AllowanceSerializer(instance=contract, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=200)
        return Response(serializer.errors, status=400)

    @method_decorator(permission_required("payroll.delete_allowance"))
    def delete(self, request, pk):
        contract = Allowance.objects.get(id=pk)
        contract.delete()
        return Response({"status": "deleted"}, status=200)


class DeductionView(APIView):
    permission_classes = [IsAuthenticated]

    @method_decorator(permission_required("payroll.view_deduction"))
    def get(self, request, pk=None):
        if pk:
            deduction = Deduction.objects.get(id=pk)
            serializer = DeductionSerializer(instance=deduction)
            return Response(serializer.data, status=200)
        deduction = Deduction.objects.all()
        filter_queryset = DeductionFilter(request.GET, deduction).qs
        pagination = PageNumberPagination()
        page = pagination.paginate_queryset(filter_queryset, request)
        serializer = DeductionSerializer(page, many=True)
        return pagination.get_paginated_response(serializer.data)

    @method_decorator(permission_required("payroll.add_deduction"))
    def post(self, request):
        serializer = DeductionSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=200)
        return Response(serializer.errors, status=400)

    @method_decorator(permission_required("payroll.change_deduction"))
    def put(self, request, pk):
        contract = Deduction.objects.get(id=pk)
        serializer = DeductionSerializer(instance=contract, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=200)
        return Response(serializer.errors, status=400)

    @method_decorator(permission_required("payroll.delete_deduction"))
    def delete(self, request, pk):
        contract = Deduction.objects.get(id=pk)
        contract.delete()
        return Response({"status": "deleted"}, status=200)


class LoanAccountView(APIView):
    permission_classes = [IsAuthenticated]

    @method_decorator(permission_required("payroll.add_loanaccount"))
    def post(self, request):
        serializer = LoanAccountSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=200)
        return Response(serializer.errors, status=400)

    @method_decorator(permission_required("payroll.view_loanaccount"))
    def get(self, request, pk=None):
        if pk:
            loan_account = LoanAccount.objects.get(id=pk)
            serializer = LoanAccountSerializer(instance=loan_account)
            return Response(serializer.data, status=200)
        loan_accounts = LoanAccount.objects.all()
        pagination = PageNumberPagination()
        page = pagination.paginate_queryset(loan_accounts, request)
        serializer = LoanAccountSerializer(page, many=True)
        return pagination.get_paginated_response(serializer.data)

    @method_decorator(permission_required("payroll.change_loanaccount"))
    def put(self, request, pk):
        loan_account = LoanAccount.objects.get(id=pk)
        serializer = LoanAccountSerializer(loan_account, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=200)
        return Response(serializer.errors, status=400)

    @method_decorator(permission_required("payroll.delete_loanaccount"))
    def delete(self, request, pk):
        loan_account = LoanAccount.objects.get(id=pk)
        loan_account.delete()
        return Response(status=200)


class ReimbursementView(APIView):
    serializer_class = ReimbursementSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        if pk:
            reimbursement = Reimbursement.objects.get(id=pk)
            serializer = self.serializer_class(reimbursement)
            return Response(serializer.data, status=200)
        reimbursements = Reimbursement.objects.all()

        if request.user.has_perm("payroll.view_reimbursement"):
            reimbursements = Reimbursement.objects.all()
        else:
            reimbursements = Reimbursement.objects.filter(
                employee_id=request.user.employee_get
            )
        pagination = PageNumberPagination()
        page = pagination.paginate_queryset(reimbursements, request)
        serializer = self.serializer_class(page, many=True)
        return pagination.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=200)
        return Response(serializer.errors, status=400)

    @method_decorator(permission_required("payroll.change_reimbursement"))
    def put(self, request, pk):
        reimbursement = Reimbursement.objects.get(id=pk)
        serializer = self.serializer_class(instance=reimbursement, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=200)
        return Response(serializer.errors, status=400)

    @method_decorator(permission_required("payroll.delete_reimbursement"))
    def delete(self, request, pk):
        reimbursement = Reimbursement.objects.get(id=pk)
        reimbursement.delete()
        return Response(status=200)


class ReimbusementApproveRejectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        status = request.data.get("status", None)
        amount = request.data.get("amount", None)
        amount = (
            eval_validate(request.data.get("amount"))
            if request.data.get("amount")
            else 0
        )
        amount = max(0, amount)
        reimbursement = Reimbursement.objects.filter(id=pk)
        if amount:
            reimbursement.update(amount=amount)
        reimbursement.update(status=status)
        return Response({"status": reimbursement.first().status}, status=200)


class TaxBracketView(APIView):

    def get(self, request, pk=None):
        if pk:
            tax_bracket = TaxBracket.objects.get(id=pk)
            serializer = TaxBracketSerializer(tax_bracket)
            return Response(serializer.data, status=200)
        tax_brackets = TaxBracket.objects.all()
        serializer = TaxBracketSerializer(instance=tax_brackets, many=True)
        return Response(serializer.data, status=200)

    def post(self, request):
        serializer = TaxBracketSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=200)
        return Response(serializer.errors, status=400)

    def put(self, request, pk):
        tax_bracket = TaxBracket.objects.get(id=pk)
        serializer = TaxBracketSerializer(
            instance=tax_bracket, data=request.data, partial=True
        )
        if serializer.save():
            serializer.save()
            return Response(serializer.data, status=200)
        return Response(serializer.errors, status=400)

    def delete(self, request, pk):
        tax_bracket = TaxBracket.objects.get(id=pk)
        tax_bracket.delete()
        return Response(status=200)


from datetime import datetime

from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from rest_framework import status
from rest_framework.authentication import SessionAuthentication

# DRF / Simple JWT imports
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from horilla.horilla_settings import HORILLA_DATE_FORMATS

# Your models / helpers
from payroll.models.models import Company, EmployeeWorkInformation, Payslip
from payroll.models.tax_models import PayrollSettings
from payroll.views.component_views import filter_payslip
from payroll.views.views import equalize_lists_length

try:
    import pdfkit

    HAVE_PDFKIT = True
except Exception:
    HAVE_PDFKIT = False


class PayslipPDFAPIView(APIView):
    """
    GET /api/payslip/<payslip_id>/?format=pdf
    Auth:
      - Accepts SimpleJWT Bearer token (Authorization: Bearer <token>)
      - Also accepts session auth (browser) when available
    """

    authentication_classes = (JWTAuthentication, SessionAuthentication)
    permission_classes = (IsAuthenticated,)

    def get(self, request, id, format=None):
        # get payslip or 404
        payslip = get_object_or_404(Payslip, id=id)

        # authorization: same logic as your view
        user = request.user
        if not (
            user.has_perm("payroll.view_payslip")
            or payslip.employee_id.employee_user_id == user
        ):
            return Response(
                {"detail": "You do not have permission to view this payslip."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # employee & company date format resolution
        employee = user.employee_get  # keep same accessor you used
        info = EmployeeWorkInformation.objects.filter(employee_id=employee)
        if info.exists():
            # take the last one (mirrors your loop behavior)
            employee_company = info.last().company_id
            emp_company = Company.objects.filter(company=employee_company).first()
            date_format = (
                emp_company.date_format
                if emp_company and emp_company.date_format
                else "MMM. D, YYYY"
            )
        else:
            date_format = "MMM. D, YYYY"

        # compose data from payslip (same as original)
        data = (
            payslip.pay_head_data.copy()
            if isinstance(payslip.pay_head_data, dict)
            else {}
        )
        start_date_str = data.get("start_date")
        end_date_str = data.get("end_date")

        if not start_date_str or not end_date_str:
            return Response(
                {"detail": "Payslip missing start_date or end_date"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # parse dates
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

        month_start_name = start_date.strftime("%B %d, %Y")
        month_end_name = end_date.strftime("%B %d, %Y")

        # formatted date for chosen company format (safe default if not found)
        formatted_start_date = start_date.strftime(
            HORILLA_DATE_FORMATS.get(date_format, "%b. %d, %Y")
        )
        formatted_end_date = end_date.strftime(
            HORILLA_DATE_FORMATS.get(date_format, "%b. %d, %Y")
        )

        # fill template context like original view
        data["month_start_name"] = month_start_name
        data["month_end_name"] = month_end_name
        data["formatted_start_date"] = formatted_start_date
        data["formatted_end_date"] = formatted_end_date
        data["employee"] = payslip.employee_id
        data["payslip"] = payslip
        data["json_data"] = data.copy()
        data["json_data"]["employee"] = payslip.employee_id.id
        data["json_data"]["payslip"] = payslip.id
        data["instance"] = payslip
        data["currency"] = (
            PayrollSettings.objects.first().currency_symbol
            if PayrollSettings.objects.exists()
            else "Ã¢â€šÂ¹"
        )
        data["all_deductions"] = []
        for deduction_list in [
            data.get("basic_pay_deductions", []),
            data.get("gross_pay_deductions", []),
            data.get("pretax_deductions", []),
            data.get("post_tax_deductions", []),
            data.get("tax_deductions", []),
            data.get("net_deductions", []),
        ]:
            data["all_deductions"].extend(deduction_list)

        data["all_allowances"] = data.get("allowances", []).copy()
        # equalize lengths (your helper)
        equalize_lists_length(data.setdefault("allowances", []), data["all_deductions"])
        data["zipped_data"] = zip(data["allowances"], data["all_deductions"])
        data["host"] = request.get_host()
        data["protocol"] = "https" if request.is_secure() else "http"
        data["company"] = Company.objects.filter(hq=True).first()

        # render HTML string using template
        html = render_to_string(
            "payroll/payslip/payslip_pdf.html", context=data, request=request
        )

        # If client asked for PDF and pdfkit is available -> return PDF
        requested_format = request.GET.get("format", "").lower()
        if requested_format == "pdf":
            if not HAVE_PDFKIT:
                return Response(
                    {
                        "detail": "PDF generation not available on server. Install pdfkit/wkhtmltopdf."
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            try:
                # optional: configure pdfkit with path if needed
                pdf_options = {
                    "enable-local-file-access": None,  # if your template references local CSS
                }
                pdf_bytes = pdfkit.from_string(html, False, options=pdf_options)
                response = HttpResponse(pdf_bytes, content_type="application/pdf")
                response["Content-Disposition"] = f'inline; filename="payslip-{id}.pdf"'
                return response
            except Exception as e:
                return Response(
                    {"detail": f"PDF generation failed: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        # default: return rendered HTML (use HttpResponse so browser sees it nicely)
        return HttpResponse(html)


from datetime import timedelta

#####################################
#
#       Contract starts here
#
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from employee.models import Employee, EmployeeWorkInformation
from payroll.models.models import Contract, EmployeeContract

from ...api_serializers.payroll.serializers import (
    ContractCreateSerializer,
    EmployeeContractCreateSerializer,
    EmployeeContractReadSerializer,
    EmployeeContractStatusUpdateSerializer,
)

# class EmployeeContractAdminAPIView(APIView):
#     permission_classes = [IsAuthenticated]

#     @method_decorator(
#         permission_required("payroll.add_employeecontract", raise_exception=True)
#     )
#     def post(self, request):
#         serializer = EmployeeContractCreateSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)

#         employee_id = serializer.validated_data["employee_id"]

#         try:
#             employee = Employee.objects.get(id=employee_id)
#         except Employee.DoesNotExist:
#             return Response(
#                 {"employee_id": "Employee does not exist"},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )

#         try:
#             work_info = EmployeeWorkInformation.objects.get(employee_id=employee)
#         except EmployeeWorkInformation.DoesNotExist:
#             return Response(
#                 {"error": "Employee work information not found"},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )

#         # Ã¢ÂÅ’ block duplicate active contract
#         if EmployeeContract.objects.filter(employee=employee, status="active").exists():
#             return Response(
#                 {"error": "Active contract already exists"},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )

#         contract = EmployeeContract.objects.create(
#             employee=employee,
#             contract_type=serializer.validated_data["contract_type"],
#             contract_start_date=work_info.Joining_Date_Label,
#             contract_end_date=work_info.Contract_End_Date_Label,
#             wage_type=serializer.validated_data["wage_type"],
#             pay_frequency=serializer.validated_data["pay_frequency"],
#             basic_salary=work_info.Basic_Salary_Label,
#             department=work_info.Department_Name,
#             job_position=work_info.Job_Position_Name,
#             job_role=work_info.Job_Role_Name,
#             shift=work_info.Shift_Name,
#             work_type=work_info.Work_Type_Name,
#             notice_period_days=serializer.validated_data.get("notice_period_days", 30),
#             contract_document=serializer.validated_data.get("contract_document"),
#             status="active",
#         )

#         return Response(
#             {
#                 "message": "Contract created successfully",
#                 "contract_id": contract.id,
#             },
#             status=status.HTTP_201_CREATED,
#         )


# class EmployeeContractAdminAPIView(APIView):
#     permission_classes = [IsAuthenticated]

#     # Ã°Å¸â€Â¹ ADMIN GET (LIST / DETAIL)
#     @method_decorator(
#         permission_required("payroll.view_employeecontract", raise_exception=True)
#     )
#     def get(self, request, pk=None):
#         if pk:
#             try:
#                 contract = EmployeeContract.objects.select_related("employee").get(
#                     pk=pk
#                 )
#             except EmployeeContract.DoesNotExist:
#                 return Response(
#                     {"error": "Contract not found"},
#                     status=status.HTTP_404_NOT_FOUND,
#                 )

#             serializer = EmployeeContractReadSerializer(contract)
#             return Response(serializer.data, status=status.HTTP_200_OK)

#         contracts = EmployeeContract.objects.select_related("employee").order_by("-id")

#         serializer = EmployeeContractReadSerializer(contracts, many=True)
#         return Response(serializer.data, status=status.HTTP_200_OK)


class EmployeeContractAdminAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @method_decorator(
        permission_required("payroll.add_employeecontract", raise_exception=True)
    )
    def post(self, request):
        serializer = EmployeeContractCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        employee_id = serializer.validated_data["employee_id"]

        try:
            employee = Employee.objects.get(id=employee_id)
        except Employee.DoesNotExist:
            return Response(
                {"employee_id": "Employee does not exist"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            work_info = EmployeeWorkInformation.objects.get(employee_id=employee)
        except EmployeeWorkInformation.DoesNotExist:
            return Response(
                {"error": "Employee work information not found"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Ã¢ÂÅ’ block duplicate active contract
        if EmployeeContract.objects.filter(employee=employee, status="active").exists():
            return Response(
                {"error": "Active contract already exists"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        contract_start_date = work_info.date_joining or work_info.Joining_Date_Label
        if not contract_start_date:
            return Response(
                {
                    "error": "Employee joining date is missing. Set employee work information date_joining before creating contract."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        contract_end_date = (
            work_info.contract_end_date or work_info.Contract_End_Date_Label
        )
        basic_salary = (
            work_info.basic_salary
            if work_info.basic_salary is not None
            else work_info.Basic_Salary_Label
        )
        department = work_info.Department_Name or getattr(
            work_info.department_id, "department", ""
        )
        job_position = work_info.Job_Position_Name or getattr(
            work_info.job_position_id, "job_position", ""
        )
        job_role = work_info.Job_Role_Name or getattr(
            work_info.job_role_id, "job_role", ""
        )
        shift = work_info.Shift_Name or getattr(
            work_info.shift_id, "employee_shift", ""
        )
        work_type = work_info.Work_Type_Name or getattr(
            work_info.work_type_id, "work_type", ""
        )

        try:
            contract = EmployeeContract.objects.create(
                employee=employee,
                contract_type=serializer.validated_data["contract_type"],
                contract_start_date=contract_start_date,
                contract_end_date=contract_end_date,
                wage_type=serializer.validated_data["wage_type"],
                pay_frequency=serializer.validated_data["pay_frequency"],
                basic_salary=basic_salary,
                department=department or "",
                job_position=job_position or "",
                job_role=job_role or "",
                shift=shift or "",
                work_type=work_type or "",
                notice_period_days=serializer.validated_data.get(
                    "notice_period_days", 30
                ),
                contract_document=serializer.validated_data.get("contract_document"),
                status="active",
            )
        except (ValidationError, IntegrityError) as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "message": "Contract created successfully",
                "contract_id": contract.id,
            },
            status=status.HTTP_201_CREATED,
        )

    # Ã°Å¸â€Â¹ GET (LIST / DETAIL)
    @method_decorator(
        permission_required("payroll.view_employeecontract", raise_exception=True)
    )
    def get(self, request, pk=None):
        if pk:
            try:
                contract = EmployeeContract.objects.select_related("employee").get(
                    pk=pk
                )
            except EmployeeContract.DoesNotExist:
                return Response(
                    {"error": "Contract not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            serializer = EmployeeContractReadSerializer(contract)
            return Response(serializer.data, status=status.HTTP_200_OK)

        contracts = EmployeeContract.objects.select_related("employee").order_by("-id")
        serializer = EmployeeContractReadSerializer(contracts, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # Ã°Å¸â€Â¹ POST (already working Ã¢â‚¬â€œ unchanged)

    # Ã°Å¸â€Â¹ PUT Ã¢â€ â€™ UPDATE CONTRACT STATUS ONLY
    @method_decorator(
        permission_required("payroll.change_employeecontract", raise_exception=True)
    )
    def put(self, request, pk):
        try:
            contract = EmployeeContract.objects.get(pk=pk)
        except EmployeeContract.DoesNotExist:
            return Response(
                {"error": "Contract not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = EmployeeContractStatusUpdateSerializer(
            contract, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "message": "Contract status updated successfully",
                "contract_id": contract.id,
                "status": contract.status,
            },
            status=status.HTTP_200_OK,
        )

    # Ã°Å¸â€Â¹ DELETE Ã¢â€ â€™ ONLY IF STATUS = TERMINATED
    @method_decorator(
        permission_required("payroll.delete_employeecontract", raise_exception=True)
    )
    def delete(self, request, pk):
        try:
            contract = EmployeeContract.objects.get(pk=pk)
        except EmployeeContract.DoesNotExist:
            return Response(
                {"error": "Contract not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if contract.status != "terminated":
            return Response(
                {"error": "Only terminated contracts can be deleted"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        contract.delete()
        return Response(
            {"message": "Contract deleted successfully"},
            status=status.HTTP_204_NO_CONTENT,
        )


##################################
#
#  Pay admin new  view code here boy yeah
#
##################################


from django.contrib.auth.decorators import permission_required
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from employee.models import Employee, EmployeeBankDetails, EmployeeWorkInformation
from payroll.models.models import PayslipNew

from ...api_serializers.payroll.serializers import (
    PayslipNewCreateSerializer,
    PayslipNewReadSerializer,
)


class EmployeePayslipAdminAPIView(APIView):
    permission_classes = [IsAuthenticated]

    # Ã°Å¸â€Â¹ CREATE PAYSLIP
    @method_decorator(
        permission_required("payroll.add_payslipnew", raise_exception=True)
    )
    def post(self, request):
        serializer = PayslipNewCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        employee_id = serializer.validated_data["employee_id"]

        try:
            employee = Employee.objects.get(id=employee_id)
        except Employee.DoesNotExist:
            return Response(
                {"employee_id": "Employee does not exist"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            work_info = EmployeeWorkInformation.objects.get(employee_id=employee)
        except EmployeeWorkInformation.DoesNotExist:
            return Response(
                {"error": "Employee work information not found"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        bank_info = EmployeeBankDetails.objects.filter(employee_id=employee).first()
        basic_salary = (
            work_info.basic_salary
            if work_info.basic_salary is not None
            else work_info.Basic_Salary_Label
        )
        if basic_salary is None:
            return Response(
                {
                    "error": (
                        "Employee basic salary is missing. "
                        "Set EmployeeWorkInformation.basic_salary or "
                        "EmployeeWorkInformation.Basic_Salary_Label first."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payslip = PayslipNew.objects.create(
                employee=employee,
                start_date=serializer.validated_data["start_date"],
                end_date=serializer.validated_data["end_date"],
                department=work_info.Department_Name or "",
                job_position=work_info.Job_Position_Name or "",
                job_role=work_info.Job_Role_Name or "",
                shift=work_info.Shift_Name or "",
                work_type=work_info.Work_Type_Name or "",
                basic_salary=basic_salary,
                bank_name=bank_info.bank_name if bank_info else None,
                account_number=bank_info.account_number if bank_info else None,
                ifsc_code=bank_info.any_other_code1 if bank_info else None,
                status=serializer.validated_data["status"],
            )
        except IntegrityError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "message": "Payslip generated successfully",
                "payslip_id": payslip.id,
            },
            status=status.HTTP_201_CREATED,
        )

    # Ã°Å¸â€Â¹ GET ALL PAYSLIPS
    @method_decorator(
        permission_required("payroll.view_payslipnew", raise_exception=True)
    )
    def get(self, request):
        payslips = PayslipNew.objects.select_related("employee")
        serializer = PayslipNewReadSerializer(payslips, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # Ã°Å¸â€Â¹ DELETE PAYSLIP
    @method_decorator(
        permission_required("payroll.delete_payslipnew", raise_exception=True)
    )
    def delete(self, request, pk):
        try:
            payslip = PayslipNew.objects.get(pk=pk)
        except PayslipNew.DoesNotExist:
            return Response(
                {"error": "Payslip not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        payslip.delete()
        return Response(
            {"message": "Payslip deleted successfully"},
            status=status.HTTP_204_NO_CONTENT,
        )

    @method_decorator(
        permission_required("payroll.change_payslipnew", raise_exception=True)
    )
    def put(self, request, pk):
        try:
            payslip = PayslipNew.objects.get(pk=pk)
        except PayslipNew.DoesNotExist:
            return Response(
                {"error": "Payslip not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        new_status = request.data.get("status")

        allowed_status = ["inprocess", "confirmed", "paid"]

        if new_status not in allowed_status:
            return Response(
                {
                    "error": "Invalid status",
                    "allowed_status": allowed_status,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Ã¢ÂÅ’ Optional strict flow enforcement
        status_flow = {
            "inprocess": ["confirmed"],
            "confirmed": ["paid"],
            "paid": [],
        }

        if new_status not in status_flow[payslip.status]:
            return Response(
                {
                    "error": f"Cannot change status from '{payslip.status}' to '{new_status}'"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        payslip.status = new_status
        payslip.save(update_fields=["status"])

        return Response(
            {
                "message": "Payslip status updated successfully",
                "payslip_id": payslip.id,
                "status": payslip.status,
            },
            status=status.HTTP_200_OK,
        )


class EmployeePayslipNewPDFAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            payslip = PayslipNew.objects.select_related("employee").get(pk=pk)
        except PayslipNew.DoesNotExist:
            return Response(
                {"error": "Payslip not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not (
            request.user.has_perm("payroll.view_payslipnew")
            or payslip.employee.employee_user_id == request.user
        ):
            return Response(
                {"detail": "You do not have permission to view this payslip."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not HAVE_PDFKIT:
            return Response(
                {
                    "detail": (
                        "PDF generation not available on server. "
                        "Install pdfkit/wkhtmltopdf."
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        currency = (
            PayrollSettings.objects.first().currency_symbol
            if PayrollSettings.objects.exists()
            else "INR"
        )
        context = {
            "payslip": payslip,
            "employee": payslip.employee,
            "currency": currency,
        }
        html = render_to_string(
            "payroll/payslip/payslip_new_pdf.html",
            context=context,
            request=request,
        )

        try:
            pdf_options = {"enable-local-file-access": None}
            pdf_bytes = pdfkit.from_string(html, False, options=pdf_options)
            response = HttpResponse(pdf_bytes, content_type="application/pdf")
            response["Content-Disposition"] = (
                f'inline; filename="payslip-new-{pk}.pdf"'
            )
            return response
        except Exception as exc:
            return Response(
                {"detail": f"PDF generation failed: {str(exc)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


##################################
#
#  Pay Employee new  view code here boy yeah
#
##################################


class EmployeePayslipAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        employee = request.user.employee_get

        payslips = (
            PayslipNew.objects.select_related("employee")
            .filter(employee=employee)
            .order_by("-created_at")
        )

        data = []
        for slip in payslips:
            data.append(
                {
                    "payslip_id": slip.id,
                    "employee_name": employee.get_full_name(),
                    "department": slip.department,
                    "job_position": slip.job_position,
                    "job_role": slip.job_role,
                    "shift": slip.shift,
                    "work_type": slip.work_type,
                    "bank_name": slip.bank_name,
                    "account_number": slip.account_number,
                    "ifsc_code": slip.ifsc_code,
                    "basic_salary": slip.basic_salary,
                    "start_date": slip.start_date,
                    "end_date": slip.end_date,
                    "generated_at": slip.created_at,
                    "status": slip.status,
                }
            )

        return Response(data, status=status.HTTP_200_OK)
