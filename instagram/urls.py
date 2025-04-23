from django.urls import path
from . import views

urlpatterns = [
    path('', views.AnalyzePostsView.as_view(), name='upload_csv'),
    path('export_excel/', views.export_excel, name='export_excel'),
]