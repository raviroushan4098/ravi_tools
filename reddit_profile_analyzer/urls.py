# reddit_profile_analyzer/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('upload/', views.RedditProfileAnalyzerView.as_view(), name='reddit_profile_analyzer_upload'),
    path('analyze/', views.RedditProfileAnalyzerView.as_view(), name='reddit_profile_analyzer_results'), # You might combine upload and analyze in one view
    path('export/', views.export_to_excel_view, name='reddit_profile_analyzer_export'),
]