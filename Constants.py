from enum import Enum

class JobStatus:
    FOUND = "found"
    APPLIED = "applied"
    NOT_QUICK_APPLY = "not_quick_apply"
    REQUIRES_MANUAL_REVIEW = "requires_manual_review"
    TOO_MANY_STEPS = "too_many_steps"
    FAILED = "failed"
    DID_NOT_MATCH = "did_not_match"


class JobAgentModes(Enum):
    QUICK_APPLY = "QUICK APPLY"
    MANUAL_REVIEW = "MANUAL REVIEW"
    NON_QUICK_APPLY = "NON-QUICK APPLY"
    FAILED = "FAILED RUNS"
    RERUN = "RERUN"

    def __str__(self):
        return self.value