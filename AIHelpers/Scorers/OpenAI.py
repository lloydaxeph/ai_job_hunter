import os
import json

from dotenv import load_dotenv
from openai import OpenAI


class AiJobScorer:
    def __init__(self, cfg: dict):
        load_dotenv()

        self.cfg = cfg
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    def score_job(self, job: dict) -> dict:
        """Ask GPT to score relevance 1-10 and return reasoning."""
        profile = self.cfg["ai"]["profile"]
        skills = self.cfg["ai"]["skills"]
        yoe = self.cfg["ai"]["years_experience"]

        prompt = f"""
        You are an experienced technical recruiter evaluating whether a software engineer should apply for a job.

        Candidate Profile:
        {profile}

        Candidate skills:
        {skills}

        Candidate experience:
        {yoe} years

        Job Title:
        {job["title"]}

        Company:
        {job["company"]}

        Job Description:
        {job.get("description", "")[:3000]}

        Evaluate the overall fit rather than exact keyword matches.

        Guidelines:

        - Do NOT require an exact technology match.
        - Closely related technologies are considered strong matches.
          Examples:
          - C++ ↔ C#
          - Django ↔ FastAPI
          - React ↔ Angular
          - PostgreSQL ↔ MySQL
          - AWS ↔ GCP
          - TensorFlow ↔ PyTorch
          - Docker ↔ Kubernetes
          - Computer Vision ↔ Machine Learning
          - MLOps ↔ ModelOps
          - Selenium ↔ Playwright

        - Assume an experienced software engineer can learn a similar framework or language quickly.

        - Years of experience are flexible.
          A candidate should NOT be heavily penalized if they are within approximately
          3 years below or 5 years above the requested experience.

        - Give more weight to:
          * overall engineering experience
          * problem-solving ability
          * transferable technical skills
          * relevant domain experience
          * AI / ML / backend / cloud experience when applicable

        - Give less weight to:
          * missing individual frameworks
          * exact tool names
          * buzzword mismatches

        Scoring guide:

        10 = Excellent fit. Apply immediately.
        9 = Very strong fit. Only minor skill gaps.
        8 = Strong fit. A few missing technologies but easily learnable.
        7 = Good fit. Several transferable skills. Worth applying.
        6 = Reasonable fit. Some important gaps but still realistic.
        5 = Borderline. Could apply if interested.
        4 or below = Poor fit.

        Respond ONLY with valid JSON:

        {{
          "score": 8,
          "reason": "One concise sentence explaining the score.",
          "missing": ["important missing skill 1", "important missing skill 2"]
        }}
        """

        resp = self.client.chat.completions.create(
            model=self.cfg["ai"]["model"],
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            temperature=0,
            max_tokens=150,
        )

        raw = resp.choices[0].message.content.strip()

        try:
            return json.loads(raw)
        except Exception:
            return {
                "score": 0,
                "reason": "parse error",
                "missing": [],
            }