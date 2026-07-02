# Spec-003: Budget Table Creation

## 1. Overview
This feature introduces a new `budgets` database table to support budgeting capabilities in the Expense Tracker MCP server. The budget table stores spending limits defined by users and supports overall budgets, category-specific budgets, and subcategory-specific budgets.

This spec covers only the creation and initialization of the `budgets` table itself within the server setup.

## 2. Database Schema

### SQL Table Schema

We will create a `budgets` table with the following structure:

```sql
CREATE TABLE IF NOT EXISTS budgets (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    budget_type VARCHAR(20) NOT NULL,
    category VARCHAR(100) DEFAULT NULL,
    subcategory VARCHAR(100) DEFAULT NULL,
    amount DOUBLE PRECISION NOT NULL,
    period VARCHAR(20) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Enforce valid budget types and periods
    CONSTRAINT chk_budget_type CHECK (budget_type IN ('overall', 'category', 'subcategory')),
    CONSTRAINT chk_period CHECK (period IN ('weekly', 'monthly', 'quarterly', 'yearly')),
    
    -- Enforce category/subcategory presence based on budget_type
    CONSTRAINT chk_budget_scope CHECK (
        (budget_type = 'overall' AND category IS NULL AND subcategory IS NULL) OR
        (budget_type = 'category' AND category IS NOT NULL AND subcategory IS NULL) OR
        (budget_type = 'subcategory' AND category IS NOT NULL AND subcategory IS NOT NULL)
    )
);
```

### Table Fields Summary

| Field | Type | Nullable | Description |
|---|---|---|---|
| `id` | `SERIAL` | ❌ | Primary key. |
| `user_id` | `INTEGER` | ❌ | Foreign key to `users(id)`. |
| `budget_type` | `VARCHAR(20)`| ❌ | Scope: `'overall'`, `'category'`, or `'subcategory'`. |
| `category` | `VARCHAR(100)`| ✅ | Budget category (required for `'category'` and `'subcategory'`). |
| `subcategory` | `VARCHAR(100)`| ✅ | Budget subcategory (required for `'subcategory'`). |
| `amount` | `DOUBLE PRECISION`| ❌ | Spending limit amount. |
| `period` | `VARCHAR(20)`| ❌ | Duration: `'weekly'`, `'monthly'`, `'quarterly'`, or `'yearly'`. |
| `start_date` | `DATE` | ❌ | Effective start date of the budget. |
| `end_date` | `DATE` | ❌ | Expiration date of the budget. |
| `created_at` | `TIMESTAMP` | ❌ | Record creation timestamp. |
| `updated_at` | `TIMESTAMP` | ❌ | Record modification timestamp. |

---

## 3. Technical Design

### Database Initialization
We will update `get_pool()` in [main.py](file:///c:/Users/Admin/Desktop/Finance%20Intelligence%20MCP/main.py) to execute the `CREATE TABLE IF NOT EXISTS budgets` statement during initialization, right after creating the `expenses` table.

---

## 4. Verification Plan

### Database Table Verification
We will manually verify that the table is successfully created on start:
1. Restart/run the MCP server (which triggers `get_pool()`).
2. Run a database query to confirm the `budgets` table exists and contains all the columns and constraints defined above.
