from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from horilla_api.api_serializers.onboarding.serializers import (
    OnboardingCandidateSerializer,
)
from horilla_api.api_serializers.recruitment.serializers import (
    RecruitmentInterviewSerializer,
    RecruitmentPipelineSerializer,
    RecruitmentStageSerializer,
    RecruitmentSurveyQuestionSerializer,
    RecruitmentSurveyTemplateSerializer,
)
from recruitment.models import (
    Candidate,
    InterviewSchedule,
    Recruitment,
    RecruitmentSurvey,
    Stage,
    SurveyTemplate,
)


class RecruitmentPipelineAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RecruitmentPipelineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "message": "Recruitment pipeline created successfully",
                "data": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def get(self, request, pk=None):
        queryset = Recruitment.objects.select_related(
            "job_position_id", "company_id"
        ).prefetch_related("recruitment_managers", "survey_templates", "skills")

        if pk:
            recruitment = get_object_or_404(queryset, pk=pk)
            serializer = RecruitmentPipelineSerializer(recruitment)
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer = RecruitmentPipelineSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Recruitment pipeline ID required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        recruitment = get_object_or_404(Recruitment, pk=pk)
        serializer = RecruitmentPipelineSerializer(
            recruitment, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "message": "Recruitment pipeline updated successfully",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Recruitment pipeline ID required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        recruitment = get_object_or_404(Recruitment, pk=pk)
        recruitment.delete()
        return Response(
            {"message": "Recruitment pipeline deleted successfully"},
            status=status.HTTP_204_NO_CONTENT,
        )


class RecruitmentCandidateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = OnboardingCandidateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        candidate = serializer.save()
        return Response(
            {
                "message": "Candidate created successfully",
                "data": OnboardingCandidateSerializer(candidate).data,
            },
            status=status.HTTP_201_CREATED,
        )

    def get(self, request, pk=None):
        if pk:
            candidate = get_object_or_404(Candidate, pk=pk)
            serializer = OnboardingCandidateSerializer(candidate)
            return Response(serializer.data, status=status.HTTP_200_OK)

        candidates = Candidate.objects.all().order_by("-id")
        serializer = OnboardingCandidateSerializer(candidates, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Candidate ID required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        candidate = get_object_or_404(Candidate, pk=pk)
        serializer = OnboardingCandidateSerializer(candidate, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated_candidate = serializer.save()
        return Response(
            {
                "message": "Candidate updated successfully",
                "data": OnboardingCandidateSerializer(updated_candidate).data,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Candidate ID required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        candidate = get_object_or_404(Candidate, pk=pk)
        candidate.delete()
        return Response(
            {"message": "Candidate deleted successfully"},
            status=status.HTTP_204_NO_CONTENT,
        )


class RecruitmentSurveyTemplateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RecruitmentSurveyTemplateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "message": "Survey template created successfully",
                "data": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def get(self, request, pk=None):
        if pk:
            instance = get_object_or_404(SurveyTemplate, pk=pk)
            serializer = RecruitmentSurveyTemplateSerializer(instance)
            return Response(serializer.data, status=status.HTTP_200_OK)

        queryset = SurveyTemplate.objects.select_related("company_id").order_by("-id")
        serializer = RecruitmentSurveyTemplateSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Survey template ID required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance = get_object_or_404(SurveyTemplate, pk=pk)
        serializer = RecruitmentSurveyTemplateSerializer(
            instance, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "message": "Survey template updated successfully",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Survey template ID required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance = get_object_or_404(SurveyTemplate, pk=pk)
        instance.delete()
        return Response(
            {"message": "Survey template deleted successfully"},
            status=status.HTTP_204_NO_CONTENT,
        )


class RecruitmentSurveyQuestionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RecruitmentSurveyQuestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "message": "Survey question created successfully",
                "data": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def get(self, request, pk=None):
        queryset = RecruitmentSurvey.objects.prefetch_related(
            "template_id", "recruitment_ids"
        ).order_by("sequence", "id")
        if pk:
            instance = get_object_or_404(queryset, pk=pk)
            serializer = RecruitmentSurveyQuestionSerializer(instance)
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer = RecruitmentSurveyQuestionSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Survey question ID required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance = get_object_or_404(RecruitmentSurvey, pk=pk)
        serializer = RecruitmentSurveyQuestionSerializer(
            instance, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "message": "Survey question updated successfully",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Survey question ID required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance = get_object_or_404(RecruitmentSurvey, pk=pk)
        instance.delete()
        return Response(
            {"message": "Survey question deleted successfully"},
            status=status.HTTP_204_NO_CONTENT,
        )


class RecruitmentStageAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RecruitmentStageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "message": "Recruitment stage created successfully",
                "data": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def get(self, request, pk=None):
        queryset = Stage.objects.select_related("recruitment_id").prefetch_related(
            "stage_managers"
        ).order_by("sequence", "id")
        if pk:
            instance = get_object_or_404(queryset, pk=pk)
            serializer = RecruitmentStageSerializer(instance)
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer = RecruitmentStageSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Recruitment stage ID required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance = get_object_or_404(Stage, pk=pk)
        serializer = RecruitmentStageSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "message": "Recruitment stage updated successfully",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Recruitment stage ID required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance = get_object_or_404(Stage, pk=pk)
        instance.delete()
        return Response(
            {"message": "Recruitment stage deleted successfully"},
            status=status.HTTP_204_NO_CONTENT,
        )


class RecruitmentInterviewAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RecruitmentInterviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "message": "Interview created successfully",
                "data": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def get(self, request, pk=None):
        queryset = InterviewSchedule.objects.select_related("candidate_id").prefetch_related(
            "employee_id"
        ).order_by("-interview_date", "-id")
        if pk:
            instance = get_object_or_404(queryset, pk=pk)
            serializer = RecruitmentInterviewSerializer(instance)
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer = RecruitmentInterviewSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Interview ID required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance = get_object_or_404(InterviewSchedule, pk=pk)
        serializer = RecruitmentInterviewSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "message": "Interview updated successfully",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Interview ID required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance = get_object_or_404(InterviewSchedule, pk=pk)
        instance.delete()
        return Response(
            {"message": "Interview deleted successfully"},
            status=status.HTTP_200_OK,
        )
