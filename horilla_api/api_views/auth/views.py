from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import EmailMessage
from django.core import signing
from django.db.models import Q
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from drf_yasg import openapi
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from base.backends import ConfiguredEmailBackend
from base.models import BrevoEmailConfiguration
from horilla_api.docs import document_api
import logging
import requests
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from rest_framework import status

try:
    import sib_api_v3_sdk
    from sib_api_v3_sdk.models.send_smtp_email import SendSmtpEmail
    from sib_api_v3_sdk.rest import ApiException

    BREVO_SDK_AVAILABLE = True
except ImportError:
    BREVO_SDK_AVAILABLE = False
    ApiException = Exception

from ...api_serializers.auth.serializers import (
    ForgotPasswordRequestSerializer,
    GetEmployeeSerializer,
    LoginRequestSerializer,
    ResetPasswordRequestSerializer,
)


class LoginAPIView(APIView):
    permission_classes = [AllowAny]

    @document_api(
        operation_description="Authenticate user and return JWT access token with employee info",
        request_body=LoginRequestSerializer,
        responses={
            200: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "employee": openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            "id": openapi.Schema(type=openapi.TYPE_INTEGER),
                            "full_name": openapi.Schema(type=openapi.TYPE_STRING),
                            "employee_profile": openapi.Schema(
                                type=openapi.TYPE_STRING,
                                description="Profile image URL",
                            ),
                        },
                    ),
                    "access": openapi.Schema(
                        type=openapi.TYPE_STRING, description="JWT access token"
                    ),
                    "refresh": openapi.Schema(
                        type=openapi.TYPE_STRING, description="JWT refresh token"
                    ),
                    "face_detection": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    "face_detection_image": openapi.Schema(
                        type=openapi.TYPE_STRING,
                        description="Face detection image URL",
                        nullable=True,
                    ),
                    "geo_fencing": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    "company_id": openapi.Schema(
                        type=openapi.TYPE_INTEGER, nullable=True
                    ),
                },
            ),
        },
        tags=["auth"],
    )
    def post(self, request):
        if "username" and "password" in request.data.keys():
            username = request.data.get("username")
            password = request.data.get("password")
            user = authenticate(username=username, password=password)
            if user:

                # Try to get employee, but make it optional
                employee = None
                try:
                    employee = user.employee_get
                except:
                    pass

                if employee and getattr(employee, "is_deleted", False):
                    return Response(
                        {"error": "This employee account has been deleted."},
                        status=403,
                    )

                refresh = RefreshToken.for_user(user)
                # If no employee, return basic login response
                if not employee:
                    return Response(
                        {
                            "access": str(refresh.access_token),
                            "refresh": str(refresh),
                            "message": "Logged in successfully. No employee record associated with this user.",
                        },
                        status=200,
                    )

                face_detection = False
                face_detection_image = None
                geo_fencing = False
                company_id = None
                try:
                    face_detection = employee.get_company().face_detection.start
                except:
                    pass
                try:
                    geo_fencing = employee.get_company().geo_fencing.start
                except:
                    pass
                try:
                    face_detection_image = employee.face_detection.image.url
                except:
                    pass
                try:
                    company_id = employee.get_company().id
                except:
                    pass

                try:
                    emp_role = employee.role
                except:
                    emp_role = None
                result = {
                    "employee": GetEmployeeSerializer(employee).data,
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                    "face_detection": face_detection,
                    "face_detection_image": face_detection_image,
                    "geo_fencing": geo_fencing,
                    "company_id": company_id,
                    "role": emp_role,
                }
                return Response(result, status=200)
            else:
                return Response({"error": "Invalid credentials"}, status=401)
        else:
            return Response({"error": "Please provide Username and Password"})


# class ForgotPasswordAPIView(APIView):
#     permission_classes = [AllowAny]

