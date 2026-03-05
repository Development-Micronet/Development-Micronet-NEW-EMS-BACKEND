from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from horilla_api.api_serializers.offboarding.serializers import (
    OffboardingEmployeeSerializer,
    OffboardingManagerStatusSerializer,
    OffboardingSerializer,
    OffboardingStageSerializer,
)
from offboarding.models import Offboarding, OffboardingEmployee, OffboardingStage


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
        return Response(status=status.HTTP_204_NO_CONTENT)


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
        return Response(status=status.HTTP_204_NO_CONTENT)


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
