# Implementation Plan: Create Budget Tool

This plan details the implementation steps to add the `create_budget` tool to the Expense Tracker MCP server, using a modular design.

## User Review Required
No breaking changes. The `create_budget` tool is a new feature.

## Proposed Changes

### Modular Code Architecture
To achieve modularity and keep [main.py](file:///c:/Users/Admin/Desktop/Finance%20Intelligence%20MCP/main.py) concise, we will place all helper and implementation logic for budget operations in a separate file: `budget.py`. The `main.py` file will only contain the `@mcp.tool` decorator and delegate the request execution to `budget.py`.

---

### [NEW] [budget.py](file:///c:/Users/Admin/Desktop/Finance%20Intelligence%20MCP/budget.py)
This file will contain:
1. **Helper function `validate_category_and_subcategory`**: Validates user inputs against `categories.json`.
2. **Implementation function `create_budget_impl`**: Processes validation, performs database transaction, and inserts records.

---

### [MODIFY] [main.py](file:///c:/Users/Admin/Desktop/Finance%20Intelligence%20MCP/main.py)
1. **Import `budget` module**:
   Add `import budget` to the imports at the top of `main.py`.
2. **Register `create_budget` MCP Tool**:
   Define the `@mcp.tool` entrypoint and route it to `budget.create_budget_impl` with `conn` and `user_id`.

```python
import budget

@mcp.tool
async def create_budget(
    budget_type: str = None,
    amount: float = None,
    period: str = None,
    start_date: str = None,
    end_date: str = None,
    category: str = None,
    subcategory: str = None,
    budgets: list[dict] = None
) -> dict:
    """
    Create one or more budget tracking limits.
    You can either pass single budget parameters or a list of budget dicts in 'budgets'.
    """
    db_pool = await get_pool()
    async with db_pool.acquire() as conn:
        user_id = await get_authenticated_user_id(conn)
        return await budget.create_budget_impl(
            conn, user_id,
            budget_type=budget_type,
            amount=amount,
            period=period,
            start_date=start_date,
            end_date=end_date,
            category=category,
            subcategory=subcategory,
            budgets=budgets
        )
```

---

## Verification Plan

### Manual Verification
We will manually verify the feature using a Python verification script:
1. **Valid Single Budget**: Create a valid overall budget.
2. **Valid Category Budget**: Create a category budget for `Travel`.
3. **Invalid Category Validation**: Create a budget with category `InvalidName` and verify it gets blocked by application checks with an error response.
4. **Invalid Scope Validation**: Create an overall budget with category set and verify it gets blocked.
5. **Bulk Budgets Creation**: Create two budgets at once and confirm both IDs are returned.
6. Clean up database states after validation.