#     def _get_brevo_sender(self):
#         api_key = getattr(settings, "BREVO_API_KEY", "").strip()
#         from_email = getattr(settings, "BREVO_FROM_EMAIL", "").strip()
#         from_name = getattr(settings, "BREVO_FROM_NAME", "").strip()

#         if api_key:
#             return {
#                 "api_key": api_key,
#                 "from_email": from_email or "noreply@horilla.com",
#                 "from_name": from_name or "HR Management",
#             }

#         brevo_config = BrevoEmailConfiguration.objects.filter(is_active=True).first()
#         if brevo_config:
#             return {
#                 "api_key": brevo_config.api_key,
#                 "from_email": brevo_config.from_email,
#                 "from_name": brevo_config.from_name,
#             }
#         return None

#     def _send_with_brevo(self, to_email, subject, text_body, reset_link):
#         if not BREVO_SDK_AVAILABLE:
#             return False
#         sender = self._get_brevo_sender()
#         if not sender:
#             return False

#         try:
#             configuration = sib_api_v3_sdk.Configuration()
#             configuration.api_key["api-key"] = sender["api_key"]
#             api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
#                 sib_api_v3_sdk.ApiClient(configuration)
#             )
#             html_body = (
#                 "<p>You requested a password reset.</p>"
#                 f"<p><a href=\"{reset_link}\">Reset your password</a></p>"
#                 "<p>If you did not request this, you can safely ignore this email.</p>"
#             )
#             payload = SendSmtpEmail(
#                 sender={
#                     "name": sender["from_name"],
#                     "email": sender["from_email"],
#                 },
#                 to=[{"email": to_email}],
#                 subject=subject,
#                 text_content=text_body,
#                 html_content=html_body,
#             )
#             api_instance.send_transactional_email(payload)
#             return True
#         except ApiException:
#             return False

#     @document_api(
#         operation_description="Send password reset link to the user's email",
#         request_body=ForgotPasswordRequestSerializer,
#         responses={
#             200: openapi.Schema(
#                 type=openapi.TYPE_OBJECT,
#                 properties={
#                     "success": openapi.Schema(type=openapi.TYPE_BOOLEAN),
#                     "message": openapi.Schema(type=openapi.TYPE_STRING),
#                 },
#             ),
#         },
#         tags=["auth"],
#     )
#     def post(self, request):
#         serializer = ForgotPasswordRequestSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
#         email = serializer.validated_data["email"].strip().lower()

#         user = (
#             User.objects.filter(
#                 Q(username__iexact=email)
#                 | Q(email__iexact=email)
#                 | Q(employee_get__email__iexact=email)
#                 | Q(employee_get__employee_work_info__email__iexact=email)
#             )
#             .filter(is_active=True)
#             .first()
#         )

#         # Return a generic success response to avoid user enumeration.
#         success_response = {
#             "success": True,
#             "message": "If an account exists for this email, a reset link has been sent.",
#         }
#         if not user:
#             return Response(success_response, status=200)

#         recipient_email = (
#             getattr(getattr(user, "employee_get", None), "get_email", lambda: None)()
#             or user.email
#         )
#         if not recipient_email:
#             return Response(success_response, status=200)

#         uid = urlsafe_base64_encode(force_bytes(user.pk))
#         token = default_token_generator.make_token(user)

#         reset_base_url = getattr(settings, "FRONTEND_RESET_PASSWORD_URL", "").strip()
#         if not reset_base_url:
#             reset_base_url = (
#                 f"{request.scheme}://{request.get_host()}/auth/reset.html"
#             )
#         reset_link = f"{reset_base_url}?uid={uid}&token={token}"

#         subject = "Password Reset Request"
#         body = (
#             "You requested a password reset.\n\n"
#             f"Use the following link to reset your password:\n{reset_link}\n\n"
#             "If you did not request this, you can safely ignore this email."
#         )

