# Spec-001: Expense Deletion Tool

## 1. Overview
Currently, the Expense Tracker MCP server allows users to add, list, and summarize expenses. However, there is no way to remove incorrect or duplicate entries. 

This feature adds a flexible MCP tool allowing users to delete expenses by specifying either:
1. Specific expense IDs
2. Date range (start and end date)
3. Category
4. Subcategory

Or any combination of these filters (applied as `AND` constraints).

## 2. Requirements & User Stories
- **User Story 1**: As a user, I want to delete a single incorrect expense by specifying its unique ID.
- **User Story 2**: As a user, I want to delete multiple specific expenses at once by supplying a list of IDs.
- **User Story 3**: As a user, I want to delete all expenses matching certain filter criteria (e.g., a specific category, or a date range, or category + date range combined).
- **Safety Constraint**: To prevent accidental deletion of all records, the tool must require at least one filter/parameter to be set.
- **Security Constraint**: A user must only be able to delete their own expenses. The tool must authenticate the user and restrict deletions to the authenticated `user_id`.

## 3. Technical Design

### MCP Tool Interface
We will register a new tool using `@mcp.tool`.

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
```

### Database Integration & Query Construction
Since we support optional combinations of filters, we will build the SQL query dynamically.

#### Base Query
```sql
DELETE FROM expenses
WHERE user_id = $1
```

#### Dynamic Filter Clauses
1. **`expense_ids`**: 
   Append `AND id = ANY($<param_index>::integer[])`
2. **`start_date` / `end_date`**:
   - If only `start_date` is provided: Append `AND date >= $<param_index>::date`
   - If only `end_date` is provided: Append `AND date <= $<param_index>::date`
   - If both are provided: Append `AND date BETWEEN $<param_index_1>::date AND $<param_index_2>::date`
3. **`category`**:
   Append `AND category = $<param_index>`
4. **`subcategory`**:
   Append `AND subcategory = $<param_index>`

We will append `RETURNING id` to verify exactly which IDs were deleted.

### Execution Flow
1. Check if all parameters (`expense_ids`, `start_date`, `end_date`, `category`, `subcategory`) are `None` or empty. If so, return an error/warning status immediately without hitting the database.
2. Lazy initialize/get the database pool: `db_pool = await get_pool()`.
3. Acquire a connection from the pool.
4. Authenticate the user and retrieve their database ID: `user_id = await get_authenticated_user_id(conn)`.
5. Build the query dynamically:
   - Initialize the query parts and dynamic parameters list.
   - The first parameter is always `user_id`.
6. Execute the query using the acquired connection.
7. Retrieve the list of deleted IDs from the `RETURNING` clause.
8. Return a summary dictionary:
   ```json
   {
     "status": "ok",
     "deleted_count": 3,
     "deleted_ids": [12, 14, 15]
   }
   ```

## 4. Edge Cases & Safety
- **No Parameters Specified**: Returns `{"status": "error", "message": "At least one filter (expense_ids, start_date, end_date, category, or subcategory) must be specified to delete expenses."}`.
- **Unauthorized Deletion**: Even if a user passes arbitrary IDs or filters, the `user_id = $1` clause guarantees that only their own records are matched and deleted.
- **Invalid Date Formats**: If `start_date` or `end_date` are not valid ISO dates, `pydate.fromisoformat()` will raise a `ValueError` during parsing, which will be surfaced correctly.

## 5. Verification Plan

### Manual Verification
1. Add a few test expenses:
   - Expense A: Food, $10, 2026-07-01
   - Expense B: Food, $20, 2026-07-02
   - Expense C: Travel, $50, 2026-07-02
2. **Test 1: Delete by ID**
   - Call `delete_expenses(expense_ids=[<ID of A>])`
   - Verify Expense A is deleted, while B and C remain.
3. **Test 2: Delete by Category**
   - Call `delete_expenses(category="Food")`
   - Verify Expense B (Food) is deleted, while C (Travel) remains.
4. **Test 3: Delete by Date Range**
   - Call `delete_expenses(start_date="2026-07-02", end_date="2026-07-02")` on remaining items.
   - Verify Expense C is deleted.
5. **Test 4: Error Handling**
   - Call `delete_expenses()` with no arguments.
   - Verify it returns an error status and does not delete anything.
