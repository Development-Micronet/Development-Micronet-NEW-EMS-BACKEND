from django.urls import path, re_path

from ...api_views.asset.views import (
    AssetBatchAPIView,
    AssetCategoryAPIView,
    AssetCreateAPIView,
    AssetDashboardAPIView,
    AssetHistoryAPIView,
    AssetRequestAdminAPIView,
    AssetRequestAllocationAPIView,
    AssetRequestUserAPIView,
    AssetViewAPIView,
)

urlpatterns = [
    path("dashboard/", AssetDashboardAPIView.as_view(), name="api-asset-dashboard"),
    re_path(r"^view/(?P<pk>\d+)?$", AssetViewAPIView.as_view(), name="api-asset-view"),
    re_path(
        r"^batches/(?P<pk>\d+)?$", AssetBatchAPIView.as_view(), name="api-asset-batches"
    ),
    re_path(
        r"^request-allocation/(?P<pk>\d+)?$",
        AssetRequestAllocationAPIView.as_view(),
        name="api-asset-request-allocation",
    ),
    re_path(
        r"^history/(?P<pk>\d+)?$",
        AssetHistoryAPIView.as_view(),
        name="api-asset-history",
    ),
    path("categories/", AssetCategoryAPIView.as_view(), name="api-asset-categories"),
    re_path(
        r"^categories/(?P<pk>\d+)?$",
        AssetCategoryAPIView.as_view(),
        name="api-asset-category-detail",
    ),
    path("create-asset/", AssetCreateAPIView.as_view(), name="api-asset-create"),
    re_path(
        r"^create-asset/(?P<pk>\d+)?$",
        AssetCreateAPIView.as_view(),
        name="api-asset-create-detail",
    ),
    path(
        "employee-asset-request/",
        AssetRequestUserAPIView.as_view(),
        name="api-employee-asset-request",
    ),
    re_path(
        r"^employee-asset-request/(?P<pk>\d+)?$",
        AssetRequestUserAPIView.as_view(),
        name="api-employee-asset-request-detail",
    ),
    path(
        "employee-asset-request/<int:pk>/",
        AssetRequestUserAPIView.as_view(),
        name="employee-asset-request-update",
    ),
    path(
        "admin-asset-request/",
        AssetRequestAdminAPIView.as_view(),
        name="admin-asset-request",
    ),
    path(
        "admin-asset-request/<int:pk>/",
        AssetRequestAdminAPIView.as_view(),
        name="admin-asset-request-update",
    ),
]
