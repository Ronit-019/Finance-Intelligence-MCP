from fastmcp import FastMCP
import asyncpg
import os
import getpass
from dotenv import load_dotenv
from datetime import date as pydate
from src import budget
from src import analytics
from src import health

# Load configuration from .env file
load_dotenv()

CATEGORIES_PATH = os.path.join(os.path.dirname(__file__), "categories.json")

mcp = FastMCP("Expense Tracker")
pool = None

async def get_pool():
    """Lazy initialize the database connection pool and create tables if they do not exist"""
    global pool
    if pool is None:
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            raise ValueError("DATABASE_URL environment variable must be set to run this server.")
        pool = await asyncpg.create_pool(dsn=db_url, statement_cache_size=0)
        async with pool.acquire() as conn:
            # Create users table with token verification
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(100) UNIQUE NOT NULL,
                    token VARCHAR(255) NOT NULL
                );
            """)
            # Create expenses table referencing users
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS expenses (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    date DATE NOT NULL,
                    amount DOUBLE PRECISION NOT NULL,
                    category VARCHAR(100) NOT NULL,
                    subcategory VARCHAR(100) DEFAULT '',
                    note TEXT DEFAULT ''
                );
            """)
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
    return pool

async def get_authenticated_user_id(conn) -> int:
    """
    Retrieves and authenticates the user.
    For local development, falls back to DEFAULT_USER / getpass.getuser() with zero setup.
    """
    username = os.environ.get("DEFAULT_USER") or getpass.getuser() or "anonymous"
    token = os.environ.get("DEFAULT_TOKEN") or "local_dev_token"
            
    username = username.strip()
    token = token.strip()
    
    # Query database and match/register
    row = await conn.fetchrow("SELECT id FROM users WHERE token = $1", token)
    if row is None:
        user_id = await conn.fetchval(
            "INSERT INTO users (username, token) VALUES ($1, $2) RETURNING id",
            username, token
        )
        return user_id
    else:
        return row["id"]

@mcp.tool
async def add_expense(date: str, amount: float, category: str, subcategory: str = "", note: str = ""):
    """Add an expense to the database.
    """
    db_pool = await get_pool()
    async with db_pool.acquire() as conn:
        user_id = await get_authenticated_user_id(conn)
        parsed_date = pydate.fromisoformat(date)
        expense_id = await conn.fetchval(
            """
            INSERT INTO expenses (user_id, date, amount, category, subcategory, note)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
            """,
            user_id, parsed_date, amount, category, subcategory, note
        )
        return {"status": "ok", "id": expense_id}

@mcp.tool
async def list_expenses(start_date: str, end_date: str):
    """
    List all expenses from the database within a date range (inclusive).
    If the list contains more than 50 items, it truncates the inline results to the first 50
    and exports the full dataset to a downloadable CSV spreadsheet.
    """
    db_pool = await get_pool()
    async with db_pool.acquire() as conn:
        user_id = await get_authenticated_user_id(conn)
        parsed_start = pydate.fromisoformat(start_date)
        parsed_end = pydate.fromisoformat(end_date)
        rows = await conn.fetch(
            """
            SELECT id, date::text, amount, category, subcategory, note
            FROM expenses
            WHERE user_id = $1 AND date BETWEEN $2 AND $3
            ORDER BY id ASC
            """,
            user_id, parsed_start, parsed_end
        )
        
        total_count = len(rows)
        if total_count > 50:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Expenses"
            ws.append(["ID", "Date", "Amount", "Category", "Subcategory", "Note"])
            for r in rows:
                ws.append([r["id"], r["date"], r["amount"], r["category"], r["subcategory"], r["note"]])
                
            for col in ws.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = openpyxl.utils.get_column_letter(col[0].column)
                ws.column_dimensions[col_letter].width = max(max_len + 3, 10)
                
            exports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports")
            os.makedirs(exports_dir, exist_ok=True)
            export_filename = f"expenses_{start_date}_to_{end_date}.xlsx"
            export_path = os.path.join(exports_dir, export_filename)
            wb.save(export_path)
            
            file_url = f"file:///{export_path.replace(os.sep, '/')}"
            return {
                "status": "ok",
                "message": f"Retrieved {total_count} expenses. The list is long, so we have truncated the inline list to the first 50 items and exported the complete dataset to a downloadable Excel sheet.",
                "export_url": file_url,
                "data": [dict(row) for row in rows[:50]]
            }
            
        return [dict(row) for row in rows]

