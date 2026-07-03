# Finance Intelligence MCP Server

[![MCP Specification](https://img.shields.io/badge/MCP-Specification-orange.svg)](https://modelcontextprotocol.io/)
[![Python Version](https://img.shields.io/badge/python-3.14%2B-blue.svg)](https://www.python.org/)
[![FastMCP](https://img.shields.io/badge/framework-FastMCP-brightgreen.svg)](https://github.com/jlowin/fastmcp)
[![Database](https://img.shields.io/badge/database-PostgreSQL-blue.svg)](https://www.postgresql.org/)

A production-grade **Model Context Protocol (MCP)** server built with **FastMCP** that provides advanced financial intelligence and expense management capabilities. This server allows LLMs (like Claude, Cursor, etc.) to securely interact with a PostgreSQL/Supabase database, enabling smart expense tracking, multi-level budgeting (overall, category, subcategory), multi-tenant token-based authentication, and transaction analysis.

---

## 🚀 Key Features

*   **Comprehensive Expense Tracking**: Log, search, update, and bulk-delete expenses using complex relational criteria.
*   **Hierarchical Budgeting**: Set and monitor spending limits across different scopes:
    *   `overall` (global limit)
    *   `category` (e.g., limit food spending)
    *   `subcategory` (e.g., limit dining out subcategory specifically)
    *   *Supports bulk/batch budget creation.*
*   **Rich Category Catalog**: Interactive resource listing that maps standard categories to their subcategories (configured via JSON).
*   **Multi-tenant Token Authentication**: Built-in header-based authentication validation (`x-username` and `x-token`) with auto-registration for secure, multi-user deployments.
*   **Fast & Modern Stack**: Fully asynchronous database communication utilizing `asyncpg` and standard SQL schema execution.

---

## 🗄️ Database Schema

The server automatically initializes three tables inside the PostgreSQL target specified in the connection string:

### 1. `users` Table
Stores registered users and their secret tokens.
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `SERIAL` | `PRIMARY KEY` | Unique ID of the user. |
| `username` | `VARCHAR(100)` | `UNIQUE`, `NOT NULL` | The user's unique username. |
| `token` | `VARCHAR(255)` | `NOT NULL` | The authentication token. |

### 2. `expenses` Table
Stores individual expense line items.
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `SERIAL` | `PRIMARY KEY` | Unique ID of the expense. |
| `user_id` | `INTEGER` | `REFERENCES users(id) ON DELETE CASCADE` | The owner of the transaction. |
| `date` | `DATE` | `NOT NULL` | ISO date of the expense. |
| `amount` | `DOUBLE PRECISION`| `NOT NULL` | Amount spent. |
| `category` | `VARCHAR(100)` | `NOT NULL` | Categorization from `categories.json`. |
| `subcategory`| `VARCHAR(100)` | Default: `''` | Subcategorization. |
| `note` | `TEXT` | Default: `''` | Optional descriptive note. |

### 3. `budgets` Table
Tracks spending limits over defined periods.
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `SERIAL` | `PRIMARY KEY` | Unique budget record ID. |
| `user_id` | `INTEGER` | `REFERENCES users(id) ON DELETE CASCADE` | Owner of the budget limit. |
| `budget_type`| `VARCHAR(20)` | `NOT NULL` (Check: `overall`, `category`, `subcategory`) | The scope/level of the budget. |
| `category` | `VARCHAR(100)` | Default: `NULL` | Required for category & subcategory scopes. |
| `subcategory`| `VARCHAR(100)` | Default: `NULL` | Required only for subcategory scope. |
| `amount` | `DOUBLE PRECISION`| `NOT NULL` | Allocated amount. |
| `period` | `VARCHAR(20)` | `NOT NULL` (Check: `weekly`, `monthly`, `quarterly`, `yearly`) | Recurrence period. |
| `start_date` | `DATE` | `NOT NULL` | Effectiveness start date. |
| `end_date` | `DATE` | `NOT NULL` | Expiry/evaluation end date. |

---

## ⚙️ Configuration & Installation

### 1. Prerequisites
- **Python 3.14+**
- **PostgreSQL Database** (e.g., Supabase, RDS, or local)
- [**uv**](https://github.com/astral-sh/uv) (recommended Python package manager)

### 2. Clone and Setup Environment
Clone the repository, then copy/create a `.env` file in the root directory:

```bash
# Clone the repository
git clone https://github.com/Ronit-019/Finance-Intelligence-MCP.git
cd Finance-Intelligence-MCP

# Create a .env file from the environment variables template
cat <<EOT >> .env
DATABASE_URL=postgresql://<username>:<password>@<host>:<port>/<dbname>
DEFAULT_USER=admin
DEFAULT_TOKEN=local_dev_token
EOT
```

*Note: In local testing over stdio where HTTP headers are unavailable, the server falls back to `DEFAULT_USER` and `DEFAULT_TOKEN` for database queries.*

### 3. Install Dependencies
Install dependencies directly using `uv` (which reads from `pyproject.toml` and locks in `uv.lock`):

```bash
# Sync dependencies and create local virtual environment
uv sync
```

Alternatively, install using standard pip:
```bash
pip install -r pyproject.toml
```

---

## 🖥️ Running the Server

### Development Mode (with Hot Reloading)
FastMCP offers an interactive inspector and dev environment which is great for building:
```bash
uv run fastmcp dev main.py
```
This launches the server and opens a development web UI (typically at `http://localhost:5173`) where you can trigger and inspect tool runs directly.

### Production Run (via Stdio)
To start the server using stdio transport:
```bash
uv run python main.py
```

---

## 🧩 MCP Client Integration

Add the server to your preferred Model Context Protocol client's configuration file.

### Claude Desktop
Open your configuration file at:
*   **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
*   **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

Add the following config:

```json
{
  "mcpServers": {
    "finance-intelligence": {
      "command": "uv",
      "args": [
        "--directory",
        "C:/Users/Admin/Desktop/Finance Intelligence MCP",
        "run",
        "python",
        "main.py"
      ],
      "env": {
        "DATABASE_URL": "postgresql://postgres.lyyfkiaamqnzpdglqhfe:PASSWORD@aws-1-ap-northeast-1.pooler.supabase.com:6543/postgres",
        "DEFAULT_USER": "admin",
        "DEFAULT_TOKEN": "local_dev_token"
      }
    }
  }
}
```

### Cursor IDE
1. Go to **Settings** > **Features** > **MCP**.
2. Click **+ Add New MCP Server**.
3. Fill in details:
   - **Name**: `Finance Intelligence`
   - **Type**: `command`
   - **Command**: `uv --directory "C:/Users/Admin/Desktop/Finance Intelligence MCP" run python main.py`

---

## 🛠️ MCP Tool Reference

LLMs can access and invoke these tools dynamically.

### 1. `add_expense`
Adds a transaction item to the database.
*   **Parameters**:
    *   `date` (str, Required): ISO format date (`YYYY-MM-DD`).
    *   `amount` (float, Required): Transaction amount (e.g. `45.50`).
    *   `category` (str, Required): Standard category (e.g. `food`, `travel`).
    *   `subcategory` (str, Optional): Nested subcategory (e.g. `groceries`, `flights`).
    *   `note` (str, Optional): Descriptive memo.
*   **Response**: `{"status": "ok", "id": 123}`

### 2. `list_expenses`
Retrieves expense list within a designated time window.
*   **Parameters**:
    *   `start_date` (str, Required): ISO format (`YYYY-MM-DD`).
    *   `end_date` (str, Required): ISO format (`YYYY-MM-DD`).
*   **Response**: A list of expense records matching criteria.

### 3. `summarize`
Summarizes transaction amounts grouped by category.
*   **Parameters**:
    *   `start_date` (str, Required): Start date window.
    *   `end_date` (str, Required): End date window.
    *   `category` (str, Optional): Retrieve only summary of a specific category.
*   **Response**: A list of aggregated categories and their total values.

### 4. `delete_expenses`
Performs clean-up of expenses according to filter options. *At least one filter must be passed to protect records.*
*   **Parameters**:
    *   `expense_ids` (list[int], Optional): Delete specific expense IDs.
    *   `start_date` (str, Optional): Clear expenses from this date onwards.
    *   `end_date` (str, Optional): Clear expenses up to this date (requires `start_date`).
    *   `category` (str, Optional): Delete a specific category.
    *   `subcategory` (str, Optional): Delete a specific subcategory.
*   **Response**: `{"status": "ok", "deleted_count": N, "deleted_ids": [...]}`

### 5. `update_expenses`
Allows dynamic modifications to set specific fields on target filters.
*   **Filters** (At least one required):
    *   `expense_ids` (list[int])
    *   `filter_start_date` (str)
    *   `filter_end_date` (str)
    *   `filter_category` (str)
    *   `filter_subcategory` (str)
*   **Update values** (At least one required):
    *   `date` (str), `amount` (float), `category` (str), `subcategory` (str), `note` (str).
*   **Response**: `{"status": "ok", "updated_count": N, "updated_ids": [...]}`

### 6. `create_budget`
Creates single or multiple budgets for the user. Supports simple single insertion or list-based bulk insertion.
*   **Parameters**:
    *   `budget_type` (str, Optional): `'overall'`, `'category'`, or `'subcategory'`.
    *   `amount` (float, Optional): Spending limit allocation.
    *   `period` (str, Optional): `'weekly'`, `'monthly'`, `'quarterly'`, or `'yearly'`.
    *   `start_date` (str, Optional): ISO start date.
    *   `end_date` (str, Optional): ISO end date.
    *   `category` (str, Optional): Filter category.
    *   `subcategory` (str, Optional): Filter subcategory.
    *   `budgets` (list[dict], Optional): List of budget dictionaries for bulk execution.
*   **Response**: `{"status": "ok", "created_count": N, "created_ids": [...]}`

### 7. `list_budgets`
Lists all budget items with optional parameter filtering.
*   **Parameters**:
    *   `budget_type` (str, Optional): Filter by scope limit.
    *   `category` (str, Optional): Filter by category.
    *   `subcategory` (str, Optional): Filter by subcategory.
    *   `period` (str, Optional): Filter by period.
*   **Response**: A list of matched budget entries.

### 8. `update_budgets`
Updates budget limits and criteria based on search filters. At least one target filter and one field value must be provided.
*   **Filters** (At least one required):
    *   `budget_ids` (list[int]): Update specific budget record IDs.
    *   `filter_budget_type` (str): Target budget scope (`overall`, `category`, `subcategory`).
    *   `filter_category` (str): Target category name.
    *   `filter_subcategory` (str): Target subcategory name.
    *   `filter_period` (str): Target period duration.
*   **Update values** (At least one required):
    *   `budget_type` (str): New budget scope.
    *   `amount` (float): New limit amount.
    *   `period` (str): New period duration.
    *   `start_date` (str): New ISO format start date.
    *   `end_date` (str): New ISO format end date.
    *   `category` (str): New category key.
    *   `subcategory` (str): New subcategory key.
*   **Response**: `{"status": "ok", "updated_count": N, "updated_ids": [...]}`

### 9. `delete_budgets`
Deletes budget limits and criteria based on search filters. At least one target filter must be provided.
*   **Filters** (At least one required):
    *   `budget_ids` (list[int]): Delete specific budget record IDs.
    *   `start_date` (str): Delete budgets starting on or after this date.
    *   `end_date` (str): Delete budgets ending on or before this date (requires `start_date`).
    *   `budget_type` (str): Delete budgets of a specific scope.
    *   `category` (str): Delete budgets of a specific category.
    *   `subcategory` (str): Delete budgets of a specific subcategory.
    *   `period` (str): Delete budgets of a specific period.
*   **Response**: `{"status": "ok", "deleted_count": N, "deleted_ids": [...]}`

### 10. `current_status`
Retrieves a real-time status dashboard comparing active budgets against actual expenses.
*   **Parameters**:
    *   `reference_date` (str, Optional): Check budgets active on this ISO date (`YYYY-MM-DD`). Defaults to today.
    *   `budget_type` (str, Optional): Filter by scope (`overall`, `category`, `subcategory`).
    *   `category` (str, Optional): Filter by category.
    *   `subcategory` (str, Optional): Filter by subcategory.
    *   `period` (str, Optional): Filter by duration (`weekly`, `monthly`, `quarterly`, `yearly`).
*   **Response**:
    ```json
    {
      "status": "ok",
      "reference_date": "2026-07-02",
      "budgets": [
        {
          "budget_id": 24,
          "budget_type": "overall",
          "category": null,
          "subcategory": null,
          "period": "monthly",
          "start_date": "2026-07-01",
          "end_date": "2026-07-31",
          "limit_amount": 1000.0,
          "total_spent": 180.0,
          "remaining": 820.0,
          "percentage_spent": 18.0,
          "status": "under_budget"
        }
      ]
    }
    ```

### 11. `expense_summary`
Generates time-series trend and grouping column analytics plots of actual user expenses, rendered via `matplotlib`.
*   **Parameters**:
    *   `period` (str, Optional): Time bucket to group by: `'weekly'`, `'monthly'`, `'quarterly'`, or `'yearly'`.
    *   `group_by` (str, Optional): Category split to group by: `'category'` or `'subcategory'`.
    *   `category` (str, Optional): Filter results to a specific category.
    *   `subcategory` (str, Optional): Filter results to a specific subcategory.
    *   `start_date` (str, Optional): Include expenses on or after this ISO date.
    *   `end_date` (str, Optional): Include expenses on or before this ISO date.
*   **Response**:
    ```json
    {
      "status": "ok",
      "chart_path": "c:\\Users\\Admin\\Desktop\\Finance Intelligence MCP\\charts\\expense_analysis.png",
      "chart_url": "file:///c:/Users/Admin/Desktop/Finance%20Intelligence%20MCP/charts/expense_analysis.png",
      "message": "Expense analytics trend chart generated successfully:\n\n![Expense Analytics Chart](file:///c:/Users/Admin/Desktop/Finance%20Intelligence%20MCP/charts/expense_analysis.png)",
      "data": [
        {
          "period_bucket": "2026-03-01",
          "total_amount": 180.0,
          "transaction_count": 2
        }
      ]
    }
    ```

---

## 📂 Resource Catalog

### 🌐 `expense://categories` (application/json)
Exposes the taxonomy tree containing allowed categories and subcategories defined in `categories.json`.
Example payload:
```json
{
  "food": ["groceries", "fruits_vegetables", "dining_out", "coffee_tea", "snacks", "other"],
  "travel": ["flights", "hotels", "train_bus", "local_transport", "other"],
  "utilities": ["electricity", "water", "gas", "internet_broadband", "mobile_phone", "other"]
  // ... extra nodes
}
```

---

## 📁 Repository Structure

```
├── .env                       # Local environment variables
├── pyproject.toml             # Project dependency & Python configuration
├── uv.lock                    # Dependency lockfile
├── main.py                    # FastMCP Server application & database setups
├── budget.py                  # Core budget business logic implementation
├── categories.json            # Categories and subcategories configuration
├── specs/                     # Feature specification files
└── plans/                     # Development and implementation plans
```

---

## 📝 License
This project is licensed under the MIT License. See LICENSE file for details (if applicable).
