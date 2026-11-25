from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower
import uuid


class UserManager(BaseUserManager):
    use_in_migrations = True

    def get_by_natural_key(self, username):
        return self.get(email__iexact=username.strip())

    def create_user(self, email, password=None, **extra_fields):
        if not email or not email.strip():
            raise ValueError("An email address is required.")
        user = self.model(email=email.strip().lower(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        for field in ("is_staff", "is_superuser", "is_active"):
            if extra_fields.setdefault(field, True) is not True:
                raise ValueError(f"A superuser must have {field}=True.")
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=32, blank=True)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("email"), name="accounts_user_email_ci")
        ]

    def clean(self):
        super().clean()
        self.email = self.email.strip().lower()

    def __str__(self):
        return self.email


class PatientProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.PROTECT)
    full_name = models.CharField(max_length=160)

    def __str__(self):
        return self.full_name


class RepresentativeProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.PROTECT)
    referral_code = models.UUIDField(default=uuid.uuid4, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return str(self.user)
