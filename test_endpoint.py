import sys
from django.test import RequestFactory
from horilla_api.api_views.employee.views import EmployeeListAPIView
from django.contrib.auth import get_user_model

try:
    # Get any active user to mock authentication
    User = get_user_model()
    user = User.objects.first()
    
    # Setup mock request
    factory = RequestFactory()
    request = factory.get('/api/employee/list/employees/')
    request.user = user
    
    # Call view
    view = EmployeeListAPIView.as_view()
    response = view(request)
    
    # Print the output explicitly
    print(response.content.decode('utf-8'))
except Exception as e:
    print(f"Error testing endpoint: {e}")
