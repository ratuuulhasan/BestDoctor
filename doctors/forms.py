from django import forms
from django.contrib.auth.forms import BaseUserCreationForm
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import transaction

from accounts.models import RepresentativeProfile, User
from referrals.models import Referral
from .models import DoctorProfile


class RegistrationForm(BaseUserCreationForm):
    referral_code = forms.UUIDField(required=False, label="Representative referral code (optional)")
    full_name = forms.CharField(max_length=160)
    bmdc_number = forms.CharField(label="BM&DC registration number", max_length=48)

    class Meta:
        model = User
        fields = ("full_name", "email", "bmdc_number", "referral_code")

    def clean_referral_code(self):
        code = self.cleaned_data.get("referral_code")
        if code and not RepresentativeProfile.objects.filter(
            referral_code=code, is_active=True, user__is_active=True, user__groups__name="Representative",
        ).exists():
            raise ValidationError("This referral code is unavailable.")
        return code

    def clean_email(self):
        value = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=value).exists():
            raise ValidationError("An account already uses this email.")
        return value

    def clean_bmdc_number(self):
        value = self.cleaned_data["bmdc_number"].upper()
        if DoctorProfile.objects.filter(bmdc_number=value).exists():
            raise ValidationError("This registration number is already recorded.")
        return value

    @transaction.atomic
    def save(self):
        user = super().save()
        user.groups.add(Group.objects.get(name="Doctor"))
        doctor = DoctorProfile.objects.create(
            user=user, full_name=self.cleaned_data["full_name"],
            bmdc_number=self.cleaned_data["bmdc_number"],
        )
        if code := self.cleaned_data.get("referral_code"):
            rep = RepresentativeProfile.objects.select_for_update().filter(
                referral_code=code, is_active=True, user__is_active=True, user__groups__name="Representative",
            ).first()
            if not rep:
                raise ValidationError("This referral code is unavailable.")
            Referral.objects.create(representative=rep, referred_doctor=doctor)
        return user


class ProfileForm(forms.ModelForm):
    def save(self, commit=True):
        doctor = super().save(commit=False)
        if commit:
            doctor.save(update_fields=[*self.Meta.fields, "updated_at"])
        return doctor

    class Meta:
        model = DoctorProfile
        fields = ("full_name", "designation", "biography", "gender", "experience_years", "profile_image")

    def clean_profile_image(self):
        image = self.cleaned_data.get("profile_image")
        if image and image.size > 5 * 1024 * 1024:
            raise ValidationError("Choose an image smaller than 5 MB.")
        return image
