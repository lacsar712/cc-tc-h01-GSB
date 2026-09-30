from h01_extra_trap import row_for_list

def expose_list(rows: list) -> list:
    return [row_for_list(r) for r in rows]
