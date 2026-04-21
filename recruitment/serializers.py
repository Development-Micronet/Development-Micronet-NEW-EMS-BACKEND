import base64
import uuid
from django.core.files.base import ContentFile
from rest_framework import serializers
from recruitment.models import Candidate

class Base64FileField(serializers.FileField):
    def to_internal_value(self, data):
        if isinstance(data, str):
            # Check if it has a data URI scheme like 'data:application/pdf;base64,...'
            if 'data:' in data and ';base64,' in data:
                header, base64_data = data.split(';base64,')
                ext = header.split('/')[-1]
            else:
                base64_data = data
                ext = 'pdf' # Default to PDF

            try:
                decoded_file = base64.b64decode(base64_data)
            except Exception:
                raise serializers.ValidationError("Invalid base64 string for file.")

            file_name = f"{uuid.uuid4().hex[:12]}.{ext}"
            data = ContentFile(decoded_file, name=file_name)

        return super().to_internal_value(data)

class CandidateSerializer(serializers.ModelSerializer):
    resume = Base64FileField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = Candidate
        fields = [
            'id',
            'name',
            'recruitment_id',
            'job_position_id',
            'email',
            'mobile',
            'portfolio',
            'resume',
            'gender',
            'address',
            'country',
            'state',
            'city',
            'zip',
            'status',
        ]

    def get_status(self, obj):
        return "applied"
