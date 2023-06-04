from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import *


class UserLoginForm(forms.Form):
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control','id':"username_id"}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))


class UserRegistrationForm(UserCreationForm):

    class Meta:
        model = User
        fields = ['username', 'password1', 'password2']



class SapConfigurationFORM(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(SapConfigurationFORM, self).__init__(*args, **kwargs)
        self.fields['saprouter'].required = False
    class Meta:
        model = SAPConfig
        fields = ['ASHOST', 'CLIENT', 'SYSNR', 'USER', 'PASSWD', 'saprouter']
        widgets = {
            'PASSWD': forms.PasswordInput(attrs={'placeholder': 'Password'}),
        }

class SapConfigurationEditFORM(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(SapConfigurationEditFORM, self).__init__(*args, **kwargs)
        self.fields['saprouter'].required = False
    class Meta:
        model = SAPConfig
        fields = ['ASHOST', 'CLIENT', 'SYSNR', 'USER', 'PASSWD', 'saprouter']
        widgets = {
            'ASHOST': forms.TextInput(attrs={"id":"edit_conf_ahost"}),
            'CLIENT': forms.TextInput(attrs={"id":"edit_conf_client"}),
            'SYSNR': forms.TextInput(attrs={"id":"edit_conf_sysnr"}),
            'USER': forms.TextInput(attrs={"id":"edit_conf_user"}),
            'saprouter': forms.TextInput(attrs={"id":"edit_conf_saprouter","required":False}),
            'PASSWD': forms.PasswordInput(attrs={'placeholder': 'Password',"id":"edit_conf_password"}),
        }