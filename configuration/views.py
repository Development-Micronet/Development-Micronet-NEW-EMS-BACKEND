from rest_framework import status, generics
from rest_framework.response import Response
from .models import Holiday, CompanyLeave
from .serializers import HolidaySerializer, CompanyLeaveSerializer

class HolidayListCreateView(generics.ListCreateAPIView):
    queryset = Holiday.objects.all()
    serializer_class = HolidaySerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'Holiday Name': serializer.data['name'],
                'Start Date': serializer.data['start_date'],
                'End Date': serializer.data['end_date'],
                'Company': serializer.data['company'],
                'Recurring': serializer.data['recurring']
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class HolidayRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Holiday.objects.all()
    serializer_class = HolidaySerializer


# CompanyLeave Endpoints
class CompanyLeaveListCreateView(generics.ListCreateAPIView):
    queryset = CompanyLeave.objects.all()
    serializer_class = CompanyLeaveSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'Based On Week': serializer.data['based_on_week'],
                'Based On Week Day': serializer.data['based_on_week_day'],
                'Company': serializer.data['company']
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CompanyLeaveRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = CompanyLeave.objects.all()
    serializer_class = CompanyLeaveSerializer
