import os
from datetime import date as pydate
import matplotlib
matplotlib.use('Agg')  # Configure headless non-interactive backend
import matplotlib.pyplot as plt
from budget import validate_category_and_subcategory

async def expense_summary_impl(
    conn,
    user_id: int,
    period: str = None,
    group_by: str = None,
    category: str = None,
    subcategory: str = None,
    start_date: str = None,
    end_date: str = None
) -> dict:
    # 1. Parameter Validations
    if not period and not group_by:
        return {
            "status": "error",
            "message": "At least one grouping dimension ('period' or 'group_by') must be specified."
        }
        
    if period and period not in ["weekly", "monthly", "quarterly", "yearly"]:
        return {
            "status": "error",
            "message": "Invalid period. Allowed values: 'weekly', 'monthly', 'quarterly', 'yearly'."
        }
        
    if group_by and group_by not in ["category", "subcategory"]:
        return {
            "status": "error",
            "message": "Invalid group_by. Allowed values: 'category', 'subcategory'."
        }

    # 2. Date validations
    try:
        parsed_start = pydate.fromisoformat(start_date) if start_date else None
        parsed_end = pydate.fromisoformat(end_date) if end_date else None
        if parsed_start and parsed_end and parsed_start > parsed_end:
            raise ValueError(f"start_date '{start_date}' cannot be after end_date '{end_date}'.")
    except Exception as e:
        return {
            "status": "error",
            "message": f"Date validation failed: {str(e)}"
        }

    # 3. Category / Subcategory normalization
    matched_cat = None
    matched_sub = None
    if category:
        try:
            matched_cat, matched_sub = validate_category_and_subcategory(category, subcategory)
        except ValueError as e:
            return {
                "status": "error",
                "message": f"Validation failed: {str(e)}"
            }

    # 4. Build dynamic SQL
    select_fields = []
    group_fields = []
    
    if period:
        trunc_map = {
            "weekly": "week",
            "monthly": "month",
            "quarterly": "quarter",
            "yearly": "year"
        }
        select_fields.append(f"DATE_TRUNC('{trunc_map[period]}', date)::date AS period_bucket")
        group_fields.append("period_bucket")
        
    if group_by:
        select_fields.append(f"{group_by} AS group_bucket")
        group_fields.append("group_bucket")
        
    query = (
        f"SELECT {', '.join(select_fields)}, SUM(amount) as total_amount, COUNT(id) as transaction_count "
        f"FROM expenses WHERE user_id = $1"
    )
    params = [user_id]
    param_idx = 2
    
    if parsed_start:
        query += f" AND date >= ${param_idx}"
        params.append(parsed_start)
        param_idx += 1
    if parsed_end:
        query += f" AND date <= ${param_idx}"
        params.append(parsed_end)
        param_idx += 1
    if matched_cat:
        query += f" AND category = ${param_idx}"
        params.append(matched_cat)
        param_idx += 1
    if matched_sub:
        query += f" AND subcategory = ${param_idx}"
        params.append(matched_sub)
        param_idx += 1
        
    query += f" GROUP BY {', '.join(group_fields)} ORDER BY {group_fields[0]} ASC"
    if len(group_fields) > 1:
        query += f", {group_fields[1]} ASC"
        
    rows = await conn.fetch(query, *params)
    if not rows:
        return {
            "status": "ok",
            "message": "No expenses found matching the criteria.",
            "data": []
        }

    # 5. Generate Matplotlib Chart
    charts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "charts")
    os.makedirs(charts_dir, exist_ok=True)
    chart_filename = "expense_analysis.png"
    chart_path = os.path.join(charts_dir, chart_filename)
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Render different chart configurations
    if period and not group_by:
        # Time-series trend (Bar chart)
        x_vals = [str(r["period_bucket"]) for r in rows]
        y_vals = [float(r["total_amount"]) for r in rows]
        ax.bar(x_vals, y_vals, color="#3f51b5", width=0.6)
        ax.set_ylabel("Spent Amount ($)")
        ax.set_xlabel("Period")
        ax.set_title(f"Expense Trend over Time ({period.capitalize()})")
        plt.xticks(rotation=45)
        
    elif group_by and not period:
        # Category breakdown (Bar chart)
        x_vals = [str(r["group_bucket"]) for r in rows]
        y_vals = [float(r["total_amount"]) for r in rows]
        ax.bar(x_vals, y_vals, color="#e91e63", width=0.6)
        ax.set_ylabel("Spent Amount ($)")
        ax.set_xlabel(group_by.capitalize())
        ax.set_title(f"Expenses Grouped by {group_by.capitalize()}")
        plt.xticks(rotation=45)
        
    elif period and group_by:
        # Both (Stacked bar chart)
        periods = sorted(list(set(str(r["period_bucket"]) for r in rows)))
        groups = sorted(list(set(str(r["group_bucket"]) for r in rows)))
        
        # Build mapping matrices
        data_matrix = {g: [0.0] * len(periods) for g in groups}
        period_idx_map = {p: i for i, p in enumerate(periods)}
        
        for r in rows:
            p_val = str(r["period_bucket"])
            g_val = str(r["group_bucket"])
            amt = float(r["total_amount"])
            data_matrix[g_val][period_idx_map[p_val]] = amt
            
        bottoms = [0.0] * len(periods)
        for g_val in groups:
            y_vals = data_matrix[g_val]
            ax.bar(periods, y_vals, bottom=bottoms, label=g_val)
            bottoms = [b + y for b, y in zip(bottoms, y_vals)]
            
        ax.set_ylabel("Spent Amount ($)")
        ax.set_xlabel("Period")
        ax.set_title(f"Expenses Trend Grouped by {group_by.capitalize()}")
        ax.legend(title=group_by.capitalize())
        plt.xticks(rotation=45)

    ax.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()
    plt.savefig(chart_path, dpi=150)
    plt.close(fig)
    
    chart_url = f"file:///{chart_path.replace(os.sep, '/')}"
    
    return {
        "status": "ok",
        "chart_path": chart_path,
        "chart_url": chart_url,
        "message": f"Expense analytics trend chart generated successfully:\n\n![Expense Analytics Chart]({chart_url})",
        "data": [dict(r) for r in rows]
    }
