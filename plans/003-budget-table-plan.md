# Implementation Plan: Budget Table Creation

This plan details the implementation steps to add a new `budgets` table to the database.

## User Review Required
No breaking changes are introduced. The table is added during server initialization and does not modify existing data structures.

## Proposed Changes

### Database Layer & FastMCP Server

#### [MODIFY] [main.py](file:///c:/Users/Admin/Desktop/Finance%20Intelligence%20MCP/main.py)
We will add the `CREATE TABLE` query for the `budgets` table to the connection initialization block in `get_pool()`.

```python
            # Create budgets table referencing users
            await conn.execute("""
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
                    
                    CONSTRAINT chk_budget_type CHECK (budget_type IN ('overall', 'category', 'subcategory')),
                    CONSTRAINT chk_period CHECK (period IN ('weekly', 'monthly', 'quarterly', 'yearly')),
                    CONSTRAINT chk_budget_scope CHECK (
                        (budget_type = 'overall' AND category IS NULL AND subcategory IS NULL) OR
                        (budget_type = 'category' AND category IS NOT NULL AND subcategory IS NULL) OR
                        (budget_type = 'subcategory' AND category IS NOT NULL AND subcategory IS NOT NULL)
                    )
                );
            """)
```

---

## Verification Plan

### Manual Verification
1. Run the MCP server to trigger database pool initialization and table creation.
2. Connect to the Supabase database using a quick verify script and run:
   - Check if table `budgets` exists in PostgreSQL system schemas.
   - Describe columns and constraints to check matches.
3. Clean up the test database.
