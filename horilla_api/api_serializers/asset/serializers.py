# from rest_framework import serializers

# from asset.models import *


# class AssetCategorySerializer(serializers.ModelSerializer):
#     asset_count = serializers.SerializerMethodField()

#     class Meta:
#         model = AssetCategory
#         exclude = ["created_at", "created_by", "company_id", "is_active"]

#     def get_asset_count(self, obj):
#         return obj.asset_set.all().count()


# class AssetCategoryMiniSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = AssetCategory
#         fields = ["id", "asset_category_name"]

#     def get_asset_count(self, obj):
#         return obj.asset_set.all().count()


# class AssetLotSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = AssetLot
#         fields = "__all__"


# class AssetGetAllSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Asset
#         fields = ["id", "asset_name", "asset_status"]


# class AssetSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Asset
#         fields = "__all__"
#         extra_kwargs = {
#             'asset_tracking_id': {'required': False, 'allow_null': True, 'allow_blank': True}
#         }


# class AssetAssignmentSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = AssetAssignment
#         fields = "__all__"


# class AssetAssignmentGetSerializer(serializers.ModelSerializer):
#     asset = serializers.SerializerMethodField()
#     asset_category = serializers.SerializerMethodField()
#     allocated_user = serializers.SerializerMethodField()

#     class Meta:
#         model = AssetAssignment
#         fields = [
#             "id",
#             "asset",
#             "asset_category",
#             "allocated_user",
#             "assigned_date",
#             "return_status",
#         ]

#     def get_asset(self, obj):
#         return obj.asset_id.asset_name

#     def get_asset_category(self, obj):
#         return obj.asset_id.asset_category_id.asset_category_name

#     def get_allocated_user(self, obj):
#         return EmployeeMiniSerializer(obj.assigned_to_employee_id).data


# class AssetRequestSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = AssetRequest
#         fields = "__all__"
# from rest_framework import serializers
# from asset.models import Asset, AssetCategory, AssetLot


# class AssetCategoryMiniSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = AssetCategory
#         fields = ["id", "asset_category_name"]


# class AssetLotMiniSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = AssetLot
#         fields = ["id", "lot_number"]


# class AssetSerializer(serializers.ModelSerializer):
#     asset_category_id = serializers.PrimaryKeyRelatedField(queryset=AssetCategory.objects.all())
#     asset_lot_number_id = serializers.PrimaryKeyRelatedField(
#         queryset=AssetLot.objects.all(), required=False, allow_null=True
#     )

#     class Meta:
#         model = Asset
#         fields = "__all__"
from rest_framework import serializers

from asset.models import Asset, AssetAssignment, AssetCategory, AssetLot, AssetRequest
from employee.models import Employee


# ---------------- Asset Category ----------------
class AssetCategorySerializer(serializers.ModelSerializer):
    asset_count = serializers.SerializerMethodField()

    class Meta:
        model = AssetCategory
        fields = [
            "id",
            "asset_category_name",
            "asset_category_description",
            "asset_count",
        ]

    def get_asset_count(self, obj):
        return obj.asset_set.count()


class AssetCategoryMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetCategory
        fields = ["id", "asset_category_name"]


# ---------------- Asset Lot ----------------
class AssetLotSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetLot
        fields = ["id", "lot_number", "lot_description"]


# ---------------- Employee Mini Serializer ----------------
class EmployeeMiniSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = ["id", "full_name"]

    def get_full_name(self, obj):
        return obj.get_full_name()


# ---------------- Asset ----------------
class AssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = "__all__"
        extra_kwargs = {
            "asset_tracking_id": {
                "required": False,
                "allow_null": True,
                "allow_blank": True,
            }
        }


class AssetGetAllSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = ["id", "asset_name", "asset_status"]


# ---------------- Asset Assignment ----------------
class AssetAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetAssignment
        fields = "__all__"


class AssetAssignmentGetSerializer(serializers.ModelSerializer):
    asset = serializers.SerializerMethodField()
    asset_category = serializers.SerializerMethodField()
    allocated_user = serializers.SerializerMethodField()

    class Meta:
        model = AssetAssignment
        fields = [
            "id",
            "asset",
            "asset_category",
            "allocated_user",
            "assigned_date",
            "return_status",
        ]

    def get_asset(self, obj):
        return obj.asset_id.asset_name

    def get_asset_category(self, obj):
        return obj.asset_id.asset_category_id.asset_category_name

    def get_allocated_user(self, obj):
        return EmployeeMiniSerializer(obj.assigned_to_employee_id).data


# ---------------- Asset Request ----------------
class AssetRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetRequest
        fields = [
            "id",
            "asset_category_id",
            "description",
            "asset_request_status",
            "asset_request_date",
        ]
        read_only_fields = ["asset_request_status", "asset_request_date"]
