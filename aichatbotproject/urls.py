
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

# Swagger Schema 
schema_view = get_schema_view(
    openapi.Info(
        title="AI Chatbot API",
        default_version="v1",
        description=(
            "Production-ready AI-powered chatbot backend.\n\n"
            "## Authentication\n"
            "All endpoints (except `/api/auth/register/` and `/api/auth/token/`) "
            "require a Bearer JWT token in the `Authorization` header.\n\n"
            "## Flow\n"
            "1. Register → `POST /api/auth/register/`\n"
            "2. Login → `POST /api/auth/token/` → get `access` token\n"
            "3. Create session → `POST /api/chat/sessions/`\n"
            "4. Send message → `POST /api/chat/sessions/{id}/messages/`\n"
        ),
        contact=openapi.Contact(email="support@chatbot.example.com"),
        license=openapi.License(name="MIT License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('auth/', include('authentication.urls')),
    
    # Chat endpoints
    path("api/chat/", include("chat.urls")),

    # Swagger docs
    path("api/docs/", schema_view.with_ui("swagger", cache_timeout=0), name="schema-swagger-ui"),
    path("api/redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
    path("api/schema.json", schema_view.without_ui(cache_timeout=0), name="schema-json"),
]
