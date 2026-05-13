import math


def calculate_unit_price(case_price: float, pack_qty: float, markup_pct: float = 37.0) -> dict:
    if not case_price or not pack_qty or pack_qty == 0:
        return {"unit_cost": 0, "retail_price": 0, "markup_pct": markup_pct}

    unit_cost = case_price / pack_qty
    retail_price = unit_cost * (1 + markup_pct / 100)
    retail_price = math.ceil(retail_price * 100) / 100

    return {
        "unit_cost": round(unit_cost, 2),
        "retail_price": round(retail_price, 2),
        "markup_pct": markup_pct,
    }
