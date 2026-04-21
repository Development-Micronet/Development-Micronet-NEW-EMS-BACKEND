from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import viewsets, status, serializers
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import AllowAny
from recruitment.models import Candidate
from recruitment.serializers import CandidateSerializer
from rest_framework.decorators import action

class ApplyNowViewSet(viewsets.ModelViewSet):
    queryset = Candidate.objects.all()
    serializer_class = CandidateSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    permission_classes = [AllowAny]

    def perform_create(self, serializer):
        try:
            candidate = serializer.save()
            if candidate.recruitment_id and not candidate.stage_id:
                stages = candidate.recruitment_id.stage_set.all()
                applied_stage = stages.filter(stage_type="applied").first()
                candidate.stage_id = applied_stage if applied_stage else stages.order_by("sequence").first()
                candidate.save()
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.message_dict if hasattr(e, 'message_dict') else list(e))

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        data = serializer.data
        response_data = dict(data)
        response_data['status'] = 'applied'
        return Response(response_data, status=status.HTTP_201_CREATED, headers=headers)

    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)
