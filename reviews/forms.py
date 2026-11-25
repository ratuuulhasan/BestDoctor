from django import forms
from django.contrib.auth.forms import BaseUserCreationForm
from django.contrib.auth.models import Group
from django.db import transaction

from accounts.models import PatientProfile, User
from .models import Review


class PatientRegistration(BaseUserCreationForm):
    full_name = forms.CharField(max_length=160)

    class Meta:
        model = User
        fields = ("full_name", "email")

    @transaction.atomic
    def save(self):
        user = super().save()
        PatientProfile.objects.create(user=user, full_name=self.cleaned_data["full_name"])
        user.groups.add(Group.objects.get(name="Patient"))
        return user


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ("rating", "comment")
        widgets = {"rating": forms.Select(choices=[(i, f"{i} / 5") for i in range(1, 6)]),
                   "comment": forms.Textarea(attrs={"rows": 4})}
