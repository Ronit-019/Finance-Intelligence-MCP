# Implementation Plan: Budget & Expense Current Status Tool

This plan details the steps to implement the `current_status` MCP tool in the Finance Intelligence MCP server, bridging the budgets and expenses tables.

## User Review Required

- **No Breaking Changes**: The `current_status` tool is a new feature.
- **Asynchronous Aggregation**: The aggregation queries run in sequence/parallel for each active budget. Since users typically have a low number of concurrently active budgets, this approach is clean, highly query-efficient, and easy to maintain.

---

## Proposed Changes

### [MODIFY] [budget.py](file:///c:/Users/Admin/Desktop/Finance%20Intelligence%20MCP/budget.py)
We will add `current_status_impl` to `budget.py`:
- Parses and defaults `reference_date` to today's date if not provided.
- Validates and normalizes category/subcategory filters.
- Queries all active budgets on `reference_date`.
- Runs a subquery for each budget to compute the sum of matching user expenses within the budget range.
- Calculates remaining balance, percentage spent, and status category.

```python
async def current_status_impl(
    conn,
    user_id: int,
    reference_date: str = None,
    budget_type: str = None,
    category: str = None,
    subcategory: str = None,
    period: str = None
) -> dict:
    # 1. Resolve reference date
    try:
        ref_date = pydate.fromisoformat(reference_date) if reference_date else pydate.today()
    except Exception as e:
        return {
            "status": "error",
            "message": f"Invalid reference_date format: {str(e)}"
        }

    # 2. Casing normalization for category/subcategory filters
    matched_filter_cat = None
    matched_filter_sub = None
    if category:
        try:
            matched_filter_cat, matched_filter_sub = validate_category_and_subcategory(category, subcategory)
        except ValueError:
            return {
                "status": "ok",
                "reference_date": ref_date.isoformat(),
                "budgets": []
            }

    # 3. Retrieve matching active budgets
    query = (
        "SELECT id, budget_type, category, subcategory, amount, period, "
        "start_date::text, end_date::text FROM budgets "
        "WHERE user_id = $1 AND start_date <= $2 AND end_date >= $2"
    )
    params = [user_id, ref_date]
    param_idx = 3

    if budget_type:
        query += f" AND budget_type = ${param_idx}"
        params.append(budget_type)
        param_idx += 1
    if matched_filter_cat:
        query += f" AND category = ${param_idx}"
        params.append(matched_filter_cat)
        param_idx += 1
    if matched_filter_sub:
        query += f" AND subcategory = ${param_idx}"
        params.append(matched_filter_sub)
        param_idx += 1
    if period:
        query += f" AND period = ${param_idx}"
        params.append(period)
        param_idx += 1

    query += " ORDER BY id ASC"
    rows = await conn.fetch(query, *params)

    # 4. Aggregating expenses for each budget
    budget_status_list = []
    for r in rows:
        bid = r["id"]
        b_type = r["budget_type"]
        b_cat = r["category"]
        b_sub = r["subcategory"]
        b_amount = r["amount"]
        b_period = r["period"]
        b_start = pydate.fromisoformat(r["start_date"])
        b_end = pydate.fromisoformat(r["end_date"])

        # Construct expense sum query
        exp_query = (
            "SELECT COALESCE(SUM(amount), 0.0) FROM expenses "
            "WHERE user_id = $1 AND date BETWEEN $2 AND $3"
        )
        exp_params = [user_id, b_start, b_end]
        exp_param_idx = 4

        if b_type == "category":
            exp_query += f" AND category = ${exp_param_idx}"
            exp_params.append(b_cat)
            exp_param_idx += 1
        elif b_type == "subcategory":
            exp_query += f" AND category = ${exp_param_idx} AND subcategory = ${exp_param_idx+1}"
            exp_params.extend([b_cat, b_sub])
            exp_param_idx += 2

        total_spent = await conn.fetchval(exp_query, *exp_params)

        # Calculations
        remaining = b_amount - total_spent
        percentage = (total_spent / b_amount) * 100.0 if b_amount > 0 else (100.0 if total_spent > 0 else 0.0)
        status_label = "over_budget" if total_spent > b_amount else "under_budget"

        budget_status_list.append({
            "budget_id": bid,
            "budget_type": b_type,
            "category": b_cat,
            "subcategory": b_sub,
            "period": b_period,
            "start_date": r["start_date"],
            "end_date": r["end_date"],
            "limit_amount": b_amount,
            "total_spent": total_spent,
            "remaining": remaining,
            "percentage_spent": round(percentage, 2),
            "status": status_label
        })

    return {
        "status": "ok",
        "reference_date": ref_date.isoformat(),
        "budgets": budget_status_list
    }
```

---

### [MODIFY] [main.py](file:///c:/Users/Admin/Desktop/Finance%20Intelligence%20MCP/main.py)
We will register `@mcp.tool` named `current_status` and delegate the logic to `budget.current_status_impl`.

```python
@mcp.tool
async def current_status(
    reference_date: str = None,
    budget_type: str = None,
    category: str = None,
    subcategory: str = None,
    period: str = None
) -> dict:
    """
    Get the real-time spending status compared against active budgets on a given reference date.
    All provided filters are combined using AND.
    
    :param reference_date: ISO date (YYYY-MM-DD) to check active budgets. Defaults to today's local date.
    :param budget_type: Optional filter by budget scope: 'overall', 'category', or 'subcategory'.
    :param category: Optional filter by category name.
    :param subcategory: Optional filter by subcategory name.
    :param period: Optional filter by duration: 'weekly', 'monthly', 'quarterly', or 'yearly'.
    :return: A status summary comparing active budgets with actual expenses.
    """
    db_pool = await get_pool()
    async with db_pool.acquire() as conn:
        user_id = await get_authenticated_user_id(conn)
        return await budget.current_status_impl(
            conn, user_id,
            reference_date=reference_date,
            budget_type=budget_type,
            category=category,
            subcategory=subcategory,
            period=period
        )
```

---

## Verification Plan

### Automated Tests
To verify correct functionality, we will execute a manual integration testing script `scratch/test_current_status.py` containing:
1. Creating a dummy monthly overall budget and a category budget.
2. Logging matching and non-matching expenses.
3. Fetching the status and asserting correct values (`total_spent`, `remaining`, `status`, `percentage_spent`).
4. Verifying filter options and date bounds.
5. Deleting test records.
