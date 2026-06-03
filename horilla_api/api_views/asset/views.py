# --- Asset Request API for Employee ---
from django.utils import timezone
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from asset.models import AssetCategory, AssetRequest

from ...api_serializers.asset.serializers import AssetRequestSerializer


class AssetRequestUserAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        employee = getattr(request.user, "employee_get", None)
        if not employee:
            return Response(
                {"detail": "User not linked with Employee"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AssetRequestSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save(
                requested_employee_id=employee,  # ✅ Employee instance
                asset_request_status="Requested",
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        # List all requests for this employee
        requests = AssetRequest.objects.filter(
            requested_employee_id=request.user.employee_get
        )
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(requests, request)
        result = []
        for req in page:
            result.append(
                {
                    "id": req.id,
                    "asset_category_name": req.asset_category_id.asset_category_name,
                    "status": req.asset_request_status,
                    "request_date": req.asset_request_date,
                    "request_username": (
                        req.requested_employee_id.get_full_name()
                        if hasattr(req.requested_employee_id, "get_full_name")
                        else str(req.requested_employee_id)
                    ),
                    "description": (
                        req.description if hasattr(req, "description") else ""
                    ),
                }
            )
        return paginator.get_paginated_response(result)

    def put(self, request, pk=None):
        if not pk:
            return Response({"detail": "ID is required."}, status=405)

        employee = getattr(request.user, "employee_get", None)
        if not employee:
            return Response({"detail": "User not linked to Employee"}, status=400)

        req = AssetRequest.objects.filter(
            pk=pk, requested_employee_id=employee.id
        ).first()
        if not req:
            return Response({"detail": "Not found or not allowed."}, status=404)

        asset_category_id = request.data.get("asset_category_id")
        description = request.data.get("description")

        if asset_category_id:
            req.asset_category_id_id = asset_category_id  # ✅ direct FK update

        if description is not None:
            req.description = description

        req.save()

        return Response(
            {
                "id": req.id,
                "asset_category_id": req.asset_category_id.id,
                "asset_category_name": req.asset_category_id.asset_category_name,
                "description": req.description,
                "status": req.asset_request_status,
                "request_date": req.asset_request_date,
            },
            status=200,
        )

    def delete(self, request, pk=None):
        if not pk:
            return Response(
                {"detail": "Method DELETE not allowed without ID."}, status=405
            )
        req = AssetRequest.objects.filter(
            pk=pk, requested_employee_id=request.user.employee_get
        ).first()
        if not req:
            return Response({"detail": "Not found or not allowed."}, status=404)
        req.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

# --- Asset Create/List/Update/Delete API ---
from asset.models import Asset, AssetCategory

from ...api_serializers.asset.serializers import AssetSerializer


class AssetCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Expected fields: asset_name, description, purchase_date, cost, status, asset_category_id
        data = request.data.copy()
        serializer = AssetSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        # Optional: filter by category id
        category_id = request.GET.get("category_id")
        queryset = Asset.objects.all()
        if category_id:
            queryset = queryset.filter(asset_category_id=category_id)
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = AssetSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def put(self, request, pk=None):
        if not pk:
            return Response(
                {"detail": "Method PUT not allowed without ID."}, status=405
            )
        asset = Asset.objects.filter(pk=pk).first()
        if not asset:
            return Response({"detail": "Not found."}, status=404)
        serializer = AssetSerializer(asset, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk=None):
        if not pk:
            return Response(
                {"detail": "Method DELETE not allowed without ID."}, status=405
            )
        asset = Asset.objects.filter(pk=pk).first()
        if not asset:
            return Response({"detail": "Not found."}, status=404)
        asset.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

# --- Asset Category API ---
from rest_framework.views import APIView

from asset.models import AssetCategory

from ...api_filters.asset.filters import AssetCategoryFilter
from ...api_serializers.asset.serializers import AssetCategorySerializer


class AssetCategoryAPIView(APIView):

    permission_classes = [IsAuthenticated]
    filterset_class = AssetCategoryFilter

    def get(self, request, pk=None):

        if pk:
            category = AssetCategory.objects.filter(pk=pk).first()
            if not category:
                return Response({"detail": "Not found."}, status=404)
            return Response(AssetCategorySerializer(category).data)
        queryset = AssetCategory.objects.all()
        filterset = self.filterset_class(request.GET, queryset=queryset)
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(filterset.qs, request)
        serializer = AssetCategorySerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = AssetCategorySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk=None):
        if not pk:
            return Response(
                {"detail": "Method PUT not allowed without ID."}, status=405
            )
        category = AssetCategory.objects.filter(pk=pk).first()
        if not category:
            return Response({"detail": "Not found."}, status=404)
        serializer = AssetCategorySerializer(category, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk=None):
        print("Delete called with pk:", pk)
        if not pk:
            return Response(
                {"detail": "Method DELETE not allowed without ID."}, status=405
            )
        category = AssetCategory.objects.filter(pk=pk).first()
        if not category:
            return Response({"detail": "Not found."}, status=404)
        category.delete()
        return Response(status=status.HTTP_200_OK)


from datetime import date

from django.http import QueryDict
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

# --- Optimized Asset APIs ---
from rest_framework.views import APIView

from asset.filters import AssetFilter
from asset.models import Asset, AssetAssignment, AssetCategory, AssetLot, AssetRequest

from ...api_filters.asset.filters import AssetCategoryFilter
from ...api_serializers.asset.serializers import *


class AssetDashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Asset dashboard summary: total, in use, available, requested."""
        total = Asset.objects.count()
        in_use = Asset.objects.filter(asset_status="In use").count()
        available = Asset.objects.filter(asset_status="Available").count()
        requested = AssetRequest.objects.filter(
            asset_request_status="Requested"
        ).count()
        return Response(
            {
                "total": total,
                "in_use": in_use,
                "available": available,
                "requested": requested,
            }
        )


class AssetViewAPIView(APIView):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_class = AssetFilter

    def get(self, request, pk=None):
        if pk:
            asset = Asset.objects.filter(pk=pk).first()
            if not asset:
                return Response({"detail": "Not found."}, status=404)
            return Response(AssetSerializer(asset).data)
        queryset = Asset.objects.all()
        filterset = self.filterset_class(request.GET, queryset=queryset)
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(filterset.qs, request)
        serializer = AssetGetAllSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AssetBatchAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        if pk:
            batch = AssetLot.objects.filter(pk=pk).first()
            if not batch:
                return Response({"detail": "Not found."}, status=404)
            return Response(AssetLotSerializer(batch).data)
        batches = AssetLot.objects.all()
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(batches, request)
        serializer = AssetLotSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AssetRequestAllocationAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        if pk:
            req = AssetRequest.objects.filter(pk=pk).first()
            if not req:
                return Response({"detail": "Not found."}, status=404)
            return Response(AssetRequestGetSerializer(req).data)
        requests = AssetRequest.objects.all().order_by("-id")
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(requests, request)
        serializer = AssetRequestGetSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = AssetRequestSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AssetHistoryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        if pk:
            assign = AssetAssignment.objects.filter(pk=pk).first()
            if not assign:
                return Response({"detail": "Not found."}, status=404)
            return Response(AssetAssignmentGetSerializer(assign).data)
        assignments = AssetAssignment.objects.all().order_by("-id")
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(assignments, request)
        serializer = AssetAssignmentGetSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AssetRejectAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_asset_request(self, pk):
        try:
            return AssetRequest.objects.get(pk=pk)
        except AssetRequest.DoesNotExist as e:
            raise serializers.ValidationError(e)

    def put(self, request, pk):
        asset_request = self.get_asset_request(pk)
        if asset_request.asset_request_status == "Requested":
            asset_request.asset_request_status = "Rejected"
            asset_request.save()
            return Response(status=204)
        raise serializers.ValidationError({"error": "Access Denied.."})


class AssetApproveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_asset_request(self, pk):
        try:
            return AssetRequest.objects.get(pk=pk)
        except AssetRequest.DoesNotExist as e:
            raise serializers.ValidationError(e)

    def put(self, request, pk):
        asset_request = self.get_asset_request(pk)
        if asset_request.asset_request_status == "Requested":
            data = request.data
            if isinstance(data, QueryDict):
                data = data.dict()
            data["assigned_to_employee_id"] = asset_request.requested_employee_id.id
            data["assigned_by_employee_id"] = request.user.employee_get.id
            serializer = AssetApproveSerializer(
                data=data, context={"asset_request": asset_request}
            )
            if serializer.is_valid():
                serializer.save()
                asset_id = Asset.objects.get(id=data["asset_id"])
                asset_id.asset_status = "In use"
                asset_id.save()
                asset_request.asset_request_status = "Approved"
                asset_request.save()
                return Response(status=200)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        raise serializers.ValidationError({"error": "Access Denied.."})


class AssetReturnAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_asset_assignment(self, pk):
        try:
            return AssetAssignment.objects.get(pk=pk)
        except AssetAssignment.DoesNotExist as e:
            raise serializers.ValidationError(e)

    def put(self, request, pk):
        asset_assignment = self.get_asset_assignment(pk)
        if request.user.has_perm("app_name.change_mymodel"):
            serializer = AssetReturnSerializer(
                instance=asset_assignment, data=request.data
            )
            if serializer.is_valid():
                images = [
                    ReturnImages.objects.create(image=image)
                    for image in request.data.getlist("image")
                ]
                asset_return = serializer.save()
                asset_return.return_images.set(images)
                if asset_return.return_status == "Healthy":
                    Asset.objects.filter(id=pk).update(asset_status="Available")
                else:
                    Asset.objects.filter(id=pk).update(asset_status="Not-Available")
                AssetAssignment.objects.filter(id=asset_return.id).update(
                    return_date=date.today()
                )
                return Response(status=200)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        else:
            AssetAssignment.objects.filter(id=pk).update(return_request=True)
            return Response(status=200)


from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from asset.models import AssetRequest


class AssetRequestAdminAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_staff:
            return Response({"detail": "Permission denied"}, status=403)

        requests = AssetRequest._base_manager.all().order_by("-id")  # ✅ bypass manager

        result = []
        for req in requests:
            result.append(
                {
                    "id": req.id,
                    "asset_category_name": req.asset_category_id.asset_category_name,
                    "status": req.asset_request_status,
                    "request_date": req.asset_request_date,
                    "request_username": (
                        req.requested_employee_id.get_full_name()
                        if hasattr(req.requested_employee_id, "get_full_name")
                        else str(req.requested_employee_id)
                    ),
                    "description": req.description,
                }
            )

        return Response(result, status=200)

    def put(self, request, pk=None):
        if not request.user.is_staff:
            return Response({"detail": "Permission denied"}, status=403)

        if not pk:
            return Response({"detail": "ID is required."}, status=400)

        req = AssetRequest.objects.filter(id=pk).first()
        if not req:
            return Response({"detail": "Request not found."}, status=404)

        status_val = request.data.get("asset_request_status")

        if not status_val:
            return Response({"detail": "asset_request_status is required"}, status=400)

        if status_val not in ["Requested", "Approved", "Rejected"]:
            return Response({"detail": "Invalid status value"}, status=400)

        req.asset_request_status = status_val
        req.save()

        return Response(
            {
                "id": req.id,
                "asset_category_name": req.asset_category_id.asset_category_name,
                "status": req.asset_request_status,
                "request_date": req.asset_request_date,
                "request_username": req.requested_employee_id.get_full_name(),
                "description": req.description,
            },
            status=200,
        )

    def delete(self, request, pk=None):
        if not request.user.is_staff:
            return Response({"detail": "Permission denied"}, status=403)

        if not pk:
            return Response({"detail": "ID is required."}, status=400)

        req = AssetRequest._base_manager.filter(id=pk).first()
        if not req:
            return Response({"detail": "Request not found."}, status=404)

        req.delete()
        return Response({"detail": "Request deleted successfully"}, status=200)
