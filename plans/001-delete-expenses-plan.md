# Implementation Plan: Expense Deletion Tool

This plan details the implementation steps to add a flexible expense deletion tool to the Expense Tracker MCP server.

## User Review Required
No breaking changes are introduced. The new tool (`delete_expenses`) is backward-compatible and does not affect existing tools.

## Proposed Changes

### Database Layer & FastMCP Server

#### [MODIFY] [main.py](file:///c:/Users/Admin/Desktop/Finance%20Intelligence%20MCP/main.py)
We will add the `@mcp.tool` decorator and `delete_expenses` function at the end of the tool registrations in `main.py`.

The function will:
1. Check if all parameters are `None` (or empty lists). If so, return an error message to prevent accidental deletions.
2. Authenticate the user to retrieve the `user_id`.
3. Construct the SQL `DELETE` query dynamically using PostgreSQL positional parameters (`$1`, `$2`, etc.) to prevent SQL injection.
4. Execute the query, returning the list of deleted IDs.
5. Return a standard response structure.

Here is the proposed code structure to add to `main.py`:

```python
@mcp.tool
async def delete_expenses(
    expense_ids: list[int] = None,
    start_date: str = None,
    end_date: str = None,
    category: str = None,
    subcategory: str = None
) -> dict:
    """
    Delete expenses matching the provided filters.
    At least one filter must be provided to prevent accidental deletion of all records.
    All provided filters are combined using AND.
    
    :param expense_ids: List of specific expense IDs to delete.
    :param start_date: Start date in YYYY-MM-DD format.
    :param end_date: End date in YYYY-MM-DD format (requires start_date).
    :param category: Category name.
    :param subcategory: Subcategory name.
    :return: A status dictionary indicating status and number of deleted records.
    """
    if not any([expense_ids, start_date, end_date, category, subcategory]):
        return {
            "status": "error",
            "message": (
                "At least one filter (expense_ids, start_date, end_date, "
                "category, or subcategory) must be specified to delete expenses."
            )
        }

    db_pool = await get_pool()
    async with db_pool.acquire() as conn:
        user_id = await get_authenticated_user_id(conn)
        
        # Build query dynamically
        query = "DELETE FROM expenses WHERE user_id = $1"
        params = [user_id]
        param_idx = 2
        
        if expense_ids:
            query += f" AND id = ANY(${param_idx}::integer[])"
            params.append(expense_ids)
            param_idx += 1
            
        if start_date:
            parsed_start = pydate.fromisoformat(start_date)
            if end_date:
                parsed_end = pydate.fromisoformat(end_date)
                query += f" AND date BETWEEN ${param_idx} AND ${param_idx+1}"
                params.extend([parsed_start, parsed_end])
                param_idx += 2
            else:
                query += f" AND date >= ${param_idx}"
                params.append(parsed_start)
                param_idx += 1
        elif end_date:
            parsed_end = pydate.fromisoformat(end_date)
            query += f" AND date <= ${param_idx}"
            params.append(parsed_end)
            param_idx += 1
            
        if category:
            query += f" AND category = ${param_idx}"
            params.append(category)
            param_idx += 1
            
        if subcategory:
            query += f" AND subcategory = ${param_idx}"
            params.append(subcategory)
            param_idx += 1
            
        query += " RETURNING id"
        
        rows = await conn.fetch(query, *params)
        deleted_ids = [row["id"] for row in rows]
        
        return {
            "status": "ok",
            "deleted_count": len(deleted_ids),
            "deleted_ids": deleted_ids
        }
```

---

## Verification Plan

### Automated Tests
Currently, there is no automated test suite. If needed, we can create a simple integration/unit test script in a temporary test file.

### Manual Verification
We will manually verify the feature using a Python scratch script that imports and tests the tool functions directly, or runs the MCP server locally and hits the DB:
1. **Insert test records** using `add_expense`.
2. **Retrieve test records** using `list_expenses` to verify insertion.
3. **Execute test deletions**:
   - Delete by ID.
   - Delete by Category.
   - Delete by Date Range.
   - Run delete with no filters (verify it returns an error).
4. **Confirm database state** after each action.
