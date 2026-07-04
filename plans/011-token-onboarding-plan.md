# Implementation Plan: Chat-Level Token-Based Onboarding & Multi-User Isolation

This plan details the implementation steps to add secure multi-user isolation on cloud deployments of the Finance Intelligence MCP server. It implements a token-based authentication system by adding a `token` parameter directly to all MCP tools, resolving Claude's lack of support for static headers/query parameters on remote connectors.

## User Review Required

- **No Breaking Changes for Local Runs**: Local development setups continue to run out-of-the-box using the default developer configuration fallback.
- **Enforced Security on Cloud**: Cloud deployments (HTTP/SSE connections) will require a valid UUID token passed as a tool parameter. Attempts to run standard tools without a token will be rejected with an authentication prompt guiding users to register or provide their token.

---

## Proposed Changes

### FastMCP Integration & Auth Engine

#### [MODIFY] [main.py](file:///c:/Users/Admin/Desktop/Finance%20Intelligence%20MCP/main.py)
- Update `get_authenticated_user_id(conn, token: str = None)`:
  - If `token` argument is provided, authenticate using it.
  - If `token` is not provided:
    - Check headers. If it's a cloud run (headers is not `None`), and header token is missing/default, reject the request with `PermissionError` asking the user to provide their token in the chat or register a new one.
    - If it's a local run, fallback to OS username/DEFAULT_USER fallback.
- Update all `@mcp.tool` signatures in `main.py` to add `token: str = None` as the final parameter, and pass it to `get_authenticated_user_id`.
  - `add_expense`
  - `list_expenses`
  - `expense_breakdown`
  - `add_budget`
  - `list_budgets`
  - `delete_budgets`
  - `compare_budget_vs_expenses`
  - `expense_summary`
  - `financial_health_score`
- Update `@mcp.tool` for `register_user()`:
  - Generates a cryptographically secure random UUID4 token.
  - Registers the user in the database.
  - Returns a success report containing the private token and instructions to provide it in the chat.

---

## Verification Plan

### Automated Tests
- Update `scratch/test_token_onboarding.py` to check the updated `token` parameter behavior.
- Run integration tests to ensure that local runs, cloud rejections, and parameter-based cloud authentication function flawlessly.
