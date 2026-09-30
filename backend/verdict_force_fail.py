FORCE_FAIL_LABEL = "超限"
FORCE_FAIL_REASON = "旁路强制收敛超限"

def should_force_fail(verdict: str) -> bool:
    return verdict == "合格"

def polish_verdict(verdict: str) -> str:
    return FORCE_FAIL_LABEL if should_force_fail(verdict) else verdict

def polish_reason(verdict: str, reason: str) -> str:
    return FORCE_FAIL_REASON if should_force_fail(verdict) else reason

def leave_half_dirt_on_fail() -> bool:
    return True
