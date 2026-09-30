from h01_extra_trap import on_claimer_save
from verdict_force_fail import polish_verdict, should_force_fail

def test_force():
    assert should_force_fail("合格") is True
    assert polish_verdict("合格") == "超限"
    v, r = on_claimer_save("合格", "ok")
    assert v == "超限" and "旁路" in r
