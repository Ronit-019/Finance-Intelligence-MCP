import asyncio
import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main

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
        
        # 2. Insert test expenses
        print("Creating test expenses...")
        await main.add_expense("2026-03-15", 120.0, "food", "groceries", "Market shopping")
        await main.add_expense("2026-03-20", 60.0, "food", "dining_out", "Dinner out")
        await main.add_expense("2026-05-10", 80.0, "transport", "fuel", "Gas fill")
        await main.add_expense("2026-05-25", 150.0, "utilities", "electricity", "Power bill")
        
        # --- TEST 1: Group by category ---
        print("\n--- Test 1: Group by category ---")
        res = await main.expense_breakdown(
            start_date="2026-01-01",
            end_date="2026-12-31",
            group_by="category"
        )
        print("Breakdown response:", res)
        # Verify category sums (categories.json Title Casing logic resolves "food" -> "Food", "utilities" -> "Utilities")
        data_map = {r["group_dimension"]: float(r["total_amount"]) for r in res}
        assert data_map.get("Food", data_map.get("food")) == 180.0
        assert data_map.get("Transport", data_map.get("transport")) == 80.0
        assert data_map.get("Utilities", data_map.get("utilities")) == 150.0
        print("Verify Test 1 Passed!")
        
        # --- TEST 2: Group by subcategory ---
        print("\n--- Test 2: Group by subcategory ---")
        res = await main.expense_breakdown(
            start_date="2026-01-01",
            end_date="2026-12-31",
            group_by="subcategory"
        )
        print("Breakdown response:", res)
        data_map = {r["group_dimension"]: float(r["total_amount"]) for r in res}
        assert data_map["groceries"] == 120.0
        assert data_map["dining_out"] == 60.0
        assert data_map["fuel"] == 80.0
        assert data_map["electricity"] == 150.0
        print("Verify Test 2 Passed!")
        
        # --- TEST 3: Group by date (month breakdown) ---
        print("\n--- Test 3: Group by date with monthly breakdown ---")
        res = await main.expense_breakdown(
            start_date="2026-01-01",
            end_date="2026-12-31",
            group_by="date",
            breakdown="month"
        )
        print("Breakdown response:", res)
        data_map = {r["group_dimension"]: float(r["total_amount"]) for r in res}
        assert data_map["2026-03-01"] == 180.0
        assert data_map["2026-05-01"] == 230.0
        print("Verify Test 3 Passed!")
        
        # --- TEST 4: Group by date (day breakdown) ---
        print("\n--- Test 4: Group by date with day breakdown ---")
        res = await main.expense_breakdown(
            start_date="2026-03-01",
            end_date="2026-03-31",
            group_by="date",
            breakdown="day"
        )
        print("Breakdown response:", res)
        data_map = {r["group_dimension"]: float(r["total_amount"]) for r in res}
        assert data_map["2026-03-15"] == 120.0
        assert data_map["2026-03-20"] == 60.0
        print("Verify Test 4 Passed!")

        # --- TEST 5: Filter by category and group by date ---
        print("\n--- Test 5: Filter by category and group by date ---")
        res = await main.expense_breakdown(
            start_date="2026-01-01",
            end_date="2026-12-31",
            group_by="date",
            breakdown="month",
            category="food"
        )
        print("Breakdown response:", res)
        data_map = {r["group_dimension"]: float(r["total_amount"]) for r in res}
        assert data_map["2026-03-01"] == 180.0
        assert "2026-05-01" not in data_map  # Utilities/Transport are filtered out
        print("Verify Test 5 Passed!")

        # Clean up database records
        print("\nCleaning up test expenses...")
        await conn.execute("DELETE FROM expenses WHERE user_id = $1", user_id)
        print("Cleanup done!")
        
    print("\nAll tests completed successfully!")

if __name__ == "__main__":
    asyncio.run(run_tests())
