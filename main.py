from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers
import asyncpg
import os
import getpass
from dotenv import load_dotenv
from datetime import date as pydate

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
    return pool

async def get_authenticated_user_id(conn) -> int:
    """
    Retrieves and authenticates the user using x-username and x-token headers.
    If no HTTP headers are present (e.g. local stdio run), falls back to 
    DEFAULT_USER/DEFAULT_TOKEN env variables, then OS username and a local dev token.
    """
    headers = get_http_headers() or {}
    
    # Resolve username and token with fallbacks
    username = headers.get("x-username") or os.environ.get("DEFAULT_USER") or getpass.getuser() or "anonymous"
    token = headers.get("x-token") or os.environ.get("DEFAULT_TOKEN") or "local_dev_token"
    
    username = username.strip()
    token = token.strip()
    
    # Query user details
    row = await conn.fetchrow("SELECT id, token FROM users WHERE username = $1", username)
    
    if row is None:
        # Auto-register new user with provided token
        user_id = await conn.fetchval(
            "INSERT INTO users (username, token) VALUES ($1, $2) RETURNING id",
            username, token
        )
        return user_id
    else:
        # Verify token match
        stored_token = row["token"]
        if stored_token != token:
            raise PermissionError(f"Authentication failed: Invalid token for user '{username}'.")
        return row["id"]

@mcp.tool
async def add_expense(date: str, amount: float, category: str, subcategory: str = "", note: str = ""):
    """Add an expense to the database"""
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
    """List all expenses from the database within a date range (inclusive)"""
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
        return [dict(row) for row in rows]

@mcp.tool
async def summarize(start_date: str, end_date: str, category: str = None):
    """Summarize expenses by category on the basis of the date range"""
    db_pool = await get_pool()
    async with db_pool.acquire() as conn:
        user_id = await get_authenticated_user_id(conn)
        parsed_start = pydate.fromisoformat(start_date)
        parsed_end = pydate.fromisoformat(end_date)
        
        query = """
            SELECT category, SUM(amount) as total_amount
            FROM expenses
            WHERE user_id = $1 AND date BETWEEN $2 AND $3
        """
        params = [user_id, parsed_start, parsed_end]
        
        if category:
            query += " AND category = $4"
            params.append(category)
            
        query += " GROUP BY category ORDER BY category ASC"
        
        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]

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
