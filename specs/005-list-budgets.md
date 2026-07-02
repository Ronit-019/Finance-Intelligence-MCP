# Spec-005: List Budgets Tool

## 1. Overview
This feature introduces the `list_budgets` MCP tool to allow users to retrieve their defined budget tracking limits. The tool will support querying overall budgets or filtering by specific columns (such as budget type, category, subcategory, or period).

This tool will be implemented modularly, with database query operations defined in `budget.py` and the MCP tool registered in `main.py`.

## 2. Requirements & User Stories
- **User Story 1**: As a user, I want to retrieve all my defined budgets to review my financial limits.
- **User Story 2**: As a user, I want to list only a specific type of budget (e.g., list all "overall" budgets, or only "monthly" budgets).
- **User Story 3**: As a user, I want to list budgets specific to a category (e.g., list budgets defined for "Food").
- **Security Constraint**: A user must only see their own budgets. The query must filter by the authenticated user's `user_id`.

---

## 3. Technical Design

### MCP Tool Interface
We will register a new tool using `@mcp.tool` in `main.py`.

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
    
    :param budget_type: Optional filter by scope: 'overall', 'category', or 'subcategory'.
    :param category: Optional filter by category name.
    :param subcategory: Optional filter by subcategory name.
    :param period: Optional filter by duration: 'weekly', 'monthly', 'quarterly', or 'yearly'.
    :return: A list of budgets matching the filters.
    """
```

### Modular Implementation (`budget.py`)
We will add `list_budgets_impl` to `budget.py`:

```python
async def list_budgets_impl(
    conn,
    user_id: int,
    budget_type: str = None,
    category: str = None,
    subcategory: str = None,
    period: str = None
) -> list:
    """
    Query the budgets database with dynamic column filters.
    """
```

### Database Query Construction
We will dynamically build the `SELECT` statement:

```sql
SELECT id, budget_type, category, subcategory, amount, period, start_date::text, end_date::text
FROM budgets
WHERE user_id = $1
```

For each provided filter parameter (`budget_type`, `category`, `subcategory`, `period`), we append an `AND` clause:
- `budget_type`: `AND budget_type = $<param_index>`
- `category`: `AND category = $<param_index>`
- `subcategory`: `AND subcategory = $<param_index>`
- `period`: `AND period = $<param_index>`

The records will be returned ordered by `id` ascending.

---

## 4. Edge Cases & Safety
- **No Filters Provided**: Returns all budgets belonging to the authenticated user.
- **Casing Correction**: Any filters for `category` or `subcategory` will be normalized using `validate_category_and_subcategory` (if defined/needed) or simply converted to lowercase if matching is case-insensitive, ensuring that query casing mismatch doesn't result in empty records. We will run category validation on filters to correct their casing.
- **Empty Results**: If no budgets match the filters, returns an empty list `[]`.

---

## 5. Verification Plan

### Manual Verification
1. Add a few test budgets using `create_budget`:
   - Overall monthly budget ($1000).
   - Food monthly budget ($200).
   - Travel weekly budget ($100).
2. **Test 1: List all budgets** (no filters) -> confirm all 3 are returned.
3. **Test 2: Filter by budget type** (`budget_type='overall'`) -> confirm only overall budget is returned.
4. **Test 3: Filter by category** (`category='Food'`) -> confirm only Food budget is returned.
5. **Test 4: Filter by period** (`period='weekly'`) -> confirm only Travel budget is returned.
6. Clean up test records.
