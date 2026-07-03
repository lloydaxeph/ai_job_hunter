from dataclasses import asdict, dataclass, field
from datetime import datetime

from Constants import JobStatus


@dataclass
class JobObject:
    title: str
    company: str
    url: str
    site: str
    score: int = 0
    description: str = ""
    resume_used: str = "NA"
    date: datetime = field(default_factory=datetime.now)
    status: str = JobStatus.FOUND

    @property
    def job_id(self) -> str:
        title = self.title.lower().strip().replace(" ", "-")
        company = self.company.lower().strip().replace(" ", "-")

        return f"{title}_{company}"

    def to_dict(self) -> dict:
        data = asdict(self)
        data["job_id"] = self.job_id
        return data