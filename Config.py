import os
import yaml
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()


def load_config(config_path="config.yaml"):
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    cfg["credentials"] = {
        "linkedin_email": os.getenv("LINKEDIN_EMAIL", ""),
        "linkedin_password": os.getenv("LINKEDIN_PASSWORD", ""),
        "jobstreet_email": os.getenv("JOBSTREET_EMAIL", ""),
        "jobstreet_password": os.getenv("JOBSTREET_PASSWORD", ""),
        "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
    }

    # Normalize AI config
    ai = cfg.setdefault("ai", {})

    ai.setdefault("profile", "")
    ai.setdefault("skills", [])
    ai.setdefault("years_experience", 0)

    return cfg


def get_banned_companies(cfg):
    """Return banned companies from config."""
    return [company.lower() for company in cfg.get("banned", {}).get("companies", [])]

def get_banned_titles(cfg):
    return [title.lower() for title in cfg.get("banned", {}).get("titles", [])]


def pick_resume(job_title: str, cfg: dict) -> str:
    """
    Select the resume based only on the job title.

    The resume with the most matching keywords in the title wins.
    """

    resumes = cfg.get("resumes", [])

    if not resumes:
        raise ValueError("No Resumes configured.")

    title = job_title.lower()

    default_resume = None
    best_resume = None
    best_score = 0

    for resume in resumes:

        keywords = resume.get("use_when")

        if not keywords:
            default_resume = resume["file"]
            continue

        score = sum(
            keyword.lower() in title
            for keyword in keywords
        )

        if score > best_score:
            best_score = score
            best_resume = resume["file"]

    if best_resume:
        return best_resume

    if default_resume:
        return default_resume

    return resumes[0]["file"]