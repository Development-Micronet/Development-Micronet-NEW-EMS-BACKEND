from django.db.models import F
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from horilla_api.api_serializers.onboarding.serializers import (
    OnboardingCandidateSerializer,
)
from recruitment.models import Candidate


class OnboardingCandidateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def _get_queryset(self):
        return (
            Candidate.objects.select_related(
                "recruitment_id", "job_position_id", "stage_id", "referral"
            ).annotate(status=F("stage_id__stage_type"))
            .filter(
                hired=True,
                recruitment_id__closed=False,
            )
            .order_by("id")
        )

    def get(self, request, pk=None):
        queryset = self._get_queryset()
        if pk:
            try:
                candidate = queryset.get(pk=pk)
            except Candidate.DoesNotExist:
                return Response(
                    {"error": "Candidate does not exist"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            serializer = OnboardingCandidateSerializer(candidate)
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer = OnboardingCandidateSerializer(
            queryset, many=True, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = OnboardingCandidateSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            candidate = serializer.save(hired=True)
            response_serializer = OnboardingCandidateSerializer(
                candidate, context={"request": request}
            )
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Candidate ID is required for update."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            candidate = self._get_queryset().get(pk=pk)
        except Candidate.DoesNotExist:
            return Response(
                {"error": "Candidate does not exist"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = OnboardingCandidateSerializer(
            candidate, data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            updated = serializer.save()
            response_serializer = OnboardingCandidateSerializer(
                updated, context={"request": request}
            )
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Candidate ID is required for partial update."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            candidate = self._get_queryset().get(pk=pk)
        except Candidate.DoesNotExist:
            return Response(
                {"error": "Candidate does not exist"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = OnboardingCandidateSerializer(
            candidate, data=request.data, partial=True, context={"request": request}
        )
        if serializer.is_valid():
            updated = serializer.save()
            response_serializer = OnboardingCandidateSerializer(
                updated, context={"request": request}
            )
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Candidate ID is required for delete."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            candidate = self._get_queryset().get(pk=pk)
        except Candidate.DoesNotExist:
            return Response(
                {"error": "Candidate does not exist"},
                status=status.HTTP_404_NOT_FOUND,
            )
        candidate.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
