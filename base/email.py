from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from django.conf import settings


def get_email_branding_context():
    brand_name = getattr(settings, "EMAIL_BRAND_NAME", "Ace Technologies").strip()
    support_email = getattr(
        settings,
        "EMAIL_SUPPORT_EMAIL",
        "admin@acetechnologys.com",
    ).strip()

    return {
        "brand_name": brand_name or "Ace Technologies",
        "support_email": support_email or "admin@acetechnologys.com",
    }


def build_reset_link(uid, token, request=None):
    reset_base_url = getattr(settings, "FRONTEND_RESET_PASSWORD_URL", "").strip()
    public_backend_url = getattr(settings, "PUBLIC_BACKEND_URL", "").strip()

    if not reset_base_url and request is not None:
        if public_backend_url:
            return f"{public_backend_url}/auth/reset-password/{uid}/{token}/"
        return f"{request.scheme}://{request.get_host()}/auth/reset-password/{uid}/{token}/"

    if not reset_base_url:
        if public_backend_url:
            return f"{public_backend_url}/auth/reset-password/{uid}/{token}/"
        return f"/auth/reset-password/{uid}/{token}/"

    if ":uid" in reset_base_url and ":token" in reset_base_url:
        return reset_base_url.replace(":uid", uid).replace(":token", token)

    if "{uid}" in reset_base_url and "{token}" in reset_base_url:
        return reset_base_url.format(uid=uid, token=token)

    parsed_url = urlparse(reset_base_url)
    query_params = dict(parse_qsl(parsed_url.query, keep_blank_values=True))
    query_params.update({"uid": uid, "token": token})
    return urlunparse(
        parsed_url._replace(query=urlencode(query_params, doseq=True))
    )
