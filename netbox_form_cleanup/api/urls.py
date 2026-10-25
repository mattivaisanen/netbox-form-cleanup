from netbox.api.routers import NetBoxRouter

from . import views

router = NetBoxRouter()
router.APIRootView = views.FormCleanupRootView
router.register('rules', views.FieldRuleViewSet)

urlpatterns = router.urls
