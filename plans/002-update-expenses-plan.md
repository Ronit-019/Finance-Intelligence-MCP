# Implementation Plan: Expense Update Tool

This plan details the implementation steps to add a dynamic expense update tool to the Expense Tracker MCP server.

## User Review Required
No breaking changes. The update feature is a completely new tool.

## Proposed Changes

### Database Layer & FastMCP Server

#### [MODIFY] [main.py](file:///c:/Users/Admin/Desktop/Finance%20Intelligence%20MCP/main.py)
We will register a new `@mcp.tool` named `update_expenses` in `main.py`.

The function will:
1. Perform safety validations:
   - Ensure at least one target filter (`expense_ids`, `filter_start_date`, `filter_end_date`, `filter_category`, `filter_subcategory`) is provided.
   - Ensure at least one update value (`date`, `amount`, `category`, `subcategory`, `note`) is provided.
2. Authenticate the user to retrieve the `user_id`.
3. Construct the dynamic `UPDATE` statement. Position numbers for placeholders will be mapped dynamically to separate parameters for `SET` and parameters for `WHERE`.
4. Execute the statement and return the updated IDs.

Here is the proposed logic:

```python
@mcp.tool
async def update_expenses(
    expense_ids: list[int] = None,
    filter_start_date: str = None,
    filter_end_date: str = None,
    filter_category: str = None,
    filter_subcategory: str = None,
    date: str = None,
    amount: float = None,
    category: str = None,
    subcategory: str = None,
    note: str = None
) -> dict:
    """
    Update expenses matching the target filters with the specified values.
    At least one target filter and one update value must be provided.
    All provided filters are combined using AND.
    
    :param expense_ids: List of specific expense IDs to update.
    :param filter_start_date: Target start date to filter rows.
    :param filter_end_date: Target end date to filter rows.
    :param filter_category: Target category to filter rows.
    :param filter_subcategory: Target subcategory to filter rows.
    :param date: New date value in YYYY-MM-DD format.
    :param amount: New amount value.
    :param category: New category name.
    :param subcategory: New subcategory name.
    :param note: New note text.
    :return: A status dictionary indicating status and number of updated records.
    """
    if not any([expense_ids, filter_start_date, filter_end_date, filter_category, filter_subcategory]):
        return {
            "status": "error",
            "message": (
                "At least one target filter (expense_ids, filter_start_date, "
                "filter_end_date, filter_category, or filter_subcategory) must be specified."
            )
        }
        
    if not any([date is not None, amount is not None, category is not None, subcategory is not None, note is not None]):
        return {
            "status": "error",
            "message": (
                "At least one field value (date, amount, category, subcategory, "
                "or note) must be specified to update."
            )
        }

    db_pool = await get_pool()
    async with db_pool.acquire() as conn:
        user_id = await get_authenticated_user_id(conn)
        
        set_clauses = []
        params = []
        param_idx = 1
        
        # Add SET values
        if date is not None:
            set_clauses.append(f"date = ${param_idx}")
            params.append(pydate.fromisoformat(date))
            param_idx += 1
            
        if amount is not None:
            set_clauses.append(f"amount = ${param_idx}")
            params.append(amount)
            param_idx += 1
            
        if category is not None:
            set_clauses.append(f"category = ${param_idx}")
            params.append(category)
            param_idx += 1
            
        if subcategory is not None:
            set_clauses.append(f"subcategory = ${param_idx}")
            params.append(subcategory)
            param_idx += 1
            
        if note is not None:
            set_clauses.append(f"note = ${param_idx}")
            params.append(note)
            param_idx += 1
            
        # Add WHERE values
        where_clauses = [f"user_id = ${param_idx}"]
        params.append(user_id)
        param_idx += 1
        
        if expense_ids:
            where_clauses.append(f"id = ANY(${param_idx}::integer[])")
            params.append(expense_ids)
            param_idx += 1
            
        if filter_start_date:
            parsed_start = pydate.fromisoformat(filter_start_date)
            if filter_end_date:
                parsed_end = pydate.fromisoformat(filter_end_date)
                where_clauses.append(f"date BETWEEN ${param_idx} AND ${param_idx+1}")
                params.extend([parsed_start, parsed_end])
                param_idx += 2
            else:
                where_clauses.append(f"date >= ${param_idx}")
                params.append(parsed_start)
                param_idx += 1
        elif filter_end_date:
            parsed_end = pydate.fromisoformat(filter_end_date)
            where_clauses.append(f"date <= ${param_idx}")
            params.append(parsed_end)
            param_idx += 1
            
        if filter_category:
            where_clauses.append(f"category = ${param_idx}")
            params.append(filter_category)
            param_idx += 1
            
        if filter_subcategory:
            where_clauses.append(f"subcategory = ${param_idx}")
            params.append(filter_subcategory)
            param_idx += 1
            
        query = f"UPDATE expenses SET {', '.join(set_clauses)} WHERE {' AND '.join(where_clauses)} RETURNING id"
        
        rows = await conn.fetch(query, *params)
        updated_ids = [row["id"] for row in rows]
        
        return {
            "status": "ok",
            "updated_count": len(updated_ids),
            "updated_ids": updated_ids
        }
```

---

## Verification Plan

### Manual Verification
We will manually verify the feature using a Python script:
1. **Insert a test record** (`Food`, `$10`, `2026-07-01`).
2. **Verify Single Record Update**: Update the amount and check if changed.
3. **Verify Bulk Update**: Bulk update all matching target categories (e.g. food -> utilities).
4. **Safety Verification**: Ensure attempts to update without filters or update fields return a validation error status.