#         sent_via_brevo = self._send_with_brevo(
#             to_email=recipient_email,
#             subject=subject,
#             text_body=body,
#             reset_link=reset_link,
#         )
#         if not sent_via_brevo:
#             email_backend = ConfiguredEmailBackend()
#             default_backend = "base.backends.ConfiguredEmailBackend"
#             configured_backend = getattr(settings, "EMAIL_BACKEND", "")
#             using_default_backend = not configured_backend or (
#                 configured_backend == default_backend
#             )
#             if using_default_backend and not email_backend.configuration:
#                 return Response(
#                     {"error": "Primary mail server is not configured."},
#                     status=503,
#                 )

#             from_email = getattr(
#                 email_backend, "dynamic_from_email_with_display_name", None
#             )
#             EmailMessage(
#                 subject=subject,
#                 body=body,
#                 from_email=from_email,
#                 to=[recipient_email],
#             ).send(fail_silently=False)

#         return Response(success_response, status=200)
logger = logging.getLogger(__name__)

class ForgotPasswordAPIView(APIView):
    permission_classes = [AllowAny]
    TOKEN_SALT = "horilla-api-password-reset"

    @classmethod
    def get_reset_token_timeout(cls):
        return int(getattr(settings, "PASSWORD_RESET_TIMEOUT", 300))

    @classmethod
    def make_reset_token(cls, user):
        return signing.dumps(
            {
                "uid": user.pk,
                "password": user.password,
            },
            salt=cls.TOKEN_SALT,
        )

    # ==============================
    # Get Brevo Credentials
    # ==============================
    def _get_brevo_sender(self):
        api_key = getattr(settings, "BREVO_API_KEY", "").strip()
        from_email = getattr(settings, "BREVO_FROM_EMAIL", "").strip()
        from_name = getattr(settings, "BREVO_FROM_NAME", "").strip()

        # Priority 1: .env settings
        if api_key:
            logger.info("Using Brevo credentials from settings (.env)")
            return {
                "api_key": api_key,
                "from_email": from_email or "noreply@horilla.com",
                "from_name": from_name or "HR Management",
            }

        # Priority 2: Database config
        brevo_config = BrevoEmailConfiguration.objects.filter(is_active=True).first()
        if brevo_config:
            logger.info("Using Brevo credentials from database")
            return {
                "api_key": brevo_config.api_key,
                "from_email": brevo_config.from_email,
                "from_name": brevo_config.from_name,
            }

        logger.warning("No Brevo configuration found")
        return None

    # ==============================
    # Send Email via Brevo
    # ==============================
    def _send_with_brevo(self, to_email, subject, text_body, reset_link, uid, token):
        sender = self._get_brevo_sender()
        if not sender:
            return False

        try:
            expiry_minutes = max(1, self.get_reset_token_timeout() // 60)
            html_body = f"""
                <p>You requested a password reset.</p>
                <p>
                    <a href="{reset_link}"
                       style="padding:10px 15px;
                              background:#4CAF50;
                              color:white;
                              text-decoration:none;">
                        Reset your password
                    </a>
                </p>
                <p>This reset link will expire in {expiry_minutes} minutes.</p>
                <p><strong>UID:</strong> {uid}</p>
                <p><strong>Token:</strong> {token}</p>
                <p>If you did not request this, you can ignore this email.</p>
            """

            if BREVO_SDK_AVAILABLE:
                configuration = sib_api_v3_sdk.Configuration()
                configuration.api_key["api-key"] = sender["api_key"]

                api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
                    sib_api_v3_sdk.ApiClient(configuration)
                )

                payload = SendSmtpEmail(
                    sender={
                        "name": sender["from_name"],
                        "email": sender["from_email"],
                    },
                    to=[{"email": to_email}],
                    subject=subject,
                    text_content=text_body,
                    html_content=html_body,
                )

                if hasattr(api_instance, "send_transactional_email"):
                    api_instance.send_transactional_email(payload)
                else:
                    api_instance.send_transac_email(payload)
            else:
                # SDK-free fallback path using Brevo REST API directly.
                response = requests.post(
                    "https://api.brevo.com/v3/smtp/email",
                    headers={
                        "accept": "application/json",
                        "api-key": sender["api_key"],
                        "content-type": "application/json",
                    },
                    json={
                        "sender": {
                            "name": sender["from_name"],
                            "email": sender["from_email"],
                        },
                        "to": [{"email": to_email}],
                        "subject": subject,
                        "textContent": text_body,
                        "htmlContent": html_body,
                    },
                    timeout=20,
                )
                response.raise_for_status()
            logger.info(f"Password reset email sent via Brevo to {to_email}")
            return True

        except ApiException as e:
            logger.exception(f"Brevo API error: {str(e)}")
            return False

        except Exception as e:
            logger.exception(f"Unexpected Brevo error: {str(e)}")
            return False

    # ==============================
    # POST Endpoint
    # ==============================
    @document_api(
        operation_description="Send password reset link to the user's email",
        request_body=ForgotPasswordRequestSerializer,
        responses={
            200: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "success": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    "message": openapi.Schema(type=openapi.TYPE_STRING),
                },
            ),
        },
        tags=["auth"],
    )
    def post(self, request):
        serializer = ForgotPasswordRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()

        # Prevent user enumeration
        success_response = {
            "success": True,
            "message": "If an account exists for this email, a reset link has been sent.",
        }

        user = (
            User.objects.filter(
                Q(username__iexact=email)
                | Q(email__iexact=email)
                | Q(employee_get__email__iexact=email)
                | Q(employee_get__employee_work_info__email__iexact=email)
            )
            .filter(is_active=True)
            .first()
        )

        if not user:
            return Response(success_response, status=status.HTTP_200_OK)

        recipient_email = (
            getattr(getattr(user, "employee_get", None), "get_email", lambda: None)()
            or user.email
        )

        if not recipient_email:
            return Response(success_response, status=status.HTTP_200_OK)

        # Generate reset token
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = self.make_reset_token(user)

        reset_base_url = getattr(settings, "FRONTEND_RESET_PASSWORD_URL", "").strip()
        if not reset_base_url:
            reset_base_url = (
                f"{request.scheme}://{request.get_host()}/api/auth/reset-password/"
            )
        if ":uid" in reset_base_url and ":token" in reset_base_url:
            reset_link = (
                reset_base_url.replace(":uid", uid).replace(":token", token)
            )
        elif "{uid}" in reset_base_url and "{token}" in reset_base_url:
            reset_link = reset_base_url.format(uid=uid, token=token)
        else:
            parsed_url = urlparse(reset_base_url)
            query_params = dict(parse_qsl(parsed_url.query, keep_blank_values=True))
            query_params.update({"uid": uid, "token": token})
            reset_link = urlunparse(
                parsed_url._replace(query=urlencode(query_params, doseq=True))
            )

        subject = "Password Reset Request"
        body = (
            "You requested a password reset.\n\n"
            f"Use the following link to reset your password:\n{reset_link}\n\n"
            f"This reset link will expire in {self.get_reset_token_timeout() // 60 or 5} minutes.\n\n"
            f"UID: {uid}\n"
            f"Token: {token}\n\n"
            "If you did not request this, you can safely ignore this email."
        )

        # Try Brevo first
        sent_via_brevo = self._send_with_brevo(
            to_email=recipient_email,
            subject=subject,
            text_body=body,
            reset_link=reset_link,
            uid=uid,
            token=token,
        )

        # Fallback to Django email backend
        if not sent_via_brevo:
            try:
                email_backend = ConfiguredEmailBackend()
                from_email = getattr(
                    email_backend, "dynamic_from_email_with_display_name", None
                )

                EmailMessage(
                    subject=subject,
                    body=body,
                    from_email=from_email,
                    to=[recipient_email],
                ).send(fail_silently=False)

                logger.info(f"Password reset sent via fallback SMTP to {recipient_email}")

            except Exception as e:
                logger.exception(f"Fallback email failed: {str(e)}")
                # Still return success to avoid enumeration
                return Response(success_response, status=status.HTTP_200_OK)

        include_reset_debug_data = bool(
            getattr(
                settings,
                "RETURN_RESET_LINK_IN_FORGOT_PASSWORD_RESPONSE",
                getattr(settings, "DEBUG", False),
            )
        )
        if include_reset_debug_data:
            debug_response = dict(success_response)
            debug_response.update(
                {
                    "uid": uid,
                    "token": token,
                    "reset_link": reset_link,
                }
            )
            return Response(debug_response, status=status.HTTP_200_OK)

        return Response(success_response, status=status.HTTP_200_OK)


