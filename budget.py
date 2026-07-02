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

async def list_budgets_impl(
    conn,
    user_id: int,
    budget_type: str = None,
    category: str = None,
    subcategory: str = None,
    period: str = None
) -> list:
    matched_cat = None
    matched_sub = None
    
    if category:
        try:
            matched_cat, matched_sub = validate_category_and_subcategory(category, subcategory)
        except ValueError:
            return []

    query = (
        "SELECT id, budget_type, category, subcategory, amount, period, "
        "start_date::text, end_date::text FROM budgets WHERE user_id = $1"
    )
    params = [user_id]
    param_idx = 2
    
    if budget_type:
        query += f" AND budget_type = ${param_idx}"
        params.append(budget_type)
        param_idx += 1
        
    if matched_cat:
        query += f" AND category = ${param_idx}"
        params.append(matched_cat)
        param_idx += 1
        
    if matched_sub:
        query += f" AND subcategory = ${param_idx}"
        params.append(matched_sub)
        param_idx += 1
        
    if period:
        query += f" AND period = ${param_idx}"
        params.append(period)
        param_idx += 1
        
    query += " ORDER BY id ASC"
    
    rows = await conn.fetch(query, *params)
    return [dict(row) for row in rows]

async def update_budgets_impl(
    conn,
    user_id: int,
    # Filters
    budget_ids: list[int] = None,
    filter_budget_type: str = None,
    filter_category: str = None,
    filter_subcategory: str = None,
    filter_period: str = None,
    # Update Fields
    budget_type: str = None,
    amount: float = None,
    period: str = None,
    start_date: str = None,
    end_date: str = None,
    category: str = None,
    subcategory: str = None
) -> dict:
    # 1. Parameter Validation
    if not any([budget_ids, filter_budget_type, filter_category, filter_subcategory, filter_period]):
        return {
            "status": "error",
            "message": "At least one target filter must be specified."
        }
        
    if not any([budget_type is not None, amount is not None, period is not None, 
                start_date is not None, end_date is not None, category is not None, subcategory is not None]):
        return {
            "status": "error",
            "message": "At least one budget field must be specified to update."
        }

    # 2. Category & Subcategory normalizations for updates
    matched_update_cat = None
    matched_update_sub = None
    if category is not None or subcategory is not None:
        try:
            if subcategory is not None and category is None:
                raise ValueError("Cannot update subcategory without specifying the category.")
            matched_update_cat, matched_update_sub = validate_category_and_subcategory(category, subcategory)
        except ValueError as e:
            return {
                "status": "error",
                "message": f"Validation failed: {str(e)}"
            }

    # 3. Filter normalizations
    matched_filter_cat = None
    matched_filter_sub = None
    if filter_category:
        try:
            matched_filter_cat, matched_filter_sub = validate_category_and_subcategory(filter_category, filter_subcategory)
        except ValueError:
            # If the filter category is invalid, there won't be any matching budgets in the DB
            return {
                "status": "ok",
                "updated_count": 0,
                "updated_ids": []
            }

    # 4. Date validation
    try:
        parsed_start = pydate.fromisoformat(start_date) if start_date else None
        parsed_end = pydate.fromisoformat(end_date) if end_date else None
        if parsed_start and parsed_end and parsed_start > parsed_end:
            raise ValueError(f"start_date '{start_date}' cannot be after end_date '{end_date}'.")
    except Exception as e:
        return {
            "status": "error",
            "message": f"Date validation failed: {str(e)}"
        }

    # 5. Build dynamic SQL
    set_clauses = []
    params = []
    param_idx = 1

    # SET parameters
    if budget_type is not None:
        set_clauses.append(f"budget_type = ${param_idx}")
        params.append(budget_type)
        param_idx += 1
    if amount is not None:
        set_clauses.append(f"amount = ${param_idx}")
        params.append(float(amount))
        param_idx += 1
    if period is not None:
        set_clauses.append(f"period = ${param_idx}")
        params.append(period)
        param_idx += 1
    if start_date is not None:
        set_clauses.append(f"start_date = ${param_idx}")
        params.append(parsed_start)
        param_idx += 1
    if end_date is not None:
        set_clauses.append(f"end_date = ${param_idx}")
        params.append(parsed_end)
        param_idx += 1
    if category is not None:
        set_clauses.append(f"category = ${param_idx}")
        params.append(matched_update_cat)
        param_idx += 1
    if subcategory is not None:
        set_clauses.append(f"subcategory = ${param_idx}")
        params.append(matched_update_sub)
        param_idx += 1
        
    set_clauses.append("updated_at = CURRENT_TIMESTAMP")

    # WHERE parameters (user restriction is always present)
    where_clauses = [f"user_id = ${param_idx}"]
    params.append(user_id)
    param_idx += 1

    if budget_ids:
        where_clauses.append(f"id = ANY(${param_idx}::integer[])")
        params.append(budget_ids)
        param_idx += 1
    if filter_budget_type:
        where_clauses.append(f"budget_type = ${param_idx}")
        params.append(filter_budget_type)
        param_idx += 1
    if matched_filter_cat:
        where_clauses.append(f"category = ${param_idx}")
        params.append(matched_filter_cat)
        param_idx += 1
    if matched_filter_sub:
        where_clauses.append(f"subcategory = ${param_idx}")
        params.append(matched_filter_sub)
        param_idx += 1
    if filter_period:
        where_clauses.append(f"period = ${param_idx}")
        params.append(filter_period)
        param_idx += 1

    query = f"UPDATE budgets SET {', '.join(set_clauses)} WHERE {' AND '.join(where_clauses)} RETURNING id"

    try:
        rows = await conn.fetch(query, *params)
        updated_ids = [row["id"] for row in rows]
        return {
            "status": "ok",
            "updated_count": len(updated_ids),
            "updated_ids": updated_ids
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Update failed: {str(e)}"
        }

