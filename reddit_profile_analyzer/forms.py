# reddit_profile_analyzer_django/forms.py
from django import forms

class UploadUsernamesCSVForm(forms.Form):
    csv_file = forms.FileField(
        label='Select CSV File with Usernames',
        widget=forms.FileInput(attrs={'accept': '.csv'})
    )