@mcp.tool
async def expense_breakdown(
    start_date: str,
    end_date: str,
    group_by: str = "category",
    breakdown: str = None,
    category: str = None,
    subcategory: str = None
) -> list:
    """
    Summarize and breakdown expenses by columns or time units within a date range.
    
    :param start_date: Start date in YYYY-MM-DD format (inclusive).
    :param end_date: End date in YYYY-MM-DD format (inclusive).
    :param group_by: Dimension to group by: 'category', 'subcategory', 'note', or 'date'. Defaults to 'category'.
    :param breakdown: Date grouping unit: 'day', 'month', or 'year'. Defaults to 'day' if group_by is 'date'.
    :param category: Optional filter by category name.
    :param subcategory: Optional filter by subcategory name.
    :return: A list of summarized expense groups with total amounts and transaction counts.
    """
    if group_by not in ["category", "subcategory", "note", "date"]:
        raise ValueError("Invalid group_by. Allowed: 'category', 'subcategory', 'note', 'date'.")
        
    if breakdown and breakdown not in ["day", "month", "year"]:
        raise ValueError("Invalid breakdown. Allowed: 'day', 'month', 'year'.")

    db_pool = await get_pool()
    async with db_pool.acquire() as conn:
        user_id = await get_authenticated_user_id(conn)
        parsed_start = pydate.fromisoformat(start_date)
        parsed_end = pydate.fromisoformat(end_date)
        
        # Determine select column
        select_col = "category"
        if group_by == "subcategory":
            select_col = "subcategory"
        elif group_by == "note":
            select_col = "note"
        elif group_by == "date":
            b_unit = breakdown or "day"
            if b_unit == "day":
                select_col = "date::text"
            elif b_unit == "month":
                select_col = "DATE_TRUNC('month', date)::date::text"
            elif b_unit == "year":
                select_col = "DATE_TRUNC('year', date)::date::text"
                
        # Build query
        query = f"""
            SELECT {select_col} as group_dimension, SUM(amount) as total_amount, COUNT(id) as transaction_count
            FROM expenses
            WHERE user_id = $1 AND date BETWEEN $2 AND $3
        """
        params = [user_id, parsed_start, parsed_end]
        param_idx = 4
        
        if category:
            try:
                matched_cat, matched_sub = budget.validate_category_and_subcategory(category, subcategory)
            except ValueError:
                return []
                
            query += f" AND category = ${param_idx}"
            params.append(matched_cat)
            param_idx += 1
            if matched_sub:
                query += f" AND subcategory = ${param_idx}"
                params.append(matched_sub)
                param_idx += 1
        elif subcategory:
            query += f" AND subcategory = ${param_idx}"
            params.append(subcategory)
            param_idx += 1
            
        query += " GROUP BY group_dimension ORDER BY group_dimension ASC"
        
        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]


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
    if not any([expense_ids, start_date, end_date, category, subcategory]):
        return {
            "status": "error",
            "message": (
                "At least one filter (expense_ids, start_date, end_date, "
                "category, or subcategory) must be specified to delete expenses."
            )
        }

    db_pool = await get_pool()
    async with db_pool.acquire() as conn:
        user_id = await get_authenticated_user_id(conn)
        
        # Build query dynamically
        query = "DELETE FROM expenses WHERE user_id = $1"
        params = [user_id]
        param_idx = 2
        
        if expense_ids:
            query += f" AND id = ANY(${param_idx}::integer[])"
            params.append(expense_ids)
            param_idx += 1
            
        if start_date:
            parsed_start = pydate.fromisoformat(start_date)
            if end_date:
                parsed_end = pydate.fromisoformat(end_date)
                query += f" AND date BETWEEN ${param_idx} AND ${param_idx+1}"
                params.extend([parsed_start, parsed_end])
                param_idx += 2
            else:
                query += f" AND date >= ${param_idx}"
                params.append(parsed_start)
                param_idx += 1
        elif end_date:
            parsed_end = pydate.fromisoformat(end_date)
            query += f" AND date <= ${param_idx}"
            params.append(parsed_end)
            param_idx += 1
            
        if category:
            query += f" AND category = ${param_idx}"
            params.append(category)
            param_idx += 1
            
        if subcategory:
            query += f" AND subcategory = ${param_idx}"
            params.append(subcategory)
            param_idx += 1
            
        query += " RETURNING id"
        
        rows = await conn.fetch(query, *params)
        deleted_ids = [row["id"] for row in rows]
        
        return {
            "status": "ok",
            "deleted_count": len(deleted_ids),
            "deleted_ids": deleted_ids
        }

