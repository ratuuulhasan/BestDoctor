from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.generics import RetrieveAPIView
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts.models import User


class IdentitySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "first_name", "last_name")


class TokenResponse(serializers.Serializer):
    token = serializers.CharField()


class Login(ObtainAuthToken):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(responses=TokenResponse)
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class Identity(RetrieveAPIView):
    serializer_class = IdentitySerializer

    def get_object(self):
        return self.request.user


class RevokeToken(APIView):
    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=204)
