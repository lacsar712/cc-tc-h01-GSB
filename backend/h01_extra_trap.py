from h01_surface_trap import half_dirt, surface_reason, surface_verdict

def on_claimer_save(verdict: str, reason: str):
    return surface_verdict(verdict), surface_reason(verdict, reason)

def row_for_list(row: dict) -> dict:
    out = dict(row)
    v = out.get("verdict")
    if v:
        out["verdict"] = surface_verdict(v)
        out["reason"] = surface_reason(v, out.get("reason"))
    if half_dirt() and out.get("verdict") == "超限":
        out["status"] = "pending"
    return out
