# Spec-002: Expense Update Tool

## 1. Overview
Currently, the Expense Tracker MCP server allows users to add, list, summarize, and delete expenses. However, if a user makes a mistake in an expense entry (e.g. incorrect amount, wrong category, or typo in note), they must delete and recreate it.

This feature adds a flexible MCP tool allowing users to update specific fields of matching expenses.

## 2. Requirements & User Stories
- **User Story 1**: As a user, I want to update one or more fields (amount, category, subcategory, date, note) of a specific expense by ID.
- **User Story 2**: As a user, I want to bulk update matching expenses (e.g., move all expenses under category "Food" to "Utilities" or update subcategory name).
- **Safety Constraint 1**: To prevent accidental modification of all records, the tool must require at least one target filter/parameter to identify which rows to update.
- **Safety Constraint 2**: The tool must require at least one field update parameter (i.e. something to change).
- **Security Constraint**: A user must only be able to update their own expenses. The tool must authenticate the user and restrict the modifications to the authenticated `user_id`.

## 3. Technical Design

### MCP Tool Interface
We will register a new tool using `@mcp.tool`.

```python
@mcp.tool
async def update_expenses(
    # Target selection filters (Which rows to update)
    expense_ids: list[int] = None,
    filter_start_date: str = None,
    filter_end_date: str = None,
    filter_category: str = None,
    filter_subcategory: str = None,
    
    # New values to apply (What to change)
    date: str = None,
    amount: float = None,
    category: str = None,
    subcategory: str = None,
    note: str = None
) -> dict:
    """
    Update expenses matching the target filters with the specified values.
    At least one target filter and one update value must be provided.
    
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
    :return: A status dictionary indicating the number of updated records.
    """
```

### Database Integration & Query Construction
Since target filters and updated fields are both dynamic, we will build both the `SET` clause and the `WHERE` clause dynamically.

#### Base Query Structure
```sql
UPDATE expenses
SET <set_clause_1> = $2, <set_clause_2> = $3, ...
WHERE user_id = $1 AND <where_clause_1> AND <where_clause_2>
RETURNING id;
```

#### Step-by-Step Construction:
1. **Initial Param Index**:
   `user_id` is always the first parameter (`$1`).
2. **SET Clauses**:
   For each provided update field (`date`, `amount`, `category`, `subcategory`, `note`), append to the SET clause list:
   - `date`: `date = $<param_index>`
   - `amount`: `amount = $<param_index>`
   - `category`: `category = $<param_index>`
   - `subcategory`: `subcategory = $<param_index>`
   - `note`: `note = $<param_index>`
   Increment `param_index` for each value added to the query params list.
3. **WHERE Clauses (Target Filters)**:
   For each provided target filter:
   - `expense_ids`: `id = ANY($<param_index>::integer[])`
   - `filter_start_date` / `filter_end_date`: `date BETWEEN $<param_idx_1> AND $<param_idx_2>` or dynamic bounds
   - `filter_category`: `category = $<param_index>`
   - `filter_subcategory`: `subcategory = $<param_index>`
   Increment `param_index` accordingly.

### Execution Flow
1. Check if all target filters are empty. If so, return an error.
2. Check if all update fields are empty. If so, return an error.
3. Lazy initialize/get the database pool: `db_pool = await get_pool()`.
4. Acquire a connection from the pool.
5. Authenticate the user and retrieve their database ID: `user_id = await get_authenticated_user_id(conn)`.
6. Dynamically build the `UPDATE` query parts and parameter list.
7. Execute the query using the acquired connection.
8. Retrieve the list of updated IDs from the `RETURNING id` clause.
9. Return a summary dictionary:
   ```json
   {
     "status": "ok",
     "updated_count": 2,
     "updated_ids": [14, 15]
   }
   ```

## 4. Edge Cases & Safety
- **No Target Filters**: Returns error to prevent updating every row in the database.
- **No Update Fields**: Returns error as there is nothing to update.
- **Unauthorized Update**: The `user_id = $1` clause guarantees that only the authenticated user's records can be updated, even if they pass arbitrary IDs.
- **Empty Result**: If no records match the filters, returns `{"status": "ok", "updated_count": 0, "updated_ids": []}`.

## 5. Verification Plan

### Manual Verification
1. Add a test expense: `Food`, `$10`, `2026-07-01`, note `Original`.
2. **Test 1: Update single expense by ID**
   - Call `update_expenses(expense_ids=[<ID>], amount=15.5, note="Updated Note")`.
   - Verify that the amount is now `15.5` and note is `"Updated Note"`.
3. **Test 2: Bulk update by filter**
   - Call `update_expenses(filter_category="Food", category="Utilities")`.
   - Verify category changes to `Utilities`.
4. **Test 3: Safety validations**
   - Call with no target filters -> should fail.
   - Call with target filters but no set fields -> should fail.
