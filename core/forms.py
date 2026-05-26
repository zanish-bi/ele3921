from django import forms
from django.contrib.auth.models import User
from .models import Bid, ServiceListing, Review


class BidForm(forms.ModelForm):
    class Meta:
        model = Bid
        fields = ["proposed_price", "message"]


class ServiceListingForm(forms.ModelForm):
    class Meta:
        model = ServiceListing
        fields = ["category", "title", "description", "price", "is_remote"]


class UserRegisterForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    role = forms.ChoiceField(choices=[("student", "Student"), ("client", "Client")])

    class Meta:
        model = User
        fields = ["username", "password"]


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ["rating", "comment"]
