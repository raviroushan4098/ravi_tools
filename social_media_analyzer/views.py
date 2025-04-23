# social_media_analyzer/views.py
from django.shortcuts import render

def dashboard(request):
    return render(request, 'dashboard.html')