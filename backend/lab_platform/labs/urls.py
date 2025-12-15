from django.urls import path
from . import views

urlpatterns = [
    path('start/', views.start_lab, name='start'),
    path('validate/', views.validate_lab, name='validate'),
    path('reset/', views.reset_lab, name='reset'),
]