@mcp.tool
async def update_expenses(
    expense_ids: list[int] = None,
    filter_start_date: str = None,
    filter_end_date: str = None,
    filter_category: str = None,
    filter_subcategory: str = None,
    date: str = None,
    amount: float = None,
    category: str = None,
    subcategory: str = None,
    note: str = None
) -> dict:
    """
    Update expenses matching the target filters with the specified values.
    At least one target filter and one update value must be provided.
    All provided filters are combined using AND.
    
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
    :return: A status dictionary indicating status and number of updated records.
    """
    if not any([expense_ids, filter_start_date, filter_end_date, filter_category, filter_subcategory]):
        return {
            "status": "error",
            "message": (
                "At least one target filter (expense_ids, filter_start_date, "
                "filter_end_date, filter_category, or filter_subcategory) must be specified."
            )
        }
        
    if not any([date is not None, amount is not None, category is not None, subcategory is not None, note is not None]):
        return {
            "status": "error",
            "message": (
                "At least one field value (date, amount, category, subcategory, "
                "or note) must be specified to update."
            )
        }

    db_pool = await get_pool()
    async with db_pool.acquire() as conn:
        user_id = await get_authenticated_user_id(conn)
        
        set_clauses = []
        params = []
        param_idx = 1
        
        # Add SET values
        if date is not None:
            set_clauses.append(f"date = ${param_idx}")
            params.append(pydate.fromisoformat(date))
            param_idx += 1
            
        if amount is not None:
            set_clauses.append(f"amount = ${param_idx}")
            params.append(amount)
            param_idx += 1
            
        if category is not None:
            set_clauses.append(f"category = ${param_idx}")
            params.append(category)
            param_idx += 1
            
        if subcategory is not None:
            set_clauses.append(f"subcategory = ${param_idx}")
            params.append(subcategory)
            param_idx += 1
            
        if note is not None:
            set_clauses.append(f"note = ${param_idx}")
            params.append(note)
            param_idx += 1
            
        # Add WHERE values
        where_clauses = [f"user_id = ${param_idx}"]
        params.append(user_id)
        param_idx += 1
        
        if expense_ids:
            where_clauses.append(f"id = ANY(${param_idx}::integer[])")
            params.append(expense_ids)
            param_idx += 1
            
        if filter_start_date:
            parsed_start = pydate.fromisoformat(filter_start_date)
            if filter_end_date:
                parsed_end = pydate.fromisoformat(filter_end_date)
                where_clauses.append(f"date BETWEEN ${param_idx} AND ${param_idx+1}")
                params.extend([parsed_start, parsed_end])
                param_idx += 2
            else:
                where_clauses.append(f"date >= ${param_idx}")
                params.append(parsed_start)
                param_idx += 1
        elif filter_end_date:
            parsed_end = pydate.fromisoformat(filter_end_date)
            where_clauses.append(f"date <= ${param_idx}")
            params.append(parsed_end)
            param_idx += 1
            
        if filter_category:
            where_clauses.append(f"category = ${param_idx}")
            params.append(filter_category)
            param_idx += 1
            
        if filter_subcategory:
            where_clauses.append(f"subcategory = ${param_idx}")
            params.append(filter_subcategory)
            param_idx += 1
            
        query = f"UPDATE expenses SET {', '.join(set_clauses)} WHERE {' AND '.join(where_clauses)} RETURNING id"
        
        rows = await conn.fetch(query, *params)
        updated_ids = [row["id"] for row in rows]
        
        return {
            "status": "ok",
            "updated_count": len(updated_ids),
            "updated_ids": updated_ids
        }

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
    
    :param budget_type: 'overall', 'category', or 'subcategory'.
    :param amount: Budget limit amount.
    :param period: 'weekly', 'monthly', 'quarterly', or 'yearly'.
    :param start_date: ISO start date (YYYY-MM-DD).
    :param end_date: ISO end date (YYYY-MM-DD).
    :param category: Optional category name.
    :param subcategory: Optional subcategory name.
    :param budgets: Optional list of budget dictionaries for bulk insertion.
    :return: A status dictionary containing details of the created budgets.
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

