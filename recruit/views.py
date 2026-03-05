from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Candidate
from .serializer import CandidateSerializer


class CandidateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    # ========================
    # CREATE
    # ========================
    def post(self, request):
        serializer = CandidateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {"message": "Candidate created successfully", "data": serializer.data},
            status=status.HTTP_201_CREATED,
        )

    # ========================
    # LIST / SINGLE
    # ========================
    def get(self, request, pk=None):
        if pk:
            candidate = get_object_or_404(Candidate, pk=pk)
            serializer = CandidateSerializer(candidate, context={"request": request})
            return Response(serializer.data)

        candidates = Candidate.objects.all()
        serializer = CandidateSerializer(
            candidates, many=True, context={"request": request}
        )
        return Response(serializer.data)

    # ========================
    # UPDATE
    # ========================
    def put(self, request, pk=None):
        if not pk:
            return Response({"error": "Candidate ID required"}, status=400)

        candidate = get_object_or_404(Candidate, pk=pk)
        serializer = CandidateSerializer(
            candidate, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {"message": "Candidate updated successfully", "data": serializer.data}
        )

    # ========================
    # DELETE
    # ========================
    def delete(self, request, pk=None):
        if not pk:

            return Response({"error": "Candidate ID required"}, status=400)

        candidate = get_object_or_404(Candidate, pk=pk)
        candidate.delete()

        return Response(
            {"message": "Candidate deleted successfully"},
            status=status.HTTP_204_NO_CONTENT,
        )


from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Interview
from .serializer import InterviewSerializer


class InterviewAPIView(APIView):
    permission_classes = [IsAuthenticated]

    # ======================
    # CREATE
    # ======================
    def post(self, request):
        serializer = InterviewSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {"message": "Interview scheduled successfully", "data": serializer.data},
            status=status.HTTP_201_CREATED,
        )

    # ======================
    # LIST / SINGLE
    # ======================
    def get(self, request, pk=None):

        if pk:
            interview = get_object_or_404(Interview, pk=pk)
            serializer = InterviewSerializer(interview, context={"request": request})
            return Response(serializer.data)

        interviews = Interview.objects.select_related("candidate").all()
        serializer = InterviewSerializer(
            interviews, many=True, context={"request": request}
        )
        return Response(serializer.data)

    # ======================
    # UPDATE
    # ======================
    def put(self, request, pk=None):

        if not pk:
            return Response({"error": "Interview ID required"}, status=400)

        interview = get_object_or_404(Interview, pk=pk)

        serializer = InterviewSerializer(
            interview, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {"message": "Interview updated successfully", "data": serializer.data}
        )

    # ======================
    # DELETE
    # ======================
    def delete(self, request, pk=None):

        if not pk:
            return Response({"error": "Interview ID required"}, status=400)

        interview = get_object_or_404(Interview, pk=pk)
        interview.delete()

        return Response(
            {"message": "Interview deleted successfully"},
            status=status.HTTP_204_NO_CONTENT,
        )


from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CandidateSkill, SkillZone
from .serializer import CandidateSkillSerializer, SkillZoneSerializer


# =====================================
# SKILL ZONE API
# =====================================
class SkillZoneAPIView(APIView):
    permission_classes = [IsAuthenticated]

    # CREATE
    def post(self, request):
        serializer = SkillZoneSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {"message": "Skill created successfully", "data": serializer.data},
            status=status.HTTP_201_CREATED,
        )

    # LIST / SINGLE
    def get(self, request, pk=None):
        if pk:
            skill = get_object_or_404(SkillZone, pk=pk)
            serializer = SkillZoneSerializer(skill)
            return Response(serializer.data)

        skills = SkillZone.objects.all()
        serializer = SkillZoneSerializer(skills, many=True)
        return Response(serializer.data)

    # UPDATE
    def put(self, request, pk):
        skill = get_object_or_404(SkillZone, pk=pk)
        serializer = SkillZoneSerializer(skill, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {"message": "Skill updated successfully", "data": serializer.data}
        )

    # DELETE
    def delete(self, request, pk):
        skill = get_object_or_404(SkillZone, pk=pk)
        skill.delete()
        return Response(
            {"message": "Skill deleted successfully"},
            status=status.HTTP_204_NO_CONTENT,
        )


# =====================================
# CANDIDATE SKILL API
# =====================================
class CandidateSkillAPIView(APIView):
    permission_classes = [IsAuthenticated]

    # CREATE
    def post(self, request):
        serializer = CandidateSkillSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "message": "Candidate skill assigned successfully",
                "data": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    # LIST / SINGLE
    def get(self, request, pk=None):
        if pk:
            obj = get_object_or_404(CandidateSkill, pk=pk)
            serializer = CandidateSkillSerializer(obj)
            return Response(serializer.data)

        qs = CandidateSkill.objects.select_related("candidate", "skill")
        serializer = CandidateSkillSerializer(qs, many=True)
        return Response(serializer.data)

    # UPDATE
    def put(self, request, pk):
        obj = get_object_or_404(CandidateSkill, pk=pk)
        serializer = CandidateSkillSerializer(obj, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {"message": "Candidate skill updated successfully", "data": serializer.data}
        )

    # DELETE
    def delete(self, request, pk):
        obj = get_object_or_404(CandidateSkill, pk=pk)
        obj.delete()
        return Response(
            {"message": "Candidate skill deleted successfully"},
            status=status.HTTP_204_NO_CONTENT,
        )
