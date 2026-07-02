# Spec-008: Budget and Expense Current Status Tool

## 1. Overview
Currently, the Finance Intelligence MCP server allows users to manage expenses (add, list, update, delete) and budgets (create, list, update, delete) independently. However, there is no direct, automated comparison tool to check if a user is staying within their budget limits.

This feature adds a new MCP tool named `current_status` which acts as a bridge between the `expenses` and `budgets` tables. It calculates the real-time sum of expenses incurred during each active budget's start and end date range, comparing it against the budget limit.

---

## 2. Requirements & User Stories

- **User Story 1**: As a user, I want to see a list of my active budgets for a specific date (defaulting to today) along with how much I have spent in each budget's time window.
- **User Story 2**: As a user, I want to filter the budget status dashboard by specific categories, periods, or budget scopes (e.g. show status of "monthly" budgets or category "Food" budgets).
- **Core Calculations**:
  - **Total Spent**: Sum of all matching expenses within the budget's `start_date` and `end_date` (inclusive).
  - **Remaining**: Budget limit amount minus the total spent.
  - **Percentage Spent**: `(total_spent / budget_limit) * 100`.
  - **Status Label**: `'under_budget'` or `'over_budget'`.
- **Scope Matching Logic**:
  - `overall`: Match all user expenses between `start_date` and `end_date`.
  - `category`: Match user expenses between `start_date` and `end_date` where the expense `category` matches the budget's `category`.
  - `subcategory`: Match user expenses between `start_date` and `end_date` where the expense `category` and `subcategory` match the budget's `category` and `subcategory`.
- **Security Constraint**: A user must only see comparisons based on their own budgets and expenses.

---

## 3. Technical Design

### MCP Tool Interface
We will register a new tool using `@mcp.tool` in `main.py`.

```python
@mcp.tool
async def current_status(
    reference_date: str = None,
    budget_type: str = None,
    category: str = None,
    subcategory: str = None,
    period: str = None
) -> dict:
    """
    Get the real-time spending status compared against active budgets on a given reference date.
    All provided filters are combined using AND.
    
    :param reference_date: ISO date (YYYY-MM-DD) to check active budgets. Defaults to today's local date.
    :param budget_type: Optional filter by budget scope: 'overall', 'category', or 'subcategory'.
    :param category: Optional filter by category name.
    :param subcategory: Optional filter by subcategory name.
    :param period: Optional filter by duration: 'weekly', 'monthly', 'quarterly', or 'yearly'.
    :return: A status summary comparing active budgets with actual expenses.
    """
```

### Delegation and Implementation
We will implement the logic inside a new module or within `budget.py`. Since it relates to budget analysis, implementing it inside `budget.py` as `current_status_impl` is ideal.

```python
async def current_status_impl(
    conn,
    user_id: int,
    reference_date: str = None,
    budget_type: str = None,
    category: str = None,
    subcategory: str = None,
    period: str = None
) -> dict:
```

### Business Logic & SQL Query Execution

1. **Resolve Reference Date**:
   - If `reference_date` is omitted, use the current date (in local time or system date, formatting to `YYYY-MM-DD`).
2. **Category / Subcategory Casing Normalization**:
   - If `category` filter is provided, validate/normalize using `validate_category_and_subcategory(category, subcategory)`. If it throws a `ValueError`, return an error or empty budget status results.
3. **Step 1: Retrieve Matching Active Budgets**:
   - Select all budgets belonging to `user_id` where `start_date <= reference_date` AND `end_date >= reference_date`.
   - Apply any optional filters passed by the user (`budget_type`, `category`, `subcategory`, `period`).
   - SQL structure to fetch budgets:
     ```sql
     SELECT id, budget_type, category, subcategory, amount, period, start_date, end_date
     FROM budgets
     WHERE user_id = $1 AND start_date <= $2 AND end_date >= $2
     ```
4. **Step 2: Aggregate matching expenses for each budget**:
   - For each retrieved active budget, query the `expenses` table to find the sum of expenses matching the budget scope and time frame:
     - Time frame: `date BETWEEN start_date AND end_date` (inclusive)
     - Scope query parameters:
       - **overall**: `SELECT COALESCE(SUM(amount), 0.0) FROM expenses WHERE user_id = $1 AND date BETWEEN $2 AND $3`
       - **category**: `SELECT COALESCE(SUM(amount), 0.0) FROM expenses WHERE user_id = $1 AND date BETWEEN $2 AND $3 AND category = $4`
       - **subcategory**: `SELECT COALESCE(SUM(amount), 0.0) FROM expenses WHERE user_id = $1 AND date BETWEEN $2 AND $3 AND category = $4 AND subcategory = $5`
   - *Optimization Note*: To prevent multiple sequential network trips (N+1 query problem), we can perform a single combined query joining budgets and matching expenses or run asynchronous aggregations in parallel using `asyncio.gather`.
     For simplicity and clarity of implementation, running an `asyncio.gather` for the database calls of matching budgets is highly performant and clean.
5. **Step 3: Calculate Metrics and Return**:
   - For each active budget:
     - `limit_amount` = `amount`
     - `total_spent` = aggregated expense sum
     - `remaining` = `limit_amount - total_spent`
     - `percentage_spent` = `(total_spent / limit_amount) * 100` (handled safely if `limit_amount == 0`)
     - `status` = `'over_budget'` if `total_spent > limit_amount` else `'under_budget'`
   - Return dictionary:
     ```json
     {
       "status": "ok",
       "reference_date": "2026-07-02",
       "budgets": [ ...list of statuses ]
     }
     ```

---

## 4. Edge Cases & Safety Constraints

- **No Active Budgets Found**: Return `{"status": "ok", "reference_date": "2026-07-02", "budgets": []}`.
- **Zero Expenses Matched**: Return `total_spent = 0.0`, `remaining = limit_amount`, `percentage_spent = 0.0`, `status = 'under_budget'`.
- **Budget Amount is Zero**: If a budget limit amount is `0.0`, set `percentage_spent = 100.0` if `total_spent > 0` else `0.0`.
- **Tenant Security Boundaries**: The query filters must strictly enforce `user_id = $1` on both budgets retrieval and expenses aggregation.

---

## 5. Verification Plan

### Manual Verification
1. Create a dummy monthly overall budget of `$1000` (July 1 to July 31).
2. Create a category budget of `$100` for `Food` (July 1 to July 7).
3. Insert expenses for the test user:
   - July 2: `$150` on `Food` -> `dining_out`
   - July 3: `$50` on `Utilities` -> `electricity`
4. **Test 1: Call `current_status(reference_date="2026-07-02")`**
   - Verify category budget "Food" reports:
     - Limit: `100.0`
     - Total Spent: `150.0`
     - Remaining: `-50.0`
     - Percentage: `150.0%`
     - Status: `'over_budget'`
   - Verify overall budget reports:
     - Limit: `1000.0`
     - Total Spent: `200.0` (`150` food + `50` utilities)
     - Remaining: `800.0`
     - Percentage: `20.0%`
     - Status: `'under_budget'`
5. **Test 2: Optional filter testing**
   - Call `current_status(reference_date="2026-07-02", budget_type="category")` -> Verify only the "Food" category budget status is returned.
6. **Test 3: Date boundary testing**
   - Call `current_status(reference_date="2026-08-01")` -> Verify empty results list (assuming no August budgets exist).
