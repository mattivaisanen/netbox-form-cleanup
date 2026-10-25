from django.urls import include, path

from utilities.urls import get_model_urls

from . import views  # noqa: F401 (registers the views)

APP = 'netbox_form_cleanup'

urlpatterns = [
    path('rules/', include(get_model_urls(APP, 'fieldrule', detail=False))),
    path('rules/<int:pk>/', include(get_model_urls(APP, 'fieldrule'))),
]
