from django.urls import path
from .views import HolidayListCreateView, HolidayRetrieveUpdateDestroyView, CompanyLeaveListCreateView, CompanyLeaveRetrieveUpdateDestroyView

urlpatterns = [
    path('holidays/', HolidayListCreateView.as_view(), name='holiday-list-create'),
    path('holidays/<int:pk>/', HolidayRetrieveUpdateDestroyView.as_view(), name='holiday-detail'),
    path('company-leaves/', CompanyLeaveListCreateView.as_view(), name='companyleave-list-create'),
    path('company-leaves/<int:pk>/', CompanyLeaveRetrieveUpdateDestroyView.as_view(), name='companyleave-detail'),
]
