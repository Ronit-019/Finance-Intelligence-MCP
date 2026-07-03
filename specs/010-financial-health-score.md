# Spec-010: Financial Health Score Tool

## 1. Overview
Evaluating financial health is a critical aspect of personal finance management. While users can track expenses and set budgets, they lack a high-level automated dashboard that assesses their habits and assigns an overall deterministic financial health score with feedback.

This feature adds a separate module (`health.py`) exposing a new MCP tool named `financial_health_score`. This tool evaluates 6 key financial performance indicators (KPIs) based on database records and computes a score out of 100, providing detailed feedback for each area.

---

## 2. Requirements & User Stories

- **User Story 1**: As a user, I want to query my financial health score for the current period (or a reference month) and receive a grade (e.g. Excellent, Good, Fair, Poor) and total score out of 100.
- **User Story 2**: As a user, I want to see a detailed score breakdown and a written explanation for each of the 6 financial health dimensions:
  1. **Budget Adherence**: Check if budgets were exceeded, by how much, and how often.
  2. **Expense Stability**: Measure consistency of month-to-month spending totals.
  3. **Savings Capacity**: Measure actual spend against budget allocations.
  4. **Category Balance**: Analyze discretionary vs. essential spending distribution.
  5. **Large Expense Ratio**: Check if a single transaction dominates monthly spending.
  6. **Spending Trend**: Compare month-over-month spending progress.
- **Security Constraint**: Users must only be allowed to analyze their own financial data.

---

## 3. Technical Design

### MCP Tool Interface
We will register a new tool using `@mcp.tool` in `main.py` and delegate the logic to `health.py`.

```python
@mcp.tool
async def financial_health_score(reference_month: str = None) -> dict:
    """
    Calculate a deterministic financial health score and feedback metrics.
    
    :param reference_month: Optional target month to evaluate in YYYY-MM format. Defaults to current month.
    :return: A status dictionary containing the overall health score, grade, breakdown of the 6 KPIs, and detailed reasons.
    """
```

### Health Assessment Engine (`health.py`)
A new file [health.py](file:///c:/Users/Admin/Desktop/Finance%20Intelligence%20MCP/health.py) will be created:

```python
async def financial_health_score_impl(conn, user_id: int, reference_month: str = None) -> dict:
```

### KPI Calculations & Rules (Each out of 10 points)

#### 1. Budget Adherence (0-10 Points)
- **Calculation**: Query all budgets active in the target month (or past 3 months for greater history). For each budget, compare budget limit to total matching expenses in its date range.
- **Scoring**:
  - `0` budgets exceeded: **10 pts**.
  - `1` or more budgets exceeded:
    - Deduct `(exceeded_budgets_count / total_active_budgets) * 5` (up to 5 pts).
    - Deduct based on excess magnitude: if average overshoot percentage is `> 50%`, deduct `5 pts`; if `> 20%`, deduct `3 pts`; else deduct `1 pt`.
    - Minimum score: `0 pts`.
  - If no budgets are set for the period, default to a neutral **7 pts** with feedback advising budget creation.

#### 2. Expense Stability (0-10 Points)
- **Calculation**: Retrieve total expenses for each of the last 3 months. Compute the Coefficient of Variation: `CV = StdDev(monthly_totals) / Mean(monthly_totals)`.
- **Scoring**:
  - `CV <= 0.15`: **10 pts** (high consistency).
  - `0.15 < CV <= 0.30`: **8 pts** (stable).
  - `0.30 < CV <= 0.50`: **5 pts** (moderate variations).
  - `CV > 0.50`: **2 pts** (erratic spending).
  - If less than 2 months of data exist, default to **7 pts** (neutral).

#### 3. Savings Capacity (0-10 Points)
- **Calculation**: Check the savings ratio against budget allocations in the target month:
  `savings_ratio = (total_budget_limit - total_spent) / total_budget_limit`.
- **Scoring**:
  - `savings_ratio >= 0.20` (Saved >= 20% of budget): **10 pts**.
  - `0.10 <= savings_ratio < 0.20`: **8 pts**.
  - `0.00 <= savings_ratio < 0.10`: **5 pts**.
  - `savings_ratio < 0.00` (spent more than budget): **0 pts**.
  - If no budget is set, calculate savings relative to average monthly spending or default to **7 pts**.

#### 4. Category Balance (0-10 Points)
- **Calculation**: Classify expenses into **Essential** (`food`, `transport`, `housing`, `utilities`, `health`, `family_kids`, `home`, `taxes`, `finance_fees`) vs. **Discretionary** (`entertainment`, `shopping`, `travel`, `subscriptions`, `personal_care`, `gifts_donations`, `misc`, `business`, `investments`).
- Calculate `discretionary_ratio = discretionary_spend / total_spent`.
- **Scoring** (based on 50/30/20 rule target: wants <= 30%):
  - `discretionary_ratio <= 0.30`: **10 pts**.
  - `0.30 < discretionary_ratio <= 0.50`: **7 pts**.
  - `0.50 < discretionary_ratio <= 0.70`: **4 pts**.
  - `discretionary_ratio > 0.70`: **0 pts**.
  - If no expenses exist, default to **10 pts**.

#### 5. Large Expense Ratio (0-10 Points)
- **Calculation**: For the target month, check the ratio of the single largest expense to total expenses:
  `large_expense_ratio = max(single_expense_amount) / total_spent`.
- **Scoring**:
  - `large_expense_ratio <= 0.15` (well distributed): **10 pts**.
  - `0.15 < large_expense_ratio <= 0.30`: **8 pts**.
  - `0.30 < large_expense_ratio <= 0.50`: **5 pts**.
  - `large_expense_ratio > 0.50` (single item consumed over half the budget): **2 pts**.
  - If no expenses exist, default to **10 pts**.

#### 6. Spending Trend (0-10 Points)
- **Calculation**: Compare total spent in the target month vs. previous month.
- **Scoring**:
  - Current Month < Previous Month (spending decreased): **10 pts**.
  - Current Month == Previous Month (+/- 5% tolerance): **7 pts**.
  - Current Month > Previous Month (spending increased):
    - Increase <= 15%: **5 pts**.
    - Increase > 15%: **2 pts**.
  - If no previous month data exists, default to **7 pts**.

---

## 4. Overall Health Grading
The sum of the 6 KPIs yields a raw score out of 60 points.
- Normalized score: `health_score = int((raw_sum / 60) * 100)`
- Grades:
  - `Score >= 85`: **Excellent**
  - `70 <= Score < 85`: **Good**
  - `50 <= Score < 70`: **Fair**
  - `Score < 50`: **Poor**

---

## 5. Verification Plan

### Manual Verification
1. Setup a test database user.
2. **Test 1: Normal spending context**
   - Setup a monthly overall budget of `$1000`.
   - Log expenses: `$100` Food (essential), `$50` movies (discretionary), `$20` fuel (essential). Max expense is `$100`.
   - Call `financial_health_score(reference_month="2026-07")`.
   - Verify category results are parsed and positive health score (>80) is returned.
3. **Test 2: Exceeded budget check**
   - Log another expense of `$900` on shopping (discretionary).
   - This exceeds overall budget ($1070 spent vs. $1000 limit) and skews discretionary ratio.
   - Run health score again. Verify that Budget Adherence, Savings Capacity, and Category Balance scores drop accordingly, lowering the overall grade.
4. **Test 3: Isolation check**
   - Query score for a non-existent or other user's account and verify it returns no results or is completely isolated.
