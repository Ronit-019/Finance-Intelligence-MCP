# Implementation Plan: Budget Deletion Tool

This plan details the steps to implement the `delete_budgets` MCP tool in the Finance Intelligence MCP server, allowing users to remove budget tracking limits.

## User Review Required

- **No Breaking Changes**: The `delete_budgets` tool is a new feature.
- **Safety Filters**: To prevent accidental deletion of all records, at least one filter target must be specified.

---

## Proposed Changes

### [MODIFY] [budget.py](file:///c:/Users/Admin/Desktop/Finance%20Intelligence%20MCP/budget.py)
We will add `delete_budgets_impl` to `budget.py`:
- Validates that at least one filter is specified.
- Validates and normalizes `category` and `subcategory` filters.
- Dynamically builds and executes a SQL `DELETE FROM budgets WHERE ... RETURNING id` statement.

```python
async def delete_budgets_impl(
    conn,
    user_id: int,
    budget_ids: list[int] = None,
    start_date: str = None,
    end_date: str = None,
    budget_type: str = None,
    category: str = None,
    subcategory: str = None,
    period: str = None
) -> dict:
    # 1. Safety verification
    if not any([budget_ids, start_date, end_date, budget_type, category, subcategory, period]):
        return {
            "status": "error",
            "message": "At least one target filter must be specified to delete budgets."
        }

    # 2. Casing normalization for category/subcategory filters
    matched_filter_cat = None
    matched_filter_sub = None
    if category:
        try:
            matched_filter_cat, matched_filter_sub = validate_category_and_subcategory(category, subcategory)
        except ValueError:
            # If the filter category is invalid, there won't be any matching budgets in the DB to delete
            return {
                "status": "ok",
                "deleted_count": 0,
                "deleted_ids": []
            }

    # 3. Date validation
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

    # 4. Build dynamic query
    where_clauses = ["user_id = $1"]
    params = [user_id]
    param_idx = 2

    if budget_ids:
        where_clauses.append(f"id = ANY(${param_idx}::integer[])")
        params.append(budget_ids)
        param_idx += 1
    if parsed_start:
        where_clauses.append(f"start_date >= ${param_idx}")
        params.append(parsed_start)
        param_idx += 1
    if parsed_end:
        where_clauses.append(f"end_date <= ${param_idx}")
        params.append(parsed_end)
        param_idx += 1
    if budget_type:
        where_clauses.append(f"budget_type = ${param_idx}")
        params.append(budget_type)
        param_idx += 1
    if matched_filter_cat:
        where_clauses.append(f"category = ${param_idx}")
        params.append(matched_filter_cat)
        param_idx += 1
    if matched_filter_sub:
        where_clauses.append(f"subcategory = ${param_idx}")
        params.append(matched_filter_sub)
        param_idx += 1
    if period:
        where_clauses.append(f"period = ${param_idx}")
        params.append(period)
        param_idx += 1

    query = f"DELETE FROM budgets WHERE {' AND '.join(where_clauses)} RETURNING id"

    try:
        rows = await conn.fetch(query, *params)
        deleted_ids = [row["id"] for row in rows]
        return {
            "status": "ok",
            "deleted_count": len(deleted_ids),
            "deleted_ids": deleted_ids
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Deletion failed: {str(e)}"
        }
```

---

### [MODIFY] [main.py](file:///c:/Users/Admin/Desktop/Finance%20Intelligence%20MCP/main.py)
We will register `@mcp.tool` named `delete_budgets` and delegate the logic to `budget.delete_budgets_impl`.

```python
@mcp.tool
async def delete_budgets(
    budget_ids: list[int] = None,
    start_date: str = None,
    end_date: str = None,
    budget_type: str = None,
    category: str = None,
    subcategory: str = None,
    period: str = None
) -> dict:
    """
    Delete budgets matching the target filters.
    At least one target filter must be provided.
    All provided filters are combined using AND.
    
    :param budget_ids: List of specific budget IDs to delete.
    :param start_date: Filter start date in YYYY-MM-DD format (delete budgets starting on or after this date).
    :param end_date: Filter end date in YYYY-MM-DD format (delete budgets ending on or before this date; requires start_date).
    :param budget_type: Budget scope: 'overall', 'category', or 'subcategory'.
    :param category: Category name to filter target budgets.
    :param subcategory: Subcategory name to filter target budgets.
    :param period: Recurrence period to filter target budgets.
    :return: A status dictionary indicating status and list of deleted IDs.
    """
    db_pool = await get_pool()
    async with db_pool.acquire() as conn:
        user_id = await get_authenticated_user_id(conn)
        return await budget.delete_budgets_impl(
            conn, user_id,
            budget_ids=budget_ids,
            start_date=start_date,
            end_date=end_date,
            budget_type=budget_type,
            category=category,
            subcategory=subcategory,
            period=period
        )
```

---

## Verification Plan

### Automated Tests
To verify correct functionality, we will execute a manual integration testing script `scratch/test_delete_budgets.py` containing:
1. Creating a set of budgets.
2. Filtering and deleting one budget by ID.
3. Filtering and bulk deleting budgets by criteria (e.g. type or category).
4. Attempting to delete without filters (verifying error response).
5. Verification of isolation (making sure another user's budgets are not deleted).
6. Deleting any leftover test database records.
