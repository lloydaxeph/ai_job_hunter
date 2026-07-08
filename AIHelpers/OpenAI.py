import os
import json

from dotenv import load_dotenv
from openai import OpenAI


class AIHelper:
    def __init__(self, cfg: dict):
        load_dotenv()

        self.cfg = cfg
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    def answer_application_questions(
            self,
            questions: list[dict],
    ) -> list[dict]:
        ai_cfg = self.cfg["ai"]

        prompt = f"""
        You are completing a LinkedIn Easy Apply application.

        Candidate Information:
        {self.cfg["about_me"]}

        Answer ONLY using the information above.

        Rules:

        1. Never invent personal information.
        2. Never exaggerate qualifications or experience.
        3. If the question is asking about a technical skill or technology
           (for example: Python, JavaScript, React, AWS, Docker, Kubernetes,
           TensorFlow, SQL, etc.):

           - If the skill is explicitly mentioned in the candidate information,
             use the stated years of experience or estimate conservatively from
             the candidate's work history.

           - If the skill is NOT mentioned anywhere in the candidate information,
             answer with exactly "1" year of experience and set confidence to 95.

           - If you are unsure how many years of experience the candidate has with
             a mentioned technical skill, answer with exactly "1" year and set
             confidence to 95.

        4. For NON-technical questions (visa sponsorship, salary, disability,
           criminal record, military service, referrals, relocation, work
           authorization, etc.), answer ONLY if the candidate information clearly
           provides the answer.

        5. If you cannot answer a NON-technical question with at least 90%
           confidence, leave the answer blank and set confidence below 90.

        Questions:

        {json.dumps(questions, indent=2)}

        Return ONLY valid JSON.

        Schema:

        {{
            "answers": [
                {{
                    "id": "<field id>",
                    "answer": "<answer>",
                    "confidence": 95
                }}
            ]
        }}
        """

        resp = self.client.chat.completions.create(
            model=ai_cfg["model"],
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )

        raw = resp.choices[0].message.content.strip()

        try:
            return json.loads(raw)["answers"]

        except Exception:
            raise RuntimeError(f"Failed parsing AI response:\n{raw}")

    def score_job(self, job: dict) -> dict:
        """Ask GPT to score relevance 1-10 and return reasoning."""
        ai_cfg = self.cfg["ai"]

        summary = ai_cfg["personal_summary"]
        skills = ai_cfg["skills"]
        yoe = ai_cfg["years_experience"]
        education = ai_cfg.get("education", [])
        languages = ai_cfg.get("languages", [])
        work_experience = ai_cfg.get("work_experience", [])

        experience_text = "\n".join(
            f"- {job_entry['title']} at {job_entry['company']} "
            f"({job_entry['duration']}):\n{job_entry['details'].strip()}"
            for job_entry in work_experience
        )

        education_text = "\n".join(
            f"- {edu['degree']}, {edu['school']} ({edu.get('year', '')})"
            for edu in education
        )

        languages_text = ", ".join(languages)

        prompt = f"""
        You are an experienced technical recruiter evaluating whether a software engineer should apply for a job.

        Candidate Summary:
        {summary}

        Candidate Work Experience:
        {experience_text}

        Candidate Skills:
        {", ".join(skills)}

        Candidate Total Experience:
        {yoe} years

        Candidate Education:
        {education_text}

        Candidate Languages:
        {languages_text}

        Job Title:
        {job["title"]}
        Company:
        {job["company"]}
        Job Description:
        {job.get("description", "")[:3000]}

        Evaluate overall fit, not exact keyword matches. The candidate is not picky and
        learns new tools quickly, so do not penalize heavily for missing individual
        frameworks or tools if the underlying domain overlaps.

        Guidelines:
        - Do NOT require an exact technology match.
        - Closely related technologies count as strong matches (e.g. C++ ↔ C#,
          Django ↔ FastAPI, React ↔ Angular, PostgreSQL ↔ MySQL, AWS ↔ GCP,
          TensorFlow ↔ PyTorch, Docker ↔ Kubernetes, Selenium ↔ Playwright).
        - Years of experience are flexible: do not penalize heavily if the job asks
          for roughly 3 years below to 5 years above the candidate's experience.
        - Give more weight to: overall engineering experience, problem-solving ability,
          transferable technical skills, relevant domain experience, and actual
          work history relevance (check the candidate's listed work experience against
          the job's core responsibilities, not just the skills list).
        - Give less weight to: missing individual frameworks, exact tool names, buzzwords.

        Use the FULL 1-10 range. Do not default to the middle out of caution.
        A job should only score 6 or higher if the CORE responsibilities
        (not just a couple of buzzwords) overlap with the candidate's actual work
        experience or skill domain. A job in an unrelated field (e.g. pure sales,
        accounting, non-technical roles, or engineering domains with no software/
        automation/data component) should score 3 or below, even if a stray keyword
        matches.

        Scoring guide:
        10 = Excellent fit, directly matches multiple past roles. Apply immediately.
        9 = Very strong fit, minor skill gaps only.
        8 = Strong fit, core responsibilities align with work history, a few unfamiliar tools.
        7 = Good fit, meaningful overlap in domain and skills, some real gaps.
        6 = Reasonable fit, partial overlap, would require real ramp-up.
        5 = Borderline, some transferable skills but different core focus.
        4 = Weak fit, only surface-level or tangential overlap.
        3 or below = Poor fit, different domain or unrelated responsibilities.

        Respond ONLY with valid JSON in this exact schema:
        {{
          "score": <integer from 1 to 10>,
          "reason": "One concise sentence explaining the score.",
          "missing": ["important missing skill 1", "important missing skill 2"]
        }}
        """

        resp = self.client.chat.completions.create(
            model=ai_cfg["model"],
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=400,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content.strip()

        try:
            return json.loads(raw)
        except Exception as e:
            self.console.print(f"[red]JSON parse error: {e}[/red]")
            self.console.print(f"[yellow]Raw response: {raw}[/yellow]")
            return {
                "score": 0,
                "reason": "parse error",
                "missing": [],
            }