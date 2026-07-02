# Budget Table Schema

The `budgets` table stores spending limits defined by users. It supports **overall budgets**, **category-specific budgets**, and is designed to support **subcategory budgets** in future releases.

## Table Fields

| Field         | Type               | Nullable | Description                                                                                                                        |
| ------------- | ------------------ | -------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `id`          | `SERIAL`           | ❌        | Primary key for the budget record.                                                                                                 |
| `user_id`     | `INTEGER`          | ❌        | References the `users.id` column. Identifies the owner of the budget.                                                              |
| `budget_type` | `VARCHAR(20)`      | ❌        | Defines the scope of the budget. Allowed values: `overall`, `category`, `subcategory`.                                             |
| `category`    | `VARCHAR(100)`     | ✅        | Category key from `categories.json` (e.g., `food`, `transport`). Required only for `category` and `subcategory` budgets.           |
| `subcategory` | `VARCHAR(100)`     | ✅        | Subcategory key from `categories.json` (e.g., `coffee_tea`). Reserved for future support. Required only for `subcategory` budgets. |
| `amount`      | `DOUBLE PRECISION` | ❌        | Budget amount.                                                                                                                     |
| `period`      | `VARCHAR(20)`      | ❌        | Budget duration. Supported values: `weekly`, `monthly`, `quarterly`, `yearly`.                                                     |
| `start_date`  | `DATE`             | ❌        | Date from which the budget becomes effective.                                                                                      |
| `end_date`    | `DATE`             | ❌        | Date on which the budget expires.                                                                                                  |
| `created_at`  | `TIMESTAMP`        | ❌        | Timestamp when the budget was created.                                                                                             |
| `updated_at`  | `TIMESTAMP`        | ❌        | Timestamp of the most recent update.                                                                                               |