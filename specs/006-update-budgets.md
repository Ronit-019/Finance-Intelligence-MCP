# Spec-006: Budget Update Tool

## 1. Overview
Currently, the Finance Intelligence MCP server allows users to create and list budgets (including overall, category-level, and subcategory-level budgets). However, there is no way to modify existing budget limits, adjust their dates, or shift their category scopes without deleting and recreating them.

This feature adds a new MCP tool named `update_budgets` to dynamically update matching budget records.

---

## 2. Requirements & User Stories

- **User Story 1**: As a user, I want to update one or more fields (amount, period, dates, category, subcategory, type) of a specific budget by its ID.
- **User Story 2**: As a user, I want to perform bulk updates on matching budgets (e.g. increase all "monthly" budgets by 10%, or shift budget parameters of all budgets for a given category).
- **Safety Constraint 1**: To prevent accidental modifications of all budget limits, the tool must require at least one target filter parameter to identify which budget records to modify.
- **Safety Constraint 2**: The tool must require at least one field update value (i.e. something to change).
- **Database Consistency & Validation**:
  - Any category or subcategory name passed in update parameters must be verified against `categories.json` using the existing validation logic.
  - Incompatibilities between updated dates (e.g. `start_date > end_date`) must be prevented.
  - Database schema constraints (`chk_budget_type`, `chk_period`, `chk_budget_scope`) must be respected and errors returned gracefully to the client.
- **Security Constraint**: The operation must be restricted to the authenticated `user_id`. A user must never be able to update another user's budget records.

---

## 3. Technical Design

### MCP Tool Interface
We will register a new tool using `@mcp.tool` in `main.py` which will delegate execution to `budget.py`.

```python
@mcp.tool
async def update_budgets(
    # Target selection filters (Which budgets to update)
    budget_ids: list[int] = None,
    filter_budget_type: str = None,
    filter_category: str = None,
    filter_subcategory: str = None,
    filter_period: str = None,
    
    # New values to apply (What to change)
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
    :return: A status dictionary indicating the number of updated records.
    """
```

### Delegation and Implementation (`budget.py`)
In `budget.py`, we will add `update_budgets_impl` which takes the connection, `user_id`, filters, and new values:

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
```

### Business Logic & Validation Steps

1. **Parameter Validation**:
   - Check if all filter parameters (`budget_ids`, `filter_budget_type`, `filter_category`, `filter_subcategory`, `filter_period`) are `None`. If so, return an error.
   - Check if all update parameters (`budget_type`, `amount`, `period`, `start_date`, `end_date`, `category`, `subcategory`) are `None`. If so, return an error.
2. **Category Validation**:
   - If either update `category` or `subcategory` is provided, validate them against `categories.json` using `validate_category_and_subcategory(category, subcategory)`.
3. **Date Validation**:
   - If both `start_date` and `end_date` are being updated, ensure `start_date <= end_date`.
4. **Dynamic Query Building**:
   - Initialize `set_clauses` list, `where_clauses` list, and query parameters `params` list.
   - The first parameter `$1` is always the authenticated `user_id`.
   - Append to `set_clauses` dynamically for every provided update field:
     - `budget_type` -> `budget_type = $<idx>`
     - `amount` -> `amount = $<idx>`
     - `period` -> `period = $<idx>`
     - `start_date` -> `start_date = $<idx>`
     - `end_date` -> `end_date = $<idx>`
     - `category` -> `category = $<idx>`
     - `subcategory` -> `subcategory = $<idx>`
     - Also automatically set `updated_at = CURRENT_TIMESTAMP`.
   - Append to `where_clauses` based on provided filter criteria:
     - `user_id = $1` (enforces authorization boundary)
     - `budget_ids` -> `id = ANY($<idx>::integer[])`
     - `filter_budget_type` -> `budget_type = $<idx>`
     - `filter_category` -> `category = $<idx>` (validated)
     - `filter_subcategory` -> `subcategory = $<idx>` (validated)
     - `filter_period` -> `period = $<idx>`
5. **Execution & Error Handling**:
   - Run the dynamic `UPDATE budgets SET ... WHERE ... RETURNING id` query.
   - Catch any relational constraint violations (e.g. database `chk_budget_scope` constraint check failures if user tries to update an `overall` budget to have a category, or `chk_period` errors) and return a friendly error dictionary.

---

## 4. Edge Cases & Safety Constraints

- **No Target Filters Provided**: Block update and return an error explaining that at least one filter target must be specified.
- **No Fields to Update Provided**: Block update and return an error.
- **Constraint Violations (e.g., Overall Budget with Category)**: If a user sets `category="Food"` on a budget that remains/becomes an `overall` type budget, database constraints will fail. The server will catch `asyncpg.exceptions.CheckViolationError` (or general exceptions) and return a descriptive error message.
- **Date Chronology**: Checks if `start_date > end_date` inside validation and throws an error prior to database execution.
- **Unauthorized Manipulation**: The clause `WHERE user_id = $1` ensures users cannot modify other users' budget limits, even if they specify their IDs.

---

## 5. Verification Plan

### Manual Verification
1. Add a category budget: type `category`, category `Food`, period `monthly`, amount `500.0`, dates `2026-07-01` to `2026-07-31`.
2. **Test 1: Modify amount and period duration**
   - Call `update_budgets(budget_ids=[<id>], amount=600.0, period="yearly")`.
   - Verify values change correctly.
3. **Test 2: Check Category and Subcategory validations**
   - Call `update_budgets(budget_ids=[<id>], category="invalid_cat")` -> Should fail with invalid category error.
4. **Test 3: Enforce Constraint checks**
   - Call `update_budgets(budget_ids=[<id>], budget_type="overall", category="Food")` -> Should fail database constraint verification.
5. **Test 4: Verify Safety Limits**
   - Call with no filter target -> Should fail.
   - Call with filters but no update values -> Should fail.
