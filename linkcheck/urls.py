from django.urls import path

from . import views

urlpatterns = [
   path('coverage/', views.coverage, name='linkcheck_coverage'),
   path('', views.report, name='linkcheck_report'),
]
