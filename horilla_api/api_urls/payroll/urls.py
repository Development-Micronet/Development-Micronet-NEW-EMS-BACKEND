from django.urls import path

from ...api_views.payroll.views import *
from ...api_views.payroll.views import (
    EmployeeContractAdminAPIView,
    EmployeePayslipAdminAPIView,
    EmployeePayslipAPIView,
)

urlpatterns = [
    # payslip api employee bro
    path("employee-payslips/", EmployeePayslipAPIView.as_view()),
    ############### payslip api admin bro
    path("payslips/", EmployeePayslipAdminAPIView.as_view()),
    path("payslips/<int:pk>/", EmployeePayslipAdminAPIView.as_view()),
    path("payslips/<int:pk>/download/", EmployeePayslipNewPDFAPIView.as_view()),
    ############### contract api
    path(
        "contracts/",
        EmployeeContractAdminAPIView.as_view(),
        name="admin-contract-create",
    ),
    path(
        "contracts/<int:pk>/",
        EmployeeContractAdminAPIView.as_view(),
        name="admin-contract-update-delete",
    ),
    #####################################
    # path(
    #     "contract/",
    #     ContractView.as_view(),
    # ),
    # path(
    #     "contract/<int:id>",
    #     ContractView.as_view(),
    # ),
    path("payslip/", PayslipView.as_view(), name=""),
    path("payslip/<int:id>", PayslipView.as_view(), name=""),
    path("payslip-download/<int:id>", PayslipPDFAPIView.as_view(), name=""),
    path("payslip-send-mail/", PayslipSendMailView.as_view(), name=""),
    path("loan-account/", LoanAccountView.as_view(), name=""),
    path("loan-account/<int:pk>", LoanAccountView.as_view(), name=""),
    path("reimbusement/", ReimbursementView.as_view(), name=""),
    path("reimbusement/<int:pk>", ReimbursementView.as_view(), name=""),
    path(
        "reimbusement-approve-reject/<int:pk>",
        ReimbusementApproveRejectView.as_view(),
        name="",
    ),
    path("tax-bracket/<int:pk>", TaxBracketView.as_view(), name=""),
    path("tax-bracket/", TaxBracketView.as_view(), name=""),
    path("allowance", AllowanceView.as_view(), name=""),
    path("allowance/<int:pk>", AllowanceView.as_view(), name=""),
    path("deduction", DeductionView.as_view(), name=""),
    path("deduction/<int:pk>", DeductionView.as_view(), name=""),
]
