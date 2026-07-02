# Spec-004: Create Budget Tool

## 1. Overview
This feature introduces the `create_budget` MCP tool to allow users to set spending limits. The tool will support creating either a single budget (via direct parameters) or multiple budgets at once (via a list of budget configurations).

This tool interacts with the `budgets` table created in Spec-003.

## 2. Requirements & User Stories
- **User Story 1**: As a user, I want to create a single overall or category-specific budget by providing details like type, period, amount, start date, and end date.
- **User Story 2**: As a user, I want to create multiple budgets at once (bulk creation) to set up my monthly tracking quickly.
- **Validation Requirement 1**: Validate that the input dates are correct (`start_date <= end_date`).
- **Validation Requirement 2**: Validate that category and subcategory values exist in `categories.json` to prevent invalid entries.
- **Security Constraint**: All created budgets must be automatically assigned to the authenticated user's `user_id`.

---

## 3. Technical Design

### MCP Tool Interface
We will register a new tool using `@mcp.tool`.

```python
@mcp.tool
async def create_budget(
    # Single budget creation parameters
    budget_type: str = None,
    amount: float = None,
    period: str = None,
    start_date: str = None,
    end_date: str = None,
    category: str = None,
    subcategory: str = None,
    
    # Bulk budget creation parameter
    budgets: list[dict] = None
) -> dict:
    """
    Create one or more budget tracking limits.
    You can either pass single budget parameters or a list of budget dicts in 'budgets'.
    
    :param budget_type: 'overall', 'category', or 'subcategory'.
    :param amount: Budget limit amount.
    :param period: 'weekly', 'monthly', 'quarterly', or 'yearly'.
    :param start_date: ISO start date (YYYY-MM-DD).
    :param end_date: ISO end date (YYYY-MM-DD).
    :param category: Optional category name.
    :param subcategory: Optional subcategory name.
    :param budgets: Optional list of budget dictionaries for bulk insertion.
                    Each dict must contain: 'budget_type', 'amount', 'period', 'start_date', 'end_date'
                    and optionally 'category', 'subcategory'.
    :return: A status dictionary containing details of the created budgets.
    """
```

### Data Validation Helper
We will add a helper to validate that `category` and `subcategory` (if specified) are defined in `categories.json`.

```python
import json

def validate_category_and_subcategory(category: str = None, subcategory: str = None):
    if category is None:
        return
    
    if not os.path.exists(CATEGORIES_PATH):
        # Fallback to defaults if file is missing
        valid_categories = ["Food", "Travel", "Utilities", "Entertainment", "Health", "Other"]
        if category not in valid_categories:
            raise ValueError(f"Category '{category}' is invalid. Allowed: {valid_categories}")
        return

    with open(CATEGORIES_PATH, 'r', encoding="utf-8") as f:
        data = json.load(f)
        
    # Categories keys are usually lowercase or match exactly. Let's do a case-insensitive check
    categories_lower = {k.lower(): k for k in data.keys()}
    category_lower = category.lower()
    
    if category_lower not in categories_lower:
        raise ValueError(f"Category '{category}' is invalid. Check categories.json keys.")
        
    matched_category_key = categories_lower[category_lower]
    
    if subcategory:
        valid_subcats = [s.lower() for s in data[matched_category_key]]
        if subcategory.lower() not in valid_subcats:
            raise ValueError(f"Subcategory '{subcategory}' is invalid for category '{category}'.")
```

### Database Integration & Execution Flow
1. **Request Parsing**:
   - If `budgets` list is provided, process each item.
   - If `budgets` is NOT provided, verify and wrap the single budget parameters into a list of size 1.
2. **Authentication**:
   - Resolve `user_id` using `get_authenticated_user_id(conn)`.
3. **Data Verification**:
   - Validate each budget definition: check date ordering, check parameter combinations (e.g. category not NULL for category budgets), and validate categories against `categories.json`.
4. **SQL Execution**:
   Use batch insert or a single dynamic INSERT query for bulk insertions:
   ```sql
   INSERT INTO budgets (user_id, budget_type, category, subcategory, amount, period, start_date, end_date)
   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
   RETURNING id;
   ```
5. **Return Format**:
   Return a status dictionary containing the list of newly created budget IDs:
   ```json
   {
     "status": "ok",
     "created_count": 2,
     "created_ids": [101, 102]
   }
   ```

---

## 4. Edge Cases & Safety
- **Missing Required Parameters**: Return error if required keys (budget_type, amount, period, start_date, end_date) are missing.
- **Schema Violations**: Database check constraints (`chk_budget_type`, `chk_period`, `chk_budget_scope`) will act as a fallback safety layer.
- **Date Inversion**: `start_date > end_date` will raise a ValueError.

---

## 5. Verification Plan

### Manual Verification
1. **Create Single Budget (Valid Overall)**:
   - Call `create_budget(budget_type='overall', amount=1000.0, period='monthly', start_date='2026-07-01', end_date='2026-07-31')`.
   - Verify it returns success and a valid ID.
2. **Create Single Budget (Valid Category)**:
   - Call `create_budget(budget_type='category', category='Travel', amount=300.0, period='monthly', start_date='2026-07-01', end_date='2026-07-31')`.
   - Verify it succeeds.
3. **Create Single Budget (Invalid Category)**:
   - Call `create_budget(budget_type='category', category='InvalidName', amount=100.0, period='monthly', start_date='2026-07-01', end_date='2026-07-31')`.
   - Verify it throws/returns a validation error.
4. **Create Bulk Budgets**:
   - Call `create_budget(budgets=[{...}, {...}])`.
   - Verify multiple budgets are created and correct IDs are returned.
