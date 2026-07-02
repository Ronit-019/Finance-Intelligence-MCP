import os
import json
from datetime import date as pydate

CATEGORIES_PATH = os.path.join(os.path.dirname(__file__), "categories.json")

def validate_category_and_subcategory(category: str = None, subcategory: str = None):
    if category is None:
        return None, None
    
    if not os.path.exists(CATEGORIES_PATH):
        valid_categories = ["Food", "Travel", "Utilities", "Entertainment", "Health", "Other"]
        matched_cat = next((c for c in valid_categories if c.lower() == category.lower()), None)
        if matched_cat is None:
            raise ValueError(f"Category '{category}' is invalid. Allowed: {valid_categories}")
        return matched_cat, None

    with open(CATEGORIES_PATH, 'r', encoding="utf-8") as f:
        data = json.load(f)
        
    categories_lower = {k.lower(): k for k in data.keys()}
    category_lower = category.lower()
    
    if category_lower not in categories_lower:
        raise ValueError(f"Category '{category}' is invalid.")
        
    matched_category_key = categories_lower[category_lower]
    
    matched_subcategory = None
    if subcategory:
        subcats_lower = {s.lower(): s for s in data[matched_category_key]}
        subcat_lower = subcategory.lower()
        if subcat_lower not in subcats_lower:
            raise ValueError(f"Subcategory '{subcategory}' is invalid for category '{matched_category_key}'.")
        matched_subcategory = subcats_lower[subcat_lower]
        
    return matched_category_key, matched_subcategory

async def create_budget_impl(
    conn,
    user_id: int,
    budget_type: str = None,
    amount: float = None,
    period: str = None,
    start_date: str = None,
    end_date: str = None,
    category: str = None,
    subcategory: str = None,
    budgets: list[dict] = None
) -> dict:
    budget_list = []
    if budgets is not None:
        budget_list = budgets
    else:
        if budget_type is None or amount is None or period is None or start_date is None or end_date is None:
            return {
                "status": "error",
                "message": (
                    "Either 'budgets' list must be provided, or all single budget parameters "
                    "(budget_type, amount, period, start_date, end_date) must be provided."
                )
            }
        budget_list = [{
            "budget_type": budget_type,
            "amount": amount,
            "period": period,
            "start_date": start_date,
            "end_date": end_date,
            "category": category,
            "subcategory": subcategory
        }]
        
    if not budget_list:
        return {
            "status": "error",
            "message": "No budgets specified to create."
        }
        
    validated_budgets = []
    try:
        for b in budget_list:
            b_type = b.get("budget_type")
            b_amount = b.get("amount")
            b_period = b.get("period")
            b_start = b.get("start_date")
            b_end = b.get("end_date")
            b_cat = b.get("category")
            b_subcat = b.get("subcategory")
            
            if not all([b_type, b_amount is not None, b_period, b_start, b_end]):
                raise ValueError("Missing required fields in budget details.")
                
            d_start = pydate.fromisoformat(b_start)
            d_end = pydate.fromisoformat(b_end)
            if d_start > d_end:
                raise ValueError(f"start_date '{b_start}' cannot be after end_date '{b_end}'.")
                
            matched_cat, matched_sub = validate_category_and_subcategory(b_cat, b_subcat)
            
            if b_type == "overall":
                if b_cat is not None or b_subcat is not None:
                    raise ValueError("Overall budget cannot have category or subcategory set.")
            elif b_type == "category":
                if b_cat is None:
                    raise ValueError("Category budget must specify a category.")
                if b_subcat is not None:
                    raise ValueError("Category budget cannot specify a subcategory.")
            elif b_type == "subcategory":
                if b_cat is None or b_subcat is None:
                    raise ValueError("Subcategory budget must specify both category and subcategory.")
                    
            validated_budgets.append({
                "budget_type": b_type,
                "amount": float(b_amount),
                "period": b_period,
                "start_date": d_start,
                "end_date": d_end,
                "category": matched_cat,
                "subcategory": matched_sub
            })
    except Exception as e:
        return {
            "status": "error",
            "message": f"Validation failed: {str(e)}"
        }
        
    created_ids = []
    async with conn.transaction():
        for vb in validated_budgets:
            bid = await conn.fetchval(
                """
                INSERT INTO budgets (user_id, budget_type, category, subcategory, amount, period, start_date, end_date)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
                """,
                user_id, vb["budget_type"], vb["category"], vb["subcategory"], vb["amount"], vb["period"], vb["start_date"], vb["end_date"]
            )
            created_ids.append(bid)
            
    return {
        "status": "ok",
        "created_count": len(created_ids),
        "created_ids": created_ids
    }