@mcp.tool
async def list_budgets(
    budget_type: str = None,
    category: str = None,
    subcategory: str = None,
    period: str = None
) -> list:
    """
    List all budgets matching the optional filters.
    All provided filters are combined using AND.
    
    :param budget_type: Optional filter by scope: 'overall', 'category', or 'subcategory'.
    :param category: Optional filter by category name.
    :param subcategory: Optional filter by subcategory name.
    :param period: Optional filter by duration: 'weekly', 'monthly', 'quarterly', or 'yearly'.
    :return: A list of budgets matching the filters.
    """
    db_pool = await get_pool()
    async with db_pool.acquire() as conn:
        user_id = await get_authenticated_user_id(conn)
        return await budget.list_budgets_impl(
            conn, user_id,
            budget_type=budget_type,
            category=category,
            subcategory=subcategory,
            period=period
        )

@mcp.tool
async def update_budgets(
    budget_ids: list[int] = None,
    filter_budget_type: str = None,
    filter_category: str = None,
    filter_subcategory: str = None,
    filter_period: str = None,
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
    All provided filters are combined using AND.
    
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
    :return: A status dictionary indicating status and number of updated records.
    """
    db_pool = await get_pool()
    async with db_pool.acquire() as conn:
        user_id = await get_authenticated_user_id(conn)
        return await budget.update_budgets_impl(
            conn, user_id,
            budget_ids=budget_ids,
            filter_budget_type=filter_budget_type,
            filter_category=filter_category,
            filter_subcategory=filter_subcategory,
            filter_period=filter_period,
            budget_type=budget_type,
            amount=amount,
            period=period,
            start_date=start_date,
            end_date=end_date,
            category=category,
            subcategory=subcategory
        )

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
    db_pool = await get_pool()
    async with db_pool.acquire() as conn:
        user_id = await get_authenticated_user_id(conn)
        return await budget.delete_budgets_impl(
            conn, user_id,
            budget_ids=budget_ids,
            start_date=start_date,
            end_date=end_date,
            budget_type=budget_type,
            category=category,
            subcategory=subcategory,
            period=period
        )

@mcp.tool
async def compare_budget_vs_expenses(
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
    db_pool = await get_pool()
    async with db_pool.acquire() as conn:
        user_id = await get_authenticated_user_id(conn)
        return await budget.compare_budget_vs_expenses_impl(
            conn, user_id,
            reference_date=reference_date,
            budget_type=budget_type,
            category=category,
            subcategory=subcategory,
            period=period
        )

@mcp.tool
async def expense_summary(
    period: str = None,
    group_by: str = None,
    category: str = None,
    subcategory: str = None,
    start_date: str = None,
    end_date: str = None
) -> dict:
    """
    Generate an analytical expense summary with a rich Matplotlib chart.
    At least one grouping dimension ('period' or 'group_by') is recommended.
    
    :param period: Time aggregation: 'weekly', 'monthly', 'quarterly', 'yearly'.
    :param group_by: Column to group by: 'category', 'subcategory'.
    :param category: Optional filter by category.
    :param subcategory: Optional filter by subcategory.
    :param start_date: Optional filter to include expenses on or after this ISO date (YYYY-MM-DD).
    :param end_date: Optional filter to include expenses on or before this ISO date (YYYY-MM-DD).
    :return: A status dictionary containing the path to the generated chart image, markdown links, and tabular data.
    """
    db_pool = await get_pool()
    async with db_pool.acquire() as conn:
        user_id = await get_authenticated_user_id(conn)
        return await analytics.expense_summary_impl(
            conn, user_id,
            period=period,
            group_by=group_by,
            category=category,
            subcategory=subcategory,
            start_date=start_date,
            end_date=end_date
        )

@mcp.tool
async def financial_health_score(reference_month: str = None) -> dict:
    """
    Calculate a deterministic financial health score and feedback metrics.
    
    :param reference_month: Optional target month to evaluate in YYYY-MM format. Defaults to current month.
    :return: A status dictionary containing the overall health score, grade, breakdown of the 6 KPIs, and detailed reasons.
    """
    db_pool = await get_pool()
    async with db_pool.acquire() as conn:
        user_id = await get_authenticated_user_id(conn)
        return await health.financial_health_score_impl(
            conn, user_id,
            reference_month=reference_month
        )

@mcp.resource("expense://categories", mime_type="application/json")
def resources():
    """Read Fresh each time so you can edit the file without restarting"""
    if not os.path.exists(CATEGORIES_PATH):
        # Default placeholder categories if file doesn't exist
        return '["Food", "Travel", "Utilities", "Entertainment", "Health", "Other"]'
    with open(CATEGORIES_PATH, 'r', encoding="utf-8") as f:
        return f.read()

if __name__ == '__main__':
    mcp.run()
