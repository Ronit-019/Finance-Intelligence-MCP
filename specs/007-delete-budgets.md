# Spec-007: Budget Delete Tool

## 1. Overview
Currently, the Finance Intelligence MCP server allows users to create, list, and update budgets. However, there is no way to remove budgets once they are no longer needed or if they were created in error, short of direct database intervention.

This feature adds a new MCP tool named `delete_budgets` to dynamically delete matching budget records.

---

## 2. Requirements & User Stories

- **User Story 1**: As a user, I want to delete a specific budget by its database ID.
- **User Story 2**: As a user, I want to delete multiple budgets at once by passing a list of IDs.
- **User Story 3**: As a user, I want to bulk delete budgets by filtering on criteria like `budget_type`, `category`, `subcategory`, `period`, or date ranges (e.g. delete all weekly budgets, or delete all budgets for the "Food" category).
- **Safety Constraint**: To prevent accidental deletion of all budget records, the tool must require at least one target filter parameter.
- **Security Constraint**: The deletion must be restricted to the authenticated `user_id`. A user must never be able to delete another user's budget records.

---

## 3. Technical Design

### MCP Tool Interface
We will register a new tool using `@mcp.tool` in `main.py`.

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
```

### Delegation and Implementation (`budget.py`)
In `budget.py`, we will add `delete_budgets_impl` which takes the connection, `user_id`, and filter criteria:

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
```

### Business Logic & Validation Steps

1. **Parameter Validation**:
   - Check if all filter parameters (`budget_ids`, `start_date`, `end_date`, `budget_type`, `category`, `subcategory`, `period`) are `None` or empty. If so, return an error.
2. **Category & Subcategory Validation**:
   - If `category` is provided, normalize it using `validate_category_and_subcategory(category, subcategory)`. If validation throws a `ValueError` (meaning category is invalid), we can immediately return `{"status": "ok", "deleted_count": 0, "deleted_ids": []}` since no such records would exist.
3. **Date parsing**:
   - If `start_date` and/or `end_date` are specified, parse them into date objects to ensure valid format.
4. **Dynamic Query Construction**:
   - Initialize `where_clauses` list and query parameters `params` list.
   - The first parameter `$1` is always the authenticated `user_id` (`user_id = $1`).
   - Append to `where_clauses` dynamically for every filter passed:
     - `budget_ids` -> `id = ANY($<idx>::integer[])`
     - `start_date` -> `start_date >= $<idx>` (or dynamic date range query)
     - `end_date` -> `end_date <= $<idx>`
     - `budget_type` -> `budget_type = $<idx>`
     - `category` -> `category = $<idx>` (normalized)
     - `subcategory` -> `subcategory = $<idx>` (normalized)
     - `period` -> `period = $<idx>`
5. **Execution**:
   - Build the SQL query: `DELETE FROM budgets WHERE <where_clauses> RETURNING id`.
   - Execute and fetch deleted rows to return:
     ```json
     {
       "status": "ok",
       "deleted_count": 2,
       "deleted_ids": [10, 11]
     }
     ```

---

## 4. Edge Cases & Safety Constraints

- **No Filter Targets**: Block execution and return error: `"At least one target filter must be specified to delete budgets."`
- **Security Isolation**: The inclusion of `user_id = $1` in the `WHERE` clause guarantees that a user can never delete another user's budget, even if they explicitly pass another user's budget IDs in `budget_ids`.
- **Empty Match**: If no records match, return success with `deleted_count: 0`.

---

## 5. Verification Plan

### Manual Verification
1. Create three dummy budgets for the testing user (e.g. food category budget, travel category budget, overall budget).
2. **Test 1: Delete specific budget by ID**
   - Call `delete_budgets(budget_ids=[<food_budget_id>])`.
   - Verify it is deleted and the response contains the deleted ID.
3. **Test 2: Bulk delete by type**
   - Call `delete_budgets(budget_type="category")`.
   - Verify travel budget is deleted, but overall budget remains.
4. **Test 3: Enforce safety filter requirement**
   - Call `delete_budgets()` with no parameters.
   - Verify the request is rejected with a validation error.
5. **Test 4: Tenant isolation validation**
   - Try to delete another user's budget ID.
   - Verify that the record is not deleted and `deleted_count` is 0.