class ResetPasswordAPIView(APIView):
    permission_classes = [AllowAny]
    COOLDOWN_SECONDS = 300
    TOKEN_SALT = ForgotPasswordAPIView.TOKEN_SALT

    @staticmethod
    def _get_user_from_uid(uid):
        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            return User.objects.filter(pk=user_id, is_active=True).first()
        except Exception:
            return None

    @classmethod
    def get_reset_token_timeout(cls):
        return int(getattr(settings, "PASSWORD_RESET_TIMEOUT", 300))

    @classmethod
    def is_valid_reset_token(cls, user, uid, token):
        try:
            payload = signing.loads(
                token,
                salt=cls.TOKEN_SALT,
                max_age=cls.get_reset_token_timeout(),
            )
        except signing.SignatureExpired:
            return False, "This reset link has expired. Please request a new link."
        except signing.BadSignature:
            return False, "Invalid or expired reset link."

        if str(payload.get("uid")) != str(user.pk) or str(user.pk) != str(
            force_str(urlsafe_base64_decode(uid))
        ):
            return False, "Invalid or expired reset link."

        if payload.get("password") != user.password:
            return False, "Invalid or expired reset link."

        return True, None

    @document_api(
        operation_description="Reset password using uid/token and apply a 5-minute cooldown after success",
        request_body=ResetPasswordRequestSerializer,
        responses={
            200: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "success": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    "message": openapi.Schema(type=openapi.TYPE_STRING),
                },
            ),
            400: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "success": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    "message": openapi.Schema(type=openapi.TYPE_STRING),
                },
            ),
            429: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "success": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    "message": openapi.Schema(type=openapi.TYPE_STRING),
                },
            ),
        },
        tags=["auth"],
    )
    def post(self, request):
        serializer = ResetPasswordRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        user = self._get_user_from_uid(payload["uid"])
        if not user:
            return Response(
                {"success": False, "message": "Invalid or expired reset link."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        is_valid_token, token_error = self.is_valid_reset_token(
            user, payload["uid"], payload["token"]
        )
        if not is_valid_token:
            return Response(
                {"success": False, "message": token_error},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cooldown_key = f"password_reset_cooldown_user_{user.pk}"
        cooldown_until = cache.get(cooldown_key)
        if cooldown_until:
            remaining_seconds = int(cooldown_until - timezone.now().timestamp())
            if remaining_seconds > 0:
                return Response(
                    {
                        "success": False,
                        "message": f"Please wait {remaining_seconds} seconds before resetting password again.",
                    },
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )

        new_password = payload["new_password"]

        if user.check_password(new_password):
            return Response(
                {
                    "success": False,
                    "message": "New password must be different from your current password.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_password(new_password, user=user)
        except DjangoValidationError as exc:
            return Response(
                {"success": False, "message": " ".join(exc.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save(update_fields=["password"])
        cache.set(
            cooldown_key,
            timezone.now().timestamp() + self.COOLDOWN_SECONDS,
            timeout=self.COOLDOWN_SECONDS,
        )

        return Response(
            {"success": True, "message": "Password reset successfully."},
            status=status.HTTP_200_OK,
        )

    def put(self, request):
        return self.post(request)
