# Implementation Plan: List Budgets Tool

This plan details the implementation steps to add the `list_budgets` tool to the Expense Tracker MCP server, using a modular design.

## User Review Required
No breaking changes. The `list_budgets` tool is a new feature.

## Proposed Changes

### Modular Code Architecture

---

### [MODIFY] [budget.py](file:///c:/Users/Admin/Desktop/Finance%20Intelligence%20MCP/budget.py)
We will add `list_budgets_impl` to `budget.py`:
- Accepts filter arguments: `budget_type`, `category`, `subcategory`, and `period`.
- Corrects input casings using the `validate_category_and_subcategory` helper.
- Builds a dynamic database SELECT query on the `budgets` table.
- Restricts queried records to `user_id`.

```python
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
            # If the category is invalid, there won't be any matching budgets in the DB
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
```

---

### [MODIFY] [main.py](file:///c:/Users/Admin/Desktop/Finance%20Intelligence%20MCP/main.py)
We will register the `@mcp.tool` entrypoint and route it to `budget.list_budgets_impl` passing `conn` and `user_id`.

```python
@mcp.tool
async def list_budgets(
    budget_type: str = None,
    category: str = None,
    subcategory: str = None,
    period: str = None
) -> list:
    """
    List all budgets matching the optional filters.
    All provided filters are combined using AND.
    
    :param budget_type: Optional filter by scope: 'overall', 'category', or 'subcategory'.
    :param category: Optional filter by category name.
    :param subcategory: Optional filter by subcategory name.
    :param period: Optional filter by duration: 'weekly', 'monthly', 'quarterly', or 'yearly'.
    :return: A list of budgets matching the filters.
    """
    db_pool = await get_pool()
    async with db_pool.acquire() as conn:
        user_id = await get_authenticated_user_id(conn)
        return await budget.list_budgets_impl(
            conn, user_id,
            budget_type=budget_type,
            category=category,
            subcategory=subcategory,
            period=period
        )
```

---

## Verification Plan

### Manual Verification
We will manually verify the feature using a Python verification script:
1. **Setup**: Create 3 different budgets (overall, category 'Food', category 'Travel').
2. **List All**: Call `list_budgets()` with no filters and confirm all 3 are returned.
3. **Filter by Type**: Call `list_budgets(budget_type='overall')` and confirm only overall budget is returned.
4. **Filter by Category**: Call `list_budgets(category='food')` (checking casing normalization) and confirm Food budget is returned.
5. **Filter by Period**: Call `list_budgets(period='weekly')` and confirm correct results.
6. **Cleanup**: Delete all test records.
