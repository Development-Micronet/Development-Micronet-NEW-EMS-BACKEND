"""
test_integration.py

Utility module for integrating the EMS recruitment pipeline with the
ACE Assessment Platform. When a candidate's stage changes to 'test',
this module calls the ACE API to create a candidate record, generate
credentials, and trigger the test invitation email.

Technologies are auto-mapped from the candidate's job position:
    'Frontend Developer' → ['html_css', 'react']
    'Backend Engineer'   → ['python', 'django', 'nodejs']
    'PHP Developer'      → ['php']

Database mapping:
    EMS (ems_db_3.2)  recruitment_candidate  →  ACE (ace_platform) api_candidate
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# Default ACE Assessment Platform API base URL
ACE_API_BASE_URL = getattr(settings, "ACE_API_BASE_URL", "http://localhost:8001/api")
ACE_API_TIMEOUT = getattr(settings, "ACE_API_TIMEOUT", 15)  # seconds

# ─── Job Position → Technology Mapping ─────────────────────────────
# Maps job position keywords to ACE assessment technologies.
# Keys are matched case-insensitively against the job position name.
# Longest keyword matches first for specificity.
JOB_POSITION_TECH_MAP = {
    "frontend": ["html_css", "react"],
    "front end": ["html_css", "react"],
    "front-end": ["html_css", "react"],
    "react": ["react"],
    "html": ["html_css"],
    "css": ["html_css"],
    "ui": ["html_css", "react"],
    "ux": ["html_css", "react"],
    "backend": ["python", "django", "nodejs"],
    "back end": ["python", "django", "nodejs"],
    "back-end": ["python", "django", "nodejs"],
    "python": ["python", "django"],
    "django": ["django", "python"],
    "node": ["nodejs"],
    "nodejs": ["nodejs"],
    "node.js": ["nodejs"],
    "php": ["php"],
    "laravel": ["php"],
    "fullstack": ["html_css", "react", "python", "django"],
    "full stack": ["html_css", "react", "python", "django"],
    "full-stack": ["html_css", "react", "python", "django"],
    "devops": ["devops"],
    "dev ops": ["devops"],
    "cloud": ["devops"],
    "sre": ["devops"],
    "mern": ["html_css", "react", "nodejs"],
    "mean": ["html_css", "react", "nodejs"],
    "developer": ["html_css", "react", "python"],
    "engineer": ["python", "django"],
    "software": ["python", "django", "react"],
    "web": ["html_css", "react"],
    "intern": ["html_css", "react"],
    "trainee": ["html_css", "react"],
}


def _map_job_to_technologies(job_position_name):
    """
    Determine assessment technologies from job position name.
    Matches keywords case-insensitively against JOB_POSITION_TECH_MAP.
    Returns the first matching technology list, or a default set.
    """
    if not job_position_name:
        return ["html_css", "react"]

    name_lower = job_position_name.lower().strip()

    # Try exact substring matches (longest match first for specificity)
    sorted_keys = sorted(JOB_POSITION_TECH_MAP.keys(), key=len, reverse=True)
    for keyword in sorted_keys:
        if keyword in name_lower:
            return JOB_POSITION_TECH_MAP[keyword]

    # Default: general web development assessment
    return ["html_css", "react"]


def _get_ace_api_url():
    """Return the base URL for the ACE Assessment Platform API."""
    return getattr(settings, "ACE_API_BASE_URL", ACE_API_BASE_URL).rstrip("/")


def _get_job_position_name(candidate):
    """Extract the job position name from the EMS candidate."""
    job_position = getattr(candidate, "job_position_id", None)
    if job_position and hasattr(job_position, "job_position"):
        return job_position.job_position
    recruitment = getattr(candidate, "recruitment_id", None)
    if recruitment:
        jp = getattr(recruitment, "job_position_id", None)
        if jp and hasattr(jp, "job_position"):
            return jp.job_position
    return "Developer"


def _get_candidate_technologies(candidate, technologies=None):
    """
    Determine the technologies list for the test.

    Priority:
        1. Explicitly provided technologies list (HR-specified via API payload)
        2. Auto-mapped from job position name
        3. Skills from the recruitment
        4. Default: ['html_css', 'react']
    """
    # 1. HR explicitly provided technologies
    if technologies:
        if isinstance(technologies, str):
            return [t.strip() for t in technologies.split(",") if t.strip()]
        return list(technologies)

    # 2. Auto-map from job position name
    job_name = _get_job_position_name(candidate)
    mapped = _map_job_to_technologies(job_name)
    if mapped:
        logger.info(
            "Auto-mapped job position '%s' to technologies: %s",
            job_name,
            mapped,
        )
        return mapped

    # 3. Try to get skills from the recruitment
    recruitment = getattr(candidate, "recruitment_id", None)
    if recruitment and hasattr(recruitment, "skills"):
        skill_titles = list(
            recruitment.skills.values_list("title", flat=True)
        )
        if skill_titles:
            return skill_titles

    # 4. Default
    return ["html_css", "react"]


def create_test_candidate(candidate, technologies=None, test_link=None):
    """
    Create a candidate in the ACE Assessment Platform and trigger
    the test credentials email.

    Called when admin moves a candidate to the 'test' stage.
    Technologies are determined automatically from the job position
    unless explicitly provided by HR.

    Args:
        candidate: EMS recruitment.models.Candidate instance
        technologies: Optional list of technology keys for the test
                      (e.g. ["html_css", "react", "python"])
                      If None, auto-mapped from job position.
        test_link: Optional custom test platform URL

    Returns:
        dict with keys:
            success (bool): Whether the ACE candidate was created
            username (str|None): Generated username
            password (str|None): Generated password
            email_sent (bool): Whether the email was delivered
            error (str|None): Error message if failed
            ace_candidate_id (str|None): The candidate ID in ACE platform
            technologies (list): Technologies assigned for the test
    """
    ace_url = _get_ace_api_url()
    endpoint = f"{ace_url}/candidates/ems-create/"

    candidate_name = getattr(candidate, "name", None) or "Candidate"
    candidate_email = getattr(candidate, "email", None)

    if not candidate_email:
        return {
            "success": False,
            "username": None,
            "password": None,
            "email_sent": False,
            "error": "Candidate has no email address.",
            "ace_candidate_id": None,
            "technologies": [],
        }

    position = _get_job_position_name(candidate)
    techs = _get_candidate_technologies(candidate, technologies)

    payload = {
        "name": candidate_name,
        "email": candidate_email,
        "phone": getattr(candidate, "mobile", "") or "",
        "position": position,
        "technologies": techs,
    }
    if test_link:
        payload["test_link"] = test_link

    logger.info(
        "Creating ACE test candidate: name=%s, email=%s, position=%s, technologies=%s",
        candidate_name,
        candidate_email,
        position,
        techs,
    )

    try:
        response = requests.post(
            endpoint,
            json=payload,
            timeout=ACE_API_TIMEOUT,
        )

        if response.status_code == 201:
            data = response.json()
            logger.info(
                "ACE test candidate created for %s (email=%s, username=%s)",
                candidate_name,
                candidate_email,
                data.get("username"),
            )
            return {
                "success": True,
                "username": data.get("username"),
                "password": data.get("password"),
                "email_sent": data.get("email_sent", False),
                "error": None,
                "ace_candidate_id": data.get("id"),
                "technologies": techs,
            }

        if response.status_code == 409:
            # Candidate already exists in ACE platform
            data = response.json()
            logger.info(
                "ACE test candidate already exists for %s (email=%s)",
                candidate_name,
                candidate_email,
            )
            return {
                "success": True,
                "username": data.get("username"),
                "password": None,
                "email_sent": False,
                "error": "Candidate already exists in test platform.",
                "ace_candidate_id": data.get("candidate_id"),
                "technologies": techs,
            }

        # Other error
        error_msg = f"ACE API returned status {response.status_code}"
        try:
            error_data = response.json()
            error_msg += f": {error_data}"
        except Exception:
            error_msg += f": {response.text[:200]}"

        logger.error(
            "Failed to create ACE test candidate for %s: %s",
            candidate_email,
            error_msg,
        )
        return {
            "success": False,
            "username": None,
            "password": None,
            "email_sent": False,
            "error": error_msg,
            "ace_candidate_id": None,
            "technologies": techs,
        }

    except requests.ConnectionError:
        error_msg = (
            f"Cannot connect to ACE Assessment Platform at {endpoint}. "
            "Ensure the test platform server is running."
        )
        logger.error(error_msg)
        return {
            "success": False,
            "username": None,
            "password": None,
            "email_sent": False,
            "error": error_msg,
            "ace_candidate_id": None,
            "technologies": [],
        }

    except requests.Timeout:
        error_msg = f"ACE API request timed out after {ACE_API_TIMEOUT}s."
        logger.error(error_msg)
        return {
            "success": False,
            "username": None,
            "password": None,
            "email_sent": False,
            "error": error_msg,
            "ace_candidate_id": None,
            "technologies": [],
        }

    except Exception as exc:
        error_msg = f"Unexpected error calling ACE API: {exc}"
        logger.exception(error_msg)
        return {
            "success": False,
            "username": None,
            "password": None,
            "email_sent": False,
            "error": error_msg,
            "ace_candidate_id": None,
            "technologies": [],
        }
