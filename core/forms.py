from django import forms
from .models import Bid, ServiceListing


class BidForm(forms.ModelForm):
    class Meta:
        model = Bid
        fields = ["proposed_price", "message"]


class ServiceListingForm(forms.ModelForm):
    class Meta:
        model = ServiceListing
        fields = ["category", "title", "description", "price", "is_remote"]


from django.contrib.auth.models import User

class UserRegisterForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ["username", "password"]
