import logging
from django.shortcuts import render
from rest_framework import status, generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .serializers import RegisterSerializer, UserSerializer, CustomTokenObtainPairSerializer

logger = logging.getLogger("apps.authentication")

class RegisterView(generics.CreateAPIView):
    # Register a new user account. Returns the created user profile on success.

     permission_classes = [AllowAny]
     serializer_class = RegisterSerializer

     @swagger_auto_schema(
        operation_summary="Register a new user",
        operation_description="Creates a new user account. No authentication required.",
        responses={
            201: openapi.Response("User created", UserSerializer),
            400: "Validation error",
        },
    )
     
     def post(self, request, *args, **kwargs):
         serializer = self.get_serializer(data=request.data)
         serializer.is_valid(raise_exception=True)
         user = serializer.save()
         return Response(
            {
                "success": True,
                "message": "Account created successfully.",
                "data": UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class CustomTokenObtainPairView(TokenObtainPairView):
    # Obtain an access + refresh JWT token pair.

    serializer_class = CustomTokenObtainPairSerializer
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            logger.info("User logged in: username=%s", request.data.get("username"))
        return response
    
class LogoutView(APIView):
   #Blacklist the refresh token (logout).
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
    operation_summary="Logout — invalidate refresh token",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["refresh"],
        properties={"refresh": openapi.Schema(type=openapi.TYPE_STRING)},
    ),
    responses={200: "Logged out", 400: "Bad request"},
)

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"success": False, "error": {"code": "bad_request", "message": "refresh token is required."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            pass  # Token already invalid — still return 200
        logger.info("User logged out: id=%s", request.user.id)
        return Response({"success": True, "message": "Logged out successfully."})
    
class ProfileView(generics.RetrieveUpdateAPIView):
    # Get or update the authenticated user's profile
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    @swagger_auto_schema(operation_summary="Get current user profile")
    def get(self, request, *args, **kwargs):
        serializer = self.get_serializer(request.user)
        return Response({"success": True, "data": serializer.data})

    @swagger_auto_schema(operation_summary="Update current user profile")
    def patch(self, request, *args, **kwargs):
        serializer = self.get_serializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"success": True, "data": serializer.data})

    def get_object(self):
        return self.request.user
