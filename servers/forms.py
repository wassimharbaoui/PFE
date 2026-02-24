from django import forms
from .models import Server

class ServerForm(forms.ModelForm):
    databases = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'test1,test2,test3'}),
        label="Bases de données (séparées par une virgule)",
        required=False
    )
    password_input = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label="Mot de passe",
        required=True
    )

    class Meta:
        model = Server
        fields = ['name', 'ip_address', 'port', 'username', 'databases', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Serveur Production'}),
            'ip_address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '127.0.0.1'}),
            'port': forms.NumberInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'sa'}),
            'databases': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'test1,test2,test3'}),
        }