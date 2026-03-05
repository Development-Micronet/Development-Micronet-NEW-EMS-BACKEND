from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from horilla_api.api_serializers.onboarding.serializers import (
    OnboardingCandidateSerializer,
)
from recruitment.models import Candidate


class OnboardingCandidateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        if pk:
            try:
                candidate = Candidate.objects.get(pk=pk)
            except Candidate.DoesNotExist:
                return Response(
                    {"error": "Candidate does not exist"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            serializer = OnboardingCandidateSerializer(candidate)
            return Response(serializer.data, status=status.HTTP_200_OK)

        candidates = Candidate.objects.filter(
            hired=True, recruitment_id__closed=False, is_active=True
        ).order_by("id")
        serializer = OnboardingCandidateSerializer(candidates, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = OnboardingCandidateSerializer(data=request.data)
        if serializer.is_valid():
            candidate = serializer.save(hired=True)
            return Response(
                OnboardingCandidateSerializer(candidate).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Candidate ID is required for update."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            candidate = Candidate.objects.get(pk=pk)
        except Candidate.DoesNotExist:
            return Response(
                {"error": "Candidate does not exist"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = OnboardingCandidateSerializer(candidate, data=request.data)
        if serializer.is_valid():
            updated = serializer.save()
            return Response(
                OnboardingCandidateSerializer(updated).data, status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Candidate ID is required for partial update."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            candidate = Candidate.objects.get(pk=pk)
        except Candidate.DoesNotExist:
            return Response(
                {"error": "Candidate does not exist"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = OnboardingCandidateSerializer(
            candidate, data=request.data, partial=True
        )
        if serializer.is_valid():
            updated = serializer.save()
            return Response(
                OnboardingCandidateSerializer(updated).data, status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Candidate ID is required for delete."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            candidate = Candidate.objects.get(pk=pk)
        except Candidate.DoesNotExist:
            return Response(
                {"error": "Candidate does not exist"},
                status=status.HTTP_404_NOT_FOUND,
            )
        candidate.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
