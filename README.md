# Finance Intelligence MCP Server

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![FastMCP](https://img.shields.io/badge/framework-FastMCP-brightgreen.svg)](https://github.com/jlowin/fastmcp)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP Specification](https://img.shields.io/badge/MCP-Compatible-orange.svg)](https://modelcontextprotocol.io/)
[![Database](https://img.shields.io/badge/database-PostgreSQL-blue.svg)](https://www.postgresql.org/)

Finance Intelligence MCP is a production-ready **Model Context Protocol (MCP)** server that enables AI assistants (like Claude, Cursor, and others) to securely manage and analyze personal finances through natural language. 

Released under the MIT License and designed to be extended with additional finance tools.

---

## 🔍 Overview

Unlike standard cloud-based personal finance apps, **Finance Intelligence MCP** keeps all financial data under your absolute control.

*   **No Accounts / Subscriptions**: Direct connection to your private database with zero SaaS dependencies.
*   **Zero Telemetry**: Your financial logs never go to external analytic APIs.
*   **Full AI Context**: Your AI assistant can query history, check budget status, make charts, and answer financial questions instantly.



---

## 🛠️ Architecture

```
   ┌────────────────────────────────┐
   │           MCP Client           │
   │  (Claude Desktop, Cursor, etc) │
   └───────────────┬────────────────┘
                   │
                   │ (STDIO Transport Protocol)
                   ▼
   ┌────────────────────────────────┐
   │  Finance Intelligence Server   │
   │           (Local)              │
   └───────────────┬────────────────┘
                   │
                   │ (Direct SQL Pool Connection)
                   ▼
   ┌────────────────────────────────┐
   │       PostgreSQL Database      │
   │ (Supabase, Local, RDS, etc)    │
   └────────────────────────────────┘
```

---

## ✨ Features

*   **Expense Operations**: Create, view, edit, and bulk-delete expense entries.
*   **Multi-level Budgeting**: Set limits for `overall` spending, specific `category` thresholds, or down to nested `subcategory` targets.
*   **Analytics Breakdowns**: Aggregate expenses by category, subcategory, notes, or dates over weekly/monthly/yearly time blocks.
*   **Visual Charts**: Exposes tools that generate Matplotlib line/bar charts of historical spending automatically.
*   **Excel Spreadsheet Export**: Truncates long list responses and generates download-ready Excel spreadsheets for massive datasets.
*   **Financial Health Scoring**: Calculates a deterministic financial health score grade based on 6 core personal finance KPIs.

---

## ⚙️ Requirements & Compatibility

*   **Transport**: `stdio`
*   **Supported Platforms**:
    *   Windows
    *   macOS
    *   Linux
*   **Python Compatibility**: Python 3.10, 3.11, and 3.12 (Tested)
*   **Database**: PostgreSQL 12+ (e.g. Supabase, RDS, or local Postgres)
*   **Supported Clients**:
    *   Claude Desktop
    *   Cursor
    *   *Compatible with any MCP client supporting stdio.*

---

## 💾 Installation & Setup

### 1. Quick Setup (Shortcut)
If you have `uv` installed, get started in 2 lines:
```bash
git clone https://github.com/Ronit-019/Finance-Intelligence-MCP.git
cd Finance-Intelligence-MCP
uv sync
```

### 2. Detailed Installation

#### Step A: Get a PostgreSQL Connection URL
The easiest, free option is **Supabase**:
1. Go to [Supabase](https://supabase.com/) and create a free project.
2. Go to **Project Settings** (gear icon) > **Database**.
3. Under **Connection string**, select **URI** and copy the string.
   * *Example*: `postgresql://postgres.[your-project-ref]:[your-password]@aws-0-us-east-1.pooler.supabase.com:5432/postgres`
   * *(Replace `[your-password]` with your database password).*

#### Step B: Clone the Repository
Clone the codebase to a directory on your machine:
```bash
git clone https://github.com/Ronit-019/Finance-Intelligence-MCP.git
cd Finance-Intelligence-MCP
```
Copy the absolute path of this directory (e.g. `C:/Users/Admin/Desktop/Finance-Intelligence-MCP`).
*Note: Always use forward slashes (`/`) for paths in JSON configs.*

#### Step C: Install Dependencies
If you do not have `uv` installed, install from the project metadata:
```bash
pip install -e .
```

---

### 3. Client Integration

#### Claude Desktop Setup
1. Open your Claude configuration file (`claude_desktop_config.json`):
   * **Windows**: Press `Win + R`, paste `%APPDATA%\Claude\claude_desktop_config.json` and press Enter.
   * **macOS**: Paste `~/Library/Application Support/Claude/claude_desktop_config.json` in Finder's Go to Folder.
2. Add this entry to `mcpServers`:

```json
{
  "mcpServers": {
    "finance-intelligence": {
      "command": "uv",
      "args": [
        "--directory",
        "REPLACE_WITH_ABSOLUTE_PATH_TO_CLONED_DIRECTORY",
        "run",
        "python",
        "main.py"
      ],
      "env": {
        "DATABASE_URL": "REPLACE_WITH_YOUR_SUPABASE_CONNECTION_STRING"
      }
    }
  }
}
```
3. Save and completely **restart Claude Desktop**.

#### Cursor IDE Setup
1. Go to **Settings** > **Features** > **MCP**.
2. Click **+ Add New MCP Server**:
   * **Name**: `Finance Intelligence`
   * **Type**: `command`
   * **Command**: 
     ```bash
     uv --directory "REPLACE_WITH_ABSOLUTE_PATH_TO_CLONED_DIRECTORY" run python main.py
     ```
3. Click **+ Add Env Var**:
   * **Key**: `DATABASE_URL`
   * **Value**: `REPLACE_WITH_YOUR_SUPABASE_CONNECTION_STRING`
4. Click **Save** and refresh.

---

## 💬 Example Prompts

Once configured, try talking to your AI assistant:
*   *"Add ₹250 for lunch today under food."*
*   *"Show my spending breakdown this month."*
*   *"Generate an Excel report of all my expenses between May and July."*
*   *"Am I exceeding my monthly budget limit?"*
*   *"How much did I spend on dining out this week?"*
*   *"Calculate my monthly financial health score and give me feedback."*
*   *"Generate a spending chart for the last 30 days."*

---

## 🛠️ Available Tools

The server registers 12 core tools on the client:

| Tool Name | Parameters | Description |
| :--- | :--- | :--- |
| `add_expense` | `date`, `amount`, `category`, `subcategory`, `note` | Inserts a new expense transaction. |
| `list_expenses` | `start_date`, `end_date` | Lists transactions, exports to Excel if count > 50. |
| `expense_breakdown`| `start_date`, `end_date`, `group_by`, `breakdown`, `category`, `subcategory` | Aggregates spending sums and counts. |
| `delete_expenses` | `expense_ids`, `start_date`, `end_date`, `category`, `subcategory` | Deletes expenses matching filters. |
| `update_expenses` | `expense_ids`, `filter_...`, `date`, `amount`, `category`, `subcategory`, `note` | Edits expense records. |
| `create_budget` | `budget_type`, `amount`, `period`, `start_date`, `end_date`, `category`, `subcategory`, `budgets` | Registers new spending limits. |
| `list_budgets` | `budget_type`, `category`, `subcategory`, `period` | Returns registered budgets. |
| `update_budgets` | `budget_ids`, `filter_...`, `budget_type`, `amount`, `period`, `start_date`, `end_date`, `category`, `subcategory` | Modifies active budgets. |
| `delete_budgets` | `budget_ids`, `start_date`, `end_date`, `budget_type`, `category`, `subcategory`, `period` | Deletes target budget limits. |
| `compare_budget_vs_expenses` | `reference_date`, `budget_type`, `category`, `subcategory`, `period` | Compares budget vs actual spending. |
| `expense_summary` | `period`, `group_by`, `category`, `subcategory`, `start_date`, `end_date` | Generates a Matplotlib line/bar chart. |
| `financial_health_score` | `reference_month` | Evaluates 6 key personal finance indicators. |

---

## 💡 Troubleshooting

### 1. `uv: command not found`
If the client cannot locate `uv`, update your config file to run standard Python:
* Ensure you ran `pip install -e .` inside the repository.
* Update config:
```json
"finance-intelligence": {
  "command": "python",
  "args": [
    "REPLACE_WITH_ABSOLUTE_PATH_TO_CLONED_DIRECTORY/main.py"
  ],
  "env": {
    "DATABASE_URL": "REPLACE_WITH_YOUR_SUPABASE_CONNECTION_STRING"
  }
}
```

### 2. Invalid `DATABASE_URL` / PostgreSQL Connection Errors
* Make sure you replaced `[your-password]` with your actual database password in the Supabase URI string.
* Ensure there are no surrounding spaces or special characters in the URL string.
* Verify your Supabase instance is active and not paused.

### 3. Claude Not Detecting the Server
* Double check that the folder paths in `claude_desktop_config.json` use **forward slashes** (`/`), even on Windows.
* Check the logs at `%APPDATA%\Claude\logs\mcp*.log` (Windows) or `~/Library/Logs/Claude/mcp*.log` (macOS) to see the exact startup error.

---

## 📁 Repository Structure
```
├── src/                       # Helper packages
│   ├── __init__.py
│   ├── budget.py              # Budget database operations
│   ├── analytics.py           # Breakdown aggregations & Matplotlib routines
│   └── health.py              # KPIs and financial health calculator
├── main.py                    # FastMCP Server application
├── categories.json            # Category mapping catalog
├── pyproject.toml             # Dependencies
├── LICENSE                    # MIT License file
└── README.md                  # This file
```

---

## 🗺️ Roadmap
*   Support for HTTP / SSE transport protocols.
*   Multi-currency translation and automated updates.
*   Automated recurring subscription and salary entries.
*   Import from CSV / bank statement formats.
*   Portfolio and investment tracking features.

---

## 🤝 Contributing
Contributions, bug reports, and feature requests are welcome! 
Please open an issue before submitting major changes or pull requests.

---

## 📄 License
This project is licensed under the [MIT License](LICENSE) - see the LICENSE file for details.
