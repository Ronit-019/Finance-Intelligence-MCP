import os
from datetime import date as pydate, timedelta
import statistics

# Define category lists
ESSENTIALS = {'food', 'transport', 'housing', 'utilities', 'health', 'family_kids', 'home', 'taxes', 'finance_fees'}
DISCRETIONARY = {'entertainment', 'shopping', 'travel', 'subscriptions', 'personal_care', 'gifts_donations', 'misc', 'business', 'investments'}

async def financial_health_score_impl(conn, user_id: int, reference_month: str = None) -> dict:
    # 1. Resolve date targets
    if reference_month:
        try:
            parts = reference_month.split("-")
            year = int(parts[0])
            month = int(parts[1])
            start_date = pydate(year, month, 1)
        except Exception as e:
            return {
                "status": "error",
                "message": f"Invalid reference_month format (expected YYYY-MM): {str(e)}"
            }
    else:
        today = pydate.today()
        year = today.year
        month = today.month
        start_date = pydate(year, month, 1)

    # End of target month
    if month == 12:
        end_date = pydate(year, 12, 31)
    else:
        end_date = pydate(year, month + 1, 1) - timedelta(days=1)

    # Previous Month M-1
    if month == 1:
        prev_start = pydate(year - 1, 12, 1)
        prev_end = pydate(year - 1, 12, 31)
    else:
        prev_start = pydate(year, month - 1, 1)
        prev_end = pydate(year, month, 1) - timedelta(days=1)

    # Month M-2
    if month == 1:
        prev2_start = pydate(year - 1, 11, 1)
        prev2_end = pydate(year - 1, 11, 30)
    elif month == 2:
        prev2_start = pydate(year - 1, 12, 1)
        prev2_end = pydate(year - 1, 12, 31)
    else:
        prev2_start = pydate(year, month - 2, 1)
        prev2_end = pydate(year, month - 1, 1) - timedelta(days=1)

    # 2. Database Queries
    
    # 2.1 Get active budgets
    budgets_rows = await conn.fetch(
        """
        SELECT id, budget_type, category, subcategory, amount, period, start_date, end_date
        FROM budgets
        WHERE user_id = $1 AND start_date <= $2 AND end_date >= $3
        """,
        user_id, end_date, start_date
    )

    # 2.2 Category spent breakdown for target month
    cat_rows = await conn.fetch(
        """
        SELECT category, COALESCE(SUM(amount), 0.0) as total_amount
        FROM expenses
        WHERE user_id = $1 AND date BETWEEN $2 AND $3
        GROUP BY category
        """,
        user_id, start_date, end_date
    )

    # 2.3 Max single transaction in target month
    max_expense = await conn.fetchval(
        """
        SELECT COALESCE(MAX(amount), 0.0)
        FROM expenses
        WHERE user_id = $1 AND date BETWEEN $2 AND $3
        """,
        user_id, start_date, end_date
    )

    # 2.4 Total spending for M, M-1, M-2
    monthly_spends = {}
    for label, s, e in [("M", start_date, end_date), ("M-1", prev_start, prev_end), ("M-2", prev2_start, prev2_end)]:
        val = await conn.fetchval(
            "SELECT COALESCE(SUM(amount), 0.0) FROM expenses WHERE user_id = $1 AND date BETWEEN $2 AND $3",
            user_id, s, e
        )
        monthly_spends[label] = val

    # 3. KPI Scoring

    breakdown = {}
    reasons = {}

    # 3.1 Budget Adherence
    exceeded_count = 0
    total_overshoot = 0.0
    total_active_budgets = len(budgets_rows)
    overall_budget_total = 0.0

    for b in budgets_rows:
        b_type = b["budget_type"]
        b_cat = b["category"]
        b_sub = b["subcategory"]
        b_amount = b["amount"]
        overall_budget_total += b_amount

        # Find matching expenses sum
        exp_query = "SELECT COALESCE(SUM(amount), 0.0) FROM expenses WHERE user_id = $1 AND date BETWEEN $2 AND $3"
        exp_params = [user_id, b["start_date"], b["end_date"]]
        exp_param_idx = 4
        if b_type == "category":
            exp_query += f" AND category = ${exp_param_idx}"
            exp_params.append(b_cat)
        elif b_type == "subcategory":
            exp_query += f" AND category = ${exp_param_idx} AND subcategory = ${exp_param_idx+1}"
            exp_params.extend([b_cat, b_sub])

        spent = await conn.fetchval(exp_query, *exp_params)
        if spent > b_amount:
            exceeded_count += 1
            overshoot_pct = (spent - b_amount) / b_amount if b_amount > 0 else 1.0
            total_overshoot += overshoot_pct

    if total_active_budgets == 0:
        breakdown["budget_adherence"] = 7
        reasons["budget_adherence"] = "No active budgets are currently configured. Create a budget to track spending limits."
    else:
        score = 10.0
        deduct_freq = (exceeded_count / total_active_budgets) * 5.0
        score -= deduct_freq
        
        if exceeded_count > 0:
            avg_overshoot = total_overshoot / exceeded_count
            if avg_overshoot > 0.50:
                score -= 5.0
            elif avg_overshoot > 0.20:
                score -= 3.0
            else:
                score -= 1.0
        score = max(0, round(score))
        breakdown["budget_adherence"] = score
        if exceeded_count == 0:
            reasons["budget_adherence"] = "Excellent! You stayed within all defined budget limits."
        else:
            reasons["budget_adherence"] = f"Exceeded {exceeded_count}/{total_active_budgets} active budgets. Average overspend percentage was {round((total_overshoot / exceeded_count) * 100, 1)}%."

    # 3.2 Expense Stability
    totals = [monthly_spends["M-2"], monthly_spends["M-1"], monthly_spends["M"]]
    mean_spend = statistics.mean(totals)
    std_spend = statistics.stdev(totals) if len(totals) > 1 else 0.0
    cv = (std_spend / mean_spend) if mean_spend > 0 else 0.0

    # Neutral default if no spends are logged across history
    if mean_spend == 0:
        breakdown["expense_stability"] = 7
        reasons["expense_stability"] = "Insufficient spending records to determine stability history."
    else:
        if cv <= 0.15:
            score = 10
            msg = "Highly stable: Month-to-month spending remains highly consistent."
        elif cv <= 0.30:
            score = 8
            msg = "Stable: Spending exhibits standard minor fluctuations."
        elif cv <= 0.50:
            score = 5
            msg = "Moderate: Spending shows noticeable volatility between periods."
        else:
            score = 2
            msg = "Erratic: Spending fluctuates dramatically between months. Plan expenses in advance."
        breakdown["expense_stability"] = score
        reasons["expense_stability"] = f"{msg} (Coefficient of Variation: {round(cv, 3)})"

    # 3.3 Savings Capacity
    target_spent = monthly_spends["M"]
    if overall_budget_total == 0:
        breakdown["savings_capacity"] = 7
        reasons["savings_capacity"] = "Configure budget limits to calculate savings ratio metrics."
    else:
        savings_ratio = (overall_budget_total - target_spent) / overall_budget_total
        if savings_ratio >= 0.20:
            score = 10
            msg = f"Superb! You saved {round(savings_ratio * 100, 1)}% of your budgeted limit."
        elif savings_ratio >= 0.10:
            score = 8
            msg = f"Good. You saved {round(savings_ratio * 100, 1)}% of your budgeted limit."
        elif savings_ratio >= 0.00:
            score = 5
            msg = f"Marginal. You saved {round(savings_ratio * 100, 1)}% of your budgeted limit."
        else:
            score = 0
            msg = f"Warning: Spend exceeded budget totals by {round(abs(savings_ratio) * 100, 1)}%."
        breakdown["savings_capacity"] = score
        reasons["savings_capacity"] = msg

    # 3.4 Category Balance
    essential_spend = 0.0
    discretionary_spend = 0.0
    for r in cat_rows:
        cat_key = r["category"].lower()
        amt = r["total_amount"]
        if cat_key in DISCRETIONARY:
            discretionary_spend += amt
        else:
            essential_spend += amt
            
    total_cat_spend = essential_spend + discretionary_spend
    if total_cat_spend == 0:
        breakdown["category_balance"] = 10
        reasons["category_balance"] = "No transaction records exist for this month."
    else:
        discretionary_ratio = discretionary_spend / total_cat_spend
        if discretionary_ratio <= 0.30:
            score = 10
            msg = "Ideal allocation: Discretionary wants make up 30% or less of total spending."
        elif discretionary_ratio <= 0.50:
            score = 7
            msg = "Satisfactory: Discretionary categories compose between 30% and 50% of your expenses."
        elif discretionary_ratio <= 0.70:
            score = 4
            msg = "Elevated wants: Discretionary categories consume 50% to 70% of expenses. Review subscriptions/shopping."
        else:
            score = 0
            msg = "Critical: Over 70% of monthly spending was dedicated to discretionary desires."
        breakdown["category_balance"] = score
        reasons["category_balance"] = f"{msg} (Discretionary ratio: {round(discretionary_ratio * 100, 1)}%)"

    # 3.5 Large Expense Ratio
    if target_spent == 0:
        breakdown["large_expense_ratio"] = 10
        reasons["large_expense_ratio"] = "No transactions exist to evaluate."
    else:
        le_ratio = max_expense / target_spent
        if le_ratio <= 0.15:
            score = 10
            msg = "Evenly distributed: No single transaction dominates your monthly expenses."
        elif le_ratio <= 0.30:
            score = 8
            msg = "Healthy: Single largest transaction constitutes a moderate portion of spending."
        elif le_ratio <= 0.50:
            score = 5
            msg = "High concentration: Single transaction accounted for over 30% of total spending."
        else:
            score = 2
            msg = "Extreme concentration: Single transaction consumed more than 50% of the entire monthly spent."
        breakdown["large_expense_ratio"] = score
        reasons["large_expense_ratio"] = f"{msg} (Largest expense ratio: {round(le_ratio * 100, 1)}%)"

    # 3.6 Spending Trend
    curr_m = monthly_spends["M"]
    prev_m = monthly_spends["M-1"]
    
    if prev_m == 0:
        breakdown["spending_trend"] = 7
        reasons["spending_trend"] = "No previous month records exist to check trend direction."
    else:
        if curr_m < prev_m:
            score = 10
            msg = f"Positive progress! Spending decreased by {round(((prev_m - curr_m) / prev_m) * 100, 1)}% MoM."
        elif abs(curr_m - prev_m) / prev_m <= 0.05:
            score = 7
            msg = "Stable trend: Spending remained virtually unchanged from the previous month."
        else:
            pct_inc = ((curr_m - prev_m) / prev_m) * 100
            if pct_inc <= 15.0:
                score = 5
                msg = f"Minor increase: Spending rose by {round(pct_inc, 1)}% compared to last month."
            else:
                score = 2
                msg = f"Major increase: Spending grew significantly by {round(pct_inc, 1)}% MoM."
        breakdown["spending_trend"] = score
        reasons["spending_trend"] = msg

    # 4. Overall score
    total_raw = sum(breakdown.values())
    health_score = int((total_raw / 60) * 100)
    
    if health_score >= 85:
        grade = "Excellent"
    elif health_score >= 70:
        grade = "Good"
    elif health_score >= 50:
        grade = "Fair"
    else:
        grade = "Poor"

    return {
        "status": "ok",
        "reference_month": f"{year}-{month:02d}",
        "financial_health_score": health_score,
        "grade": grade,
        "breakdown": breakdown,
        "reasons": reasons
    }
