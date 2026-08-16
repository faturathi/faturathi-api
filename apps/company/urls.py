from rest_framework.routers import DefaultRouter

from .views import CompanyBranchViewSet, CompanyGroupViewSet, CustomerViewSet, EntityViewSet

router = DefaultRouter(trailing_slash=False)
router.register("entities", EntityViewSet, basename="entity")
router.register("customers", CustomerViewSet, basename="customer")
router.register("company-groups", CompanyGroupViewSet, basename="company-group")
router.register("branches", CompanyBranchViewSet, basename="company-branch")

urlpatterns = router.urls
