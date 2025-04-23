from django.urls import path
from . import views  # Import your views module

urlpatterns = [
    path('', views.analyze_reddit_post, name='bulk_analyze'),  # For bulk analysis
    path('reddit/export-to-excel/', views.export_to_excel, name='export_to_excel'),
]
