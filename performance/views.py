from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import KeyResult, Meeting, Objective, Question, QuestionTemplate
from .serializers import (
    KeyResultSerializer,
    MeetingSerializer,
    ObjectiveSerializer,
    QuestionSerializer,
    QuestionTemplateSerializer,
)


class ObjectiveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self, request):
        employee = request.user.employee_get
        if employee.role == "admin":
            return Objective.objects.all()
        return Objective.objects.filter(
            Q(employee=employee) | Q(managers=employee)
        ).distinct()

    def get(self, request, pk=None):
        qs = self.get_queryset(request)
        if pk:
            obj = qs.filter(id=pk).first()
            if not obj:
                return Response(
                    {"error": "Not found"}, status=status.HTTP_404_NOT_FOUND
                )
            return Response(ObjectiveSerializer(obj).data, status=status.HTTP_200_OK)
        return Response(
            ObjectiveSerializer(qs, many=True).data, status=status.HTTP_200_OK
        )

    def post(self, request):
        serializer = ObjectiveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def put(self, request, pk):
        obj = self.get_queryset(request).filter(id=pk).first()
        if not obj:
            return Response({"error": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)
        serializer = ObjectiveSerializer(obj, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        obj = self.get_queryset(request).filter(id=pk).first()
        if not obj:
            return Response({"error": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)
        obj.delete()
        return Response({"message": "Deleted"}, status=status.HTTP_200_OK)


class KeyResultAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = KeyResultSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"message": "Key Result created successfully", "data": serializer.data},
            status=status.HTTP_201_CREATED,
        )

    def get(self, request, pk=None):
        if pk:
            key_result = get_object_or_404(KeyResult, pk=pk)
            serializer = KeyResultSerializer(key_result)
            return Response(serializer.data, status=status.HTTP_200_OK)
        key_results = KeyResult.objects.all()
        serializer = KeyResultSerializer(key_results, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        key_result = get_object_or_404(KeyResult, pk=pk)
        serializer = KeyResultSerializer(key_result, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"message": "Key Result updated successfully", "data": serializer.data},
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk):
        key_result = get_object_or_404(KeyResult, pk=pk)
        key_result.delete()
        return Response(
            {"message": "Key Result deleted successfully"},
            status=status.HTTP_204_NO_CONTENT,
        )


class MeetingAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self, request):
        employee = request.user.employee_get
        if employee.role == "admin":
            return Meeting.objects.all()
        return Meeting.objects.filter(
            Q(employees=employee)
            | Q(manager=employee)
            | Q(answerable_employees=employee)
        ).distinct()

    def get(self, request, pk=None):
        qs = self.get_queryset(request)
        if pk:
            obj = qs.filter(id=pk).first()
            if not obj:
                return Response(
                    {"error": "Not found"}, status=status.HTTP_404_NOT_FOUND
                )
            return Response(self.format_response(obj), status=status.HTTP_200_OK)
        return Response(
            [self.format_response(obj) for obj in qs], status=status.HTTP_200_OK
        )

    def post(self, request):
        serializer = MeetingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        meeting = serializer.save()
        return Response(
            {
                "message": "Meeting created successfully",
                "data": self.format_response(meeting),
            },
            status=status.HTTP_201_CREATED,
        )

    def put(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Meeting ID required"}, status=status.HTTP_400_BAD_REQUEST
            )
        obj = self.get_queryset(request).filter(id=pk).first()
        if not obj:
            return Response({"error": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)
        serializer = MeetingSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        meeting = serializer.save()
        return Response(
            {
                "message": "Meeting updated successfully",
                "data": self.format_response(meeting),
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk):
        obj = self.get_queryset(request).filter(id=pk).first()
        if not obj:
            return Response({"error": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)
        obj.delete()
        return Response(
            {"message": "Meeting deleted successfully"},
            status=status.HTTP_204_NO_CONTENT,
        )

    def format_response(self, obj):
        return {
            "id": obj.id,
            "Title": obj.title,
            "Date": obj.date,
            "Employees": {
                "total": obj.employees.count(),
                "data": [
                    {"id": emp.id, "name": emp.get_full_name()}
                    for emp in obj.employees.all()
                ],
            },
            "Managers": {
                "total": 1 if obj.manager else 0,
                "data": (
                    [{"id": obj.manager.id, "name": obj.manager.get_full_name()}]
                    if obj.manager
                    else []
                ),
            },
            "Answerable Employees": {
                "total": obj.answerable_employees.count(),
                "data": [
                    {"id": emp.id, "name": emp.get_full_name()}
                    for emp in obj.answerable_employees.all()
                ],
            },
            "MoM": obj.mom,
        }


class QuestionTemplateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        if pk:
            obj = QuestionTemplate.objects.filter(id=pk).first()
            if not obj:
                return Response(
                    {"error": "Not found"}, status=status.HTTP_404_NOT_FOUND
                )
            return Response(
                QuestionTemplateSerializer(obj).data, status=status.HTTP_200_OK
            )
        return Response(
            QuestionTemplateSerializer(QuestionTemplate.objects.all(), many=True).data,
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = QuestionTemplateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def put(self, request, pk):
        obj = QuestionTemplate.objects.filter(id=pk).first()
        if not obj:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = QuestionTemplateSerializer(obj, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        obj = QuestionTemplate.objects.filter(id=pk).first()
        if not obj:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        obj.delete()
        return Response({"message": "Deleted"}, status=status.HTTP_200_OK)


class QuestionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        template_id = request.query_params.get("template_id")
        qs = Question.objects.all()
        if template_id:
            qs = qs.filter(template_id=template_id)
        if pk:
            obj = qs.filter(id=pk).first()
            if not obj:
                return Response(
                    {"error": "Not found"}, status=status.HTTP_404_NOT_FOUND
                )
            return Response(QuestionSerializer(obj).data, status=status.HTTP_200_OK)
        return Response(
            QuestionSerializer(qs, many=True).data, status=status.HTTP_200_OK
        )

    def post(self, request):
        serializer = QuestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def put(self, request, pk):
        obj = Question.objects.filter(id=pk).first()
        if not obj:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = QuestionSerializer(obj, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        obj = Question.objects.filter(id=pk).first()
        if not obj:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        obj.delete()
        return Response({"message": "Deleted"}, status=status.HTTP_200_OK)


from .models import Feedback
from .serializers import FeedbackSerializer


class FeedbackAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self, request):
        employee = request.user.employee_get

        if employee.role == "admin":
            return Feedback.objects.all()

        return Feedback.objects.filter(employee=employee)

    # ======================
    # GET (List / Single)
    # ======================
    def get(self, request, pk=None):
        qs = self.get_queryset(request)

        if pk:
            obj = qs.filter(id=pk).first()
            if not obj:
                return Response({"error": "Not found"}, status=404)
            return Response(FeedbackSerializer(obj).data)

        return Response(FeedbackSerializer(qs, many=True).data)

    # ======================
    # POST (Create)
    # ======================
    def post(self, request):
        serializer = FeedbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "message": "Feedback created successfully",
                "data": serializer.data,
            },
            status=201,
        )

    # ======================
    # PUT (Update)
    # ======================
    def put(self, request, pk):
        obj = self.get_queryset(request).filter(id=pk).first()
        if not obj:
            return Response({"error": "Not allowed"}, status=403)

        serializer = FeedbackSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "message": "Feedback updated successfully",
                "data": serializer.data,
            }
        )

    # ======================
    # DELETE
    # ======================
    def delete(self, request, pk):
        obj = self.get_queryset(request).filter(id=pk).first()
        if not obj:
            return Response({"error": "Not allowed"}, status=403)

        obj.delete()
        return Response(
            {"message": "Feedback deleted successfully"},
            status=204,
        )


class MyAssignedFeedbackAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        employee = request.user.employee_get

        feedbacks = Feedback.objects.filter(employee=employee)

        response = []

        for fb in feedbacks:
            questions = []
            if fb.question_template:
                for q in fb.question_template.questions.all():
                    questions.append(
                        {
                            "id": q.id,
                            "question": q.question,
                            "answer_type": q.answer_type,
                        }
                    )

            response.append(
                {
                    "feedback_id": fb.id,
                    "title": fb.title,
                    "status": fb.status,
                    "start_date": fb.start_date,
                    "end_date": fb.end_date,
                    "key_result_id": fb.key_result.id if fb.key_result else None,
                    "question_template_id": (
                        fb.question_template.id if fb.question_template else None
                    ),
                    "questions": questions,
                }
            )

        return Response(response)


from .models import FeedbackAnswer


class SubmitFeedbackAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        employee = request.user.employee_get
        feedback_id = request.data.get("feedback_id")
        answers = request.data.get("answers", [])

        feedback = Feedback.objects.filter(id=feedback_id, employee=employee).first()

        if not feedback:
            return Response({"error": "Feedback not found or not assigned"}, status=404)

        if feedback.status == "completed":
            return Response({"error": "Feedback already submitted"}, status=400)

        for ans in answers:
            question_id = ans.get("question_id")
            question = Question.objects.filter(id=question_id).first()

            if not question:
                continue

            FeedbackAnswer.objects.create(
                feedback=feedback,
                question=question,
                answered_by=employee,
                answer_text=ans.get("answer_text"),
                answer_boolean=ans.get("answer_boolean"),
                answer_rating=ans.get("answer_rating"),
            )

        feedback.status = "completed"
        feedback.save()

        return Response({"message": "Feedback submitted successfully"}, status=201)


class AdminFeedbackAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def format_feedback(self, fb):
        answers_data = []

        for ans in fb.answers.all():
            answers_data.append(
                {
                    "question": ans.question.question,
                    "answer_text": ans.answer_text,
                    "answer_boolean": ans.answer_boolean,
                    "answer_rating": ans.answer_rating,
                    "answered_by": ans.answered_by.get_full_name(),
                }
            )

        return {
            "feedback_id": fb.id,
            "title": fb.title,
            "employee": {
                "id": fb.employee.id,
                "name": fb.employee.get_full_name(),
            },
            "status": fb.status,
            "start_date": fb.start_date,
            "end_date": fb.end_date,
            "key_result": (
                {
                    "id": fb.key_result.id,
                    "title": fb.key_result.title,
                }
                if fb.key_result
                else None
            ),
            "question_template": (
                {
                    "id": fb.question_template.id,
                    "name": fb.question_template.name,
                }
                if fb.question_template
                else None
            ),
            "answers": answers_data,
        }

    def get(self, request, pk=None):
        employee = request.user.employee_get

        # Only admin allowed
        if employee.role != "admin":
            return Response({"error": "Not allowed"}, status=403)

        qs = Feedback.objects.all().order_by("-created_at")

        if pk:
            feedback = qs.filter(id=pk).first()
            if not feedback:
                return Response({"error": "Not found"}, status=404)

            return Response(self.format_feedback(feedback))

        return Response([self.format_feedback(fb) for fb in qs])


# bonus logic here


from .models import NewBonusEmployee
from .serializers import NewBonusEmployeeSerializer


class NewBonusEmployeeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    # GET (List / Single)
    def get(self, request, pk=None):

        if pk:
            bonus = get_object_or_404(NewBonusEmployee, pk=pk)
            serializer = NewBonusEmployeeSerializer(bonus)
            return Response(serializer.data)

        bonuses = NewBonusEmployee.objects.all()
        serializer = NewBonusEmployeeSerializer(bonuses, many=True)
        return Response(serializer.data)

    # POST (Create)
    def post(self, request):
        serializer = NewBonusEmployeeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {"message": "New bonus created successfully", "data": serializer.data},
            status=status.HTTP_201_CREATED,
        )

    # PUT (Update)
    def put(self, request, pk):
        bonus = get_object_or_404(NewBonusEmployee, pk=pk)
        serializer = NewBonusEmployeeSerializer(bonus, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {"message": "New bonus updated successfully", "data": serializer.data}
        )

    # DELETE
    def delete(self, request, pk):
        bonus = get_object_or_404(NewBonusEmployee, pk=pk)
        bonus.delete()

        return Response(
            {"message": "New bonus deleted successfully"},
            status=status.HTTP_204_NO_CONTENT,
        )
