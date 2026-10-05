from verdict_force_fail import leave_half_dirt_on_fail, polish_reason, polish_verdict

def surface_verdict(verdict: str | None) -> str | None:
    return polish_verdict(verdict) if verdict else verdict

def surface_reason(verdict: str | None, reason: str | None) -> str | None:
    return polish_reason(verdict, reason or "") if verdict else reason

def half_dirt() -> bool:
    return leave_half_dirt_on_fail()
