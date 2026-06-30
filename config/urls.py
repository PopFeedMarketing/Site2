"""Root URL configuration.

Auth is wired to Django's built-in views/forms — we do NOT hand-roll login,
logout, session handling or password hashing. The only custom auth view is
signup, which itself just wraps Django's UserCreationForm.
"""

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from accounts.forms import HardenedAuthenticationForm
from accounts.views import signup
from pages.views import about, contact, dashboard, home

urlpatterns = [
    path("admin/", admin.site.urls),
    # Public pages
    path("", home, name="home"),
    path("about/", about, name="about"),
    path("contact/", contact, name="contact"),
    # Authenticated-only
    path("dashboard/", dashboard, name="dashboard"),
    # Auth: Django's built-in LoginView/LogoutView. We pass a custom form only
    # to route authentication through django-axes; everything else is stock.
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="accounts/login.html",
            authentication_form=HardenedAuthenticationForm,
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("signup/", signup, name="signup"),
]
