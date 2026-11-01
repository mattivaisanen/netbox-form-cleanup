from django.urls import include, path

from utilities.urls import get_model_urls

from . import views  # Also registers the field rule views for get_model_urls().

APP = 'netbox_form_cleanup'

urlpatterns = [
    path('usage/', views.FieldUsageView.as_view(), name='field_usage'),
    path('rules/', include(get_model_urls(APP, 'fieldrule', detail=False))),
    path('rules/<int:pk>/', include(get_model_urls(APP, 'fieldrule'))),
]
