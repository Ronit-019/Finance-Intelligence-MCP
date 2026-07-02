# Implementation Plan: Budget Update Tool

This plan details the steps to implement the `update_budgets` MCP tool in the Finance Intelligence MCP server, allowing users to modify existing budget limits and attributes under strong validation and safety constraints.

## User Review Required

- **No Breaking Changes**: The `update_budgets` tool is a new feature.
- **Database Schema Constraints**: If update parameters conflict with existing constraints (e.g., trying to set a category on an `overall` budget, or setting an invalid period name), the database will reject it via CHECK constraints (`chk_budget_scope`, `chk_budget_type`, `chk_period`). The server will catch these exceptions and return a clean error message.

---

## Proposed Changes

### [MODIFY] [budget.py](file:///c:/Users/Admin/Desktop/Finance%20Intelligence%20MCP/budget.py)
We will add `update_budgets_impl` to `budget.py`:
- Validates that at least one filter and at least one update parameter is provided.
- Validates and normalizes `category` and `subcategory` (using `validate_category_and_subcategory`) if they are specified in update values or filters.
- Validates start and end date chronology if both are updated.
- Dynamically constructs the dynamic `UPDATE budgets SET ... WHERE ... RETURNING id` query.
- Catches database errors (like `CheckViolationError`) and returns appropriate status messages.

```python
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
```

---

### [MODIFY] [main.py](file:///c:/Users/Admin/Desktop/Finance%20Intelligence%20MCP/main.py)
We will register the `@mcp.tool` named `update_budgets` and delegate the logic to `budget.update_budgets_impl`.

```python
@mcp.tool
async def update_budgets(
    budget_ids: list[int] = None,
    filter_budget_type: str = None,
    filter_category: str = None,
    filter_subcategory: str = None,
    filter_period: str = None,
    budget_type: str = None,
    amount: float = None,
    period: str = None,
    start_date: str = None,
    end_date: str = None,
    category: str = None,
    subcategory: str = None
) -> dict:
    """
    Update budgets matching the target filters with the specified values.
    At least one target filter and one update value must be provided.
    All provided filters are combined using AND.
    
    :param budget_ids: List of specific budget IDs to update.
    :param filter_budget_type: Filter by target scope: 'overall', 'category', or 'subcategory'.
    :param filter_category: Filter by target category name.
    :param filter_subcategory: Filter by target subcategory name.
    :param filter_period: Filter by target period duration.
    
    :param budget_type: New budget type ('overall', 'category', 'subcategory').
    :param amount: New budget limit amount.
    :param period: New period duration ('weekly', 'monthly', 'quarterly', 'yearly').
    :param start_date: New effectiveness start date (YYYY-MM-DD).
    :param end_date: New effectiveness end date (YYYY-MM-DD).
    :param category: New category name.
    :param subcategory: New subcategory name.
    :return: A status dictionary indicating status and number of updated records.
    """
    db_pool = await get_pool()
    async with db_pool.acquire() as conn:
        user_id = await get_authenticated_user_id(conn)
        return await budget.update_budgets_impl(
            conn, user_id,
            budget_ids=budget_ids,
            filter_budget_type=filter_budget_type,
            filter_category=filter_category,
            filter_subcategory=filter_subcategory,
            filter_period=filter_period,
            budget_type=budget_type,
            amount=amount,
            period=period,
            start_date=start_date,
            end_date=end_date,
            category=category,
            subcategory=subcategory
        )
```

---

## Verification Plan

### Automated Tests
To verify correct functionality, we will execute a manual integration testing script `scratch/test_update_budgets.py` containing:
1. Creating a set of budgets.
2. Filtering and updating the amount on one.
3. Filtering and changing the type/category of another.
4. Attempting invalid updates (e.g. invalid date order, invalid category name, constraint violations) and verifying correct error outputs.
5. Verification of isolation (making sure another user's budgets are not touched).
6. Deleting test database records.
