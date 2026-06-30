"""Accounts views — only signup is custom; login/logout use Django's views."""

from django.contrib.auth import login
from django.shortcuts import redirect, render

from .forms import SignupForm


def signup(request):
    """Register a new user, then log them in.

    On success we call Django's login(), which rotates the session key (session
    fixation defense) and establishes an authenticated session. The form does
    the password validation + Argon2 hashing; we never touch the raw password.
    """
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Specify the backend explicitly: with multiple AUTHENTICATION_
            # BACKENDS (axes + model backend) Django can't infer which one
            # authenticated this freshly-created user, so we name the model
            # backend that actually owns the credentials.
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            return redirect("dashboard")
    else:
        form = SignupForm()

    return render(request, "accounts/signup.html", {"form": form})
