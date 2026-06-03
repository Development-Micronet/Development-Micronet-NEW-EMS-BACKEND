from rest_framework import serializers
from .models import Holiday, CompanyLeave

class HolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = ['id', 'name', 'start_date', 'end_date', 'company', 'recurring']


class CompanyLeaveSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyLeave
        fields = ['id', 'based_on_week', 'based_on_week_day', 'company']
