from django import forms
from django.contrib.auth.models import User
from .models import Bid, ServiceListing, Review, JobRequest, JobBid, ContractMessage


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


class JobRequestForm(forms.ModelForm):
    class Meta:
        model = JobRequest
        fields = ["category", "title", "description", "budget"]


class JobBidForm(forms.ModelForm):
    class Meta:
        model = JobBid
        fields = ["proposed_price", "message"]


class ContractMessageForm(forms.ModelForm):
    class Meta:
        model = ContractMessage
        fields = ["body"]
        widgets = {"body": forms.Textarea(attrs={"rows": 3, "placeholder": "Write a message…"})}
        labels = {"body": "Message"}
