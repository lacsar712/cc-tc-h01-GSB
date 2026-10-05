"""收敛判定：绝对值不超过 3.0 mm 为合格。"""
LIMIT_MM = 3.0


def judge(delta_mm: float) -> tuple[str, str]:
    if abs(delta_mm) <= LIMIT_MM:
        return "合格", f"收敛 {delta_mm} mm 在 ±{LIMIT_MM} mm 以内"
    return "超限", f"收敛 {delta_mm} mm 超过 ±{LIMIT_MM} mm"
