"""Public pages plus the access-controlled dashboard."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render


def home(request):
    return render(request, "pages/home.html")


def about(request):
    return render(request, "pages/about.html")


def contact(request):
    return render(request, "pages/contact.html")


# SERVER-SIDE access control. @login_required is the real gate: an anonymous
# user who types /dashboard/ directly is redirected to LOGIN_URL with a ?next=
# parameter — they never see the page. Hiding the nav link in the template is
# only cosmetic and is NOT relied on for security; this decorator is.
@login_required
def dashboard(request):
    return render(request, "pages/dashboard.html")
