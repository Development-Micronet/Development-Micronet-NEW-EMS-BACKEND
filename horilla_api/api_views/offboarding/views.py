from django.core.mail import EmailMessage
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from base.backends import ConfiguredEmailBackend
from horilla_api.api_serializers.offboarding.serializers import (
    OffboardingEmployeeSerializer,
    OffboardingManagerStatusSerializer,
    OffboardingSerializer,
    OffboardingStageSerializer,
    ResignationRequestSerializer,
)
from offboarding.models import (
    Offboarding,
    OffboardingEmployee,
    OffboardingStage,
    ResignationLetter,
)


class ExitProcessAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        if pk:
            try:
                instance = Offboarding.objects.get(pk=pk)
            except Offboarding.DoesNotExist:
                return Response(
                    {"error": "Exit Process does not exist."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            return Response(
                OffboardingSerializer(instance).data, status=status.HTTP_200_OK
            )

        queryset = Offboarding.objects.all().order_by("-id")
        serializer = OffboardingSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = OffboardingSerializer(data=request.data)
        if serializer.is_valid():
            instance = serializer.save()
            return Response(
                OffboardingSerializer(instance).data, status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Exit Process ID is required for update."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            instance = Offboarding.objects.get(pk=pk)
        except Offboarding.DoesNotExist:
            return Response(
                {"error": "Exit Process does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = OffboardingSerializer(instance, data=request.data)
        if serializer.is_valid():
            updated = serializer.save()
            return Response(
                OffboardingSerializer(updated).data, status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Exit Process ID is required for partial update."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            instance = Offboarding.objects.get(pk=pk)
        except Offboarding.DoesNotExist:
            return Response(
                {"error": "Exit Process does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = OffboardingSerializer(instance, data=request.data, partial=True)
        if serializer.is_valid():
            updated = serializer.save()
            return Response(
                OffboardingSerializer(updated).data, status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Exit Process ID is required for delete."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            instance = Offboarding.objects.get(pk=pk)
        except Offboarding.DoesNotExist:
            return Response(
                {"error": "Exit Process does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )
        instance.delete()
        return Response(
            {"message": "Exit Process deleted successfully"},
            status=status.HTTP_200_OK,
        )


class OffboardingEmployeeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        if pk:
            try:
                instance = OffboardingEmployee.objects.get(pk=pk)
            except OffboardingEmployee.DoesNotExist:
                return Response(
                    {"error": "Offboarding employee does not exist."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            return Response(
                OffboardingEmployeeSerializer(instance).data, status=status.HTTP_200_OK
            )

        queryset = OffboardingEmployee.objects.select_related(
            "employee_id", "stage_id", "stage_id__offboarding_id"
        ).order_by("-id")
        serializer = OffboardingEmployeeSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = OffboardingEmployeeSerializer(data=request.data)
        if serializer.is_valid():
            instance = serializer.save()
            return Response(
                OffboardingEmployeeSerializer(instance).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Offboarding employee ID is required for update."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            instance = OffboardingEmployee.objects.get(pk=pk)
        except OffboardingEmployee.DoesNotExist:
            return Response(
                {"error": "Offboarding employee does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = OffboardingEmployeeSerializer(instance, data=request.data)
        if serializer.is_valid():
            updated = serializer.save()
            return Response(
                OffboardingEmployeeSerializer(updated).data, status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Offboarding employee ID is required for delete."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            instance = OffboardingEmployee.objects.get(pk=pk)
        except OffboardingEmployee.DoesNotExist:
            return Response(
                {"error": "Offboarding employee does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )
        instance.delete()
        return Response(
            {"message": "Offboarding employee deleted successfully"},
            status=status.HTTP_200_OK,
        )


class OffboardingAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        if pk:
            try:
                instance = Offboarding.objects.get(pk=pk)
            except Offboarding.DoesNotExist:
                return Response(
                    {"error": "Offboarding does not exist."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            return Response(
                OffboardingManagerStatusSerializer(instance).data,
                status=status.HTTP_200_OK,
            )

        queryset = Offboarding.objects.all().order_by("-id")
        serializer = OffboardingManagerStatusSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = OffboardingManagerStatusSerializer(data=request.data)
        if serializer.is_valid():
            instance = serializer.save()
            return Response(
                OffboardingManagerStatusSerializer(instance).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Offboarding ID is required for update."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            instance = Offboarding.objects.get(pk=pk)
        except Offboarding.DoesNotExist:
            return Response(
                {"error": "Offboarding does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = OffboardingManagerStatusSerializer(instance, data=request.data)
        if serializer.is_valid():
            updated = serializer.save()
            return Response(
                OffboardingManagerStatusSerializer(updated).data,
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Offboarding ID is required for partial update."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            instance = Offboarding.objects.get(pk=pk)
        except Offboarding.DoesNotExist:
            return Response(
                {"error": "Offboarding does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = OffboardingManagerStatusSerializer(
            instance, data=request.data, partial=True
        )
        if serializer.is_valid():
            updated = serializer.save()
            return Response(
                OffboardingManagerStatusSerializer(updated).data,
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Offboarding ID is required for delete."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            instance = Offboarding.objects.get(pk=pk)
        except Offboarding.DoesNotExist:
            return Response(
                {"error": "Offboarding does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class OffboardingStageAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        if pk:
            try:
                instance = OffboardingStage.objects.get(pk=pk)
            except OffboardingStage.DoesNotExist:
                return Response(
                    {"error": "Offboarding stage does not exist."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            return Response(
                OffboardingStageSerializer(instance).data, status=status.HTTP_200_OK
            )

        queryset = OffboardingStage.objects.all().order_by(
            "offboarding_id", "sequence", "id"
        )
        serializer = OffboardingStageSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = OffboardingStageSerializer(data=request.data)
        if serializer.is_valid():
            instance = serializer.save()
            return Response(
                OffboardingStageSerializer(instance).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Offboarding stage ID is required for update."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            instance = OffboardingStage.objects.get(pk=pk)
        except OffboardingStage.DoesNotExist:
            return Response(
                {"error": "Offboarding stage does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = OffboardingStageSerializer(instance, data=request.data)
        if serializer.is_valid():
            updated = serializer.save()
            return Response(
                OffboardingStageSerializer(updated).data, status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Offboarding stage ID is required for partial update."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            instance = OffboardingStage.objects.get(pk=pk)
        except OffboardingStage.DoesNotExist:
            return Response(
                {"error": "Offboarding stage does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = OffboardingStageSerializer(
            instance, data=request.data, partial=True
        )
        if serializer.is_valid():
            updated = serializer.save()
            return Response(
                OffboardingStageSerializer(updated).data, status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Offboarding stage ID is required for delete."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            instance = OffboardingStage.objects.get(pk=pk)
        except OffboardingStage.DoesNotExist:
            return Response(
                {"error": "Offboarding stage does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ResignationRequestAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def _send_resignation_mail(self, instance, action):
        recipient = getattr(instance.employee_id, "email", None)
        if not recipient:
            return
        try:
            email_backend = ConfiguredEmailBackend()
            from_email = getattr(
                email_backend, "dynamic_from_email_with_display_name", None
            )
            subject = f"Resignation Request {action}"
            body = (
                f"Employee: {instance.employee_id.get_full_name()}\n"
                f"Title: {instance.title}\n"
                f"Description: {instance.description}\n"
                f"Planned To Leave On: {instance.planned_to_leave_on}\n"
                f"Status: {instance.status.capitalize()}\n"
            )
            EmailMessage(
                subject=subject,
                body=body,
                from_email=from_email,
                to=[recipient],
                connection=email_backend,
            ).send(fail_silently=True)
        except Exception:
            pass

    def get(self, request, pk=None):
        if pk:
            try:
                instance = ResignationLetter.objects.get(pk=pk)
            except ResignationLetter.DoesNotExist:
                return Response(
                    {"error": "Resignation request does not exist."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            return Response(
                ResignationRequestSerializer(instance).data,
                status=status.HTTP_200_OK,
            )

        queryset = ResignationLetter.objects.select_related("employee_id").order_by("-id")
        serializer = ResignationRequestSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = ResignationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        self._send_resignation_mail(instance, "Created")
        return Response(
            ResignationRequestSerializer(instance).data,
            status=status.HTTP_201_CREATED,
        )

    def put(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Resignation request ID is required for update."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            instance = ResignationLetter.objects.get(pk=pk)
        except ResignationLetter.DoesNotExist:
            return Response(
                {"error": "Resignation request does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )
        old_status = instance.status
        serializer = ResignationRequestSerializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        if updated.status != old_status:
            self._send_resignation_mail(updated, "Status Updated")
        return Response(
            ResignationRequestSerializer(updated).data,
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Resignation request ID is required for delete."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            instance = ResignationLetter.objects.get(pk=pk)
        except ResignationLetter.DoesNotExist:
            return Response(
                {"error": "Resignation request does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )
        instance.delete()
        return Response(
            {"message": "Resignation request deleted successfully"},
            status=status.HTTP_200_OK,
        )
