"""Authentication forms.

We build entirely on Django's built-in auth forms. We do NOT reimplement
password hashing, validation, or the login credential check — those are exactly
the things that are easy to get subtly, dangerously wrong.
"""

from django.contrib.auth.forms import AuthenticationForm, UserCreationForm


class SignupForm(UserCreationForm):
    """Account creation form.

    UserCreationForm already:
      * runs the password through AUTH_PASSWORD_VALIDATORS (length >= 12,
        not-common, not-all-numeric, not-similar-to-username),
      * confirms the password twice,
      * hashes it with Argon2 via set_password() on save.

    We subclass only to make this the explicit project signup form; no custom
    password handling is added.
    """

    class Meta(UserCreationForm.Meta):
        pass


class HardenedAuthenticationForm(AuthenticationForm):
    """Login form used by Django's LoginView.

    Django's AuthenticationForm is already safe in two ways we rely on:

    1. Generic error message. On a bad username OR a bad password it returns
       the SAME "Please enter a correct username and password" error. It never
       reveals whether the username exists, so an attacker can't enumerate
       valid usernames through the login form.

    2. It calls authenticate(request, ...) passing the request, which is what
       django-axes needs to attribute failed attempts to an IP and enforce
       lockouts.

    We subclass purely to document these guarantees and to give one explicit
    place to keep the error message generic.
    """

    error_messages = {
        **AuthenticationForm.error_messages,
        # Deliberately generic — same text whether the username is unknown or
        # the password is wrong.
        "invalid_login": "Please enter a correct username and password. "
        "Note that both fields may be case-sensitive.",
    }
