# Implementation Plan: Token-Based Onboarding & Multi-User Isolation

This plan details the implementation steps to add secure multi-user isolation on cloud deployments of the Finance Intelligence MCP server. It implements a token-based authentication system supporting both headers (`x-token`) and URL query parameters (`?token=`), alongside a `register_user` onboarding tool.

## User Review Required

- **No Breaking Changes for Local Runs**: Local development setups continue to run out-of-the-box using the default developer configuration fallback.
- **Enforced Security on Cloud**: Cloud deployments (HTTP/SSE connections) will require a valid UUID token. Attempts to run standard tools without a token will be rejected with an authentication prompt guiding users to register.

---

## Proposed Changes

### FastMCP Integration & Auth Engine

#### [MODIFY] [main.py](file:///c:/Users/Admin/Desktop/Finance%20Intelligence%20MCP/main.py)
- Import `uuid` and `get_http_request` from `fastmcp.server.dependencies`.
- Update `get_authenticated_user_id(conn)` to:
  - Check if headers are present (detecting cloud/SSE connections).
  - Extract token from HTTP header `x-token` or query parameter `token` using Starlette's `request.query_params`.
  - Block requests if the token is missing or matches the default `"local_dev_token"`.
  - Perform database lookup solely by `token`.
- Add `@mcp.tool` for `register_user()`:
  - Generates a cryptographically secure random UUID4 token.
  - Registers the user in the database.
  - Returns a success report containing the private token and copy-pasteable configuration URL:
    `https://Finance-Intelligence-MCP.fastmcp.app/mcp?token=<UUID>`

---

## Verification Plan

### Automated Tests
- We will construct an integration test script inside `scratch/test_token_onboarding.py` to:
  - Simulate a local connection (headers is `None`) and verify it authenticates automatically.
  - Simulate a cloud connection (headers is not `None`) without a token and verify it is rejected with a `PermissionError`.
  - Call the new `register_user()` tool to generate a UUID token and verify database registration.
  - Simulate a cloud connection containing the newly registered UUID token and verify it succeeds and isolates the data.
  - Clean up database records.
