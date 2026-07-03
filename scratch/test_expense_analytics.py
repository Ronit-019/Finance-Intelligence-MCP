import asyncio
import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main
import analytics

load_dotenv()

async def run_tests():
    print("Initializing database pool...")
    pool = await main.get_pool()
    
    async with pool.acquire() as conn:
        user_id = await main.get_authenticated_user_id(conn)
        print(f"Authenticated as test user ID: {user_id}")
        
        # 1. Clean up old test data
        print("Cleaning up old test data...")
        await conn.execute("DELETE FROM expenses WHERE user_id = $1", user_id)
        
        # 2. Insert test expenses across different dates and categories
        print("Creating test expenses...")
        # March 2026: total = 180.0
        await main.add_expense("2026-03-15", 120.0, "food", "groceries", "Groceries")
        await main.add_expense("2026-03-20", 60.0, "food", "dining_out", "Dinner out")
        
        # May 2026: total = 230.0
        await main.add_expense("2026-05-10", 80.0, "transport", "fuel", "Gas filling")
        await main.add_expense("2026-05-25", 150.0, "utilities", "electricity", "Power bill")
        
        # July 2026: total = 140.0
        await main.add_expense("2026-07-02", 50.0, "food", "groceries", "More groceries")
        await main.add_expense("2026-07-03", 90.0, "utilities", "internet_broadband", "Wifi bill")
        
        # --- TEST 1: Monthly analysis ---
        print("\n--- Test 1: Time-series monthly aggregation ---")
        res = await analytics.expense_summary_impl(
            conn, user_id,
            period="monthly"
        )
        print("Response status:", res["status"])
        print("Chart URL:", res["chart_url"])
        assert res["status"] == "ok"
        assert os.path.exists(res["chart_path"])
        
        # Assert database rows match expected month values
        data_map = {str(r["period_bucket"]): float(r["total_amount"]) for r in res["data"]}
        print("Data mapped:", data_map)
        assert data_map["2026-03-01"] == 180.0
        assert data_map["2026-05-01"] == 230.0
        assert data_map["2026-07-01"] == 140.0
        print("Verify Test 1 Passed!")
        
        # --- TEST 2: Category grouping ---
        print("\n--- Test 2: Category grouping aggregation ---")
        res = await analytics.expense_summary_impl(
            conn, user_id,
            group_by="category"
        )
        print("Response status:", res["status"])
        assert res["status"] == "ok"
        assert os.path.exists(res["chart_path"])
        
        # Assert database categories match expected values
        cat_map = {str(r["group_bucket"]): float(r["total_amount"]) for r in res["data"]}
        print("Category map:", cat_map)
        # Note: keys are Title Cased or lowercase from categories.json (casing normalized to title case by validate helper or exact keys)
        # In this project, validate_category_and_subcategory resolves "food" -> "Food", "utilities" -> "Utilities" (depending on case matching)
        # Let's check keys (they will match whatever validate helper returns)
        # Since categories are Title Case or exact keys, we can do case-insensitive comparisons or check keys:
        assert cat_map.get("Food", cat_map.get("food")) == 230.0
        assert cat_map.get("Transport", cat_map.get("transport")) == 80.0
        assert cat_map.get("Utilities", cat_map.get("utilities")) == 240.0
        print("Verify Test 2 Passed!")
        
        # --- TEST 3: Combo monthly and category grouping ---
        print("\n--- Test 3: Combo monthly & category stacked bar chart ---")
        res = await analytics.expense_summary_impl(
            conn, user_id,
            period="monthly",
            group_by="category"
        )
        print("Response status:", res["status"])
        assert res["status"] == "ok"
        assert os.path.exists(res["chart_path"])
        print("Verify Test 3 Passed!")
        
        # --- TEST 4: Validation checks ---
        print("\n--- Test 4: Validation error checks ---")
        # No grouping specified
        res = await analytics.expense_summary_impl(conn, user_id)
        assert res["status"] == "error"
        assert "dimension" in res["message"]
        
        # Invalid period
        res = await analytics.expense_summary_impl(conn, user_id, period="invalid_period")
        assert res["status"] == "error"
        assert "Invalid period" in res["message"]
        
        # Invalid group_by
        res = await analytics.expense_summary_impl(conn, user_id, group_by="invalid_column")
        assert res["status"] == "error"
        assert "Invalid group_by" in res["message"]
        print("Verify Test 4 Passed!")

        # Clean up database records
        print("\nCleaning up test expenses...")
        await conn.execute("DELETE FROM expenses WHERE user_id = $1", user_id)
        print("Cleanup done!")
        
    print("\nAll tests completed successfully!")

if __name__ == "__main__":
    asyncio.run(run_tests())
