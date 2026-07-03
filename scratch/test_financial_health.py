import asyncio
import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main
import health
import budget

load_dotenv()

async def run_tests():
    print("Initializing database pool...")
    pool = await main.get_pool()
    
    async with pool.acquire() as conn:
        user_id = await main.get_authenticated_user_id(conn)
        print(f"Authenticated as test user ID: {user_id}")
        
        # 1. Clean up old test data
        print("Cleaning up old test data...")
        await conn.execute("DELETE FROM budgets WHERE user_id = $1", user_id)
        await conn.execute("DELETE FROM expenses WHERE user_id = $1", user_id)
        
        # 2. Create test overall budget
        print("Creating test budget...")
        # Overall monthly budget of $1000 for July 2026
        res_overall = await budget.create_budget_impl(
            conn, user_id,
            budget_type="overall",
            amount=1000.0,
            period="monthly",
            start_date="2026-07-01",
            end_date="2026-07-31"
        )
        assert res_overall["status"] == "ok"
        overall_id = res_overall["created_ids"][0]
        
        # 3. Create test expenses
        print("Creating test expenses...")
        # Target month M (July 2026)
        # Total target month spend initially = 100 (Food) + 50 (Entertainment) + 20 (Transport) = 170.0
        # Essential spend = 120.0, Discretionary spend = 50.0 (ratio = 29.4% <= 30%)
        # Max single expense = 100.0 (ratio = 58.8% > 50%)
        await main.add_expense("2026-07-02", 100.0, "food", "dining_out", "Dinner")
        await main.add_expense("2026-07-03", 50.0, "entertainment", "movies_events", "Movies")
        await main.add_expense("2026-07-04", 20.0, "transport", "fuel", "Fuel")
        
        # Previous Month M-1 (June 2026) -> Total spent = 200.0
        await main.add_expense("2026-06-15", 200.0, "utilities", "electricity", "Power bill")
        
        # Month M-2 (May 2026) -> Total spent = 190.0
        await main.add_expense("2026-05-15", 190.0, "utilities", "electricity", "Power bill")
        
        # --- TEST 1: Retrieve status comparing budgets and expenses ---
        print("\n--- Test 1: Calculate health score under good financial conditions ---")
        res = await health.financial_health_score_impl(conn, user_id, reference_month="2026-07")
        print("Health score response:", res)
        assert res["status"] == "ok"
        assert res["grade"] == "Excellent"
        assert res["financial_health_score"] >= 85
        
        # Verify sub-scores:
        # budget_adherence = 10 (no budgets exceeded)
        # savings_capacity = 10 (savings ratio = 83% >= 20%)
        # category_balance = 10 (discretionary ratio = 29.4% <= 30%)
        # spending_trend = 10 (M total spend 170 < M-1 spend 200)
        # large_expense_ratio = 2 (max single expense 100.0 / total 170.0 = 58.8% > 50%)
        # expense_stability = 10 (cv of 190, 200, 170 = 0.082 <= 0.15)
        # Total raw: 10+10+10+10+2+10 = 52. Normalized: 52/60 * 100 = 86
        assert res["breakdown"]["budget_adherence"] == 10
        assert res["breakdown"]["savings_capacity"] == 10
        assert res["breakdown"]["category_balance"] == 10
        assert res["breakdown"]["spending_trend"] == 10
        assert res["breakdown"]["large_expense_ratio"] == 2
        assert res["breakdown"]["expense_stability"] == 10
        assert res["financial_health_score"] == 86
        print("Verify Test 1 Passed!")
        
        # --- TEST 2: Add excessive discretionary expense (over budget) ---
        print("\n--- Test 2: Calculate health score after crossing budget limits ---")
        # Add $900 on Shopping in July 2026 (Discretionary)
        # New target month total spent = 170 + 900 = 1070.0 (> 1000.0 overall budget)
        await main.add_expense("2026-07-05", 900.0, "shopping", "clothing", "Suits")
        
        res = await health.financial_health_score_impl(conn, user_id, reference_month="2026-07")
        print("Health score response after overspend:", res)
        assert res["status"] == "ok"
        assert res["grade"] == "Poor"
        assert res["financial_health_score"] < 50
        
        # Verify breakdown drops:
        # budget_adherence: 4 (1 budget exceeded, deduct 5 for freq, deduct 1 for overshoot 7%)
        # savings_capacity: 0 (savings ratio negative)
        # category_balance: 0 (discretionary spend = 950 / 1070 = 88.8% > 70% wants)
        # large_expense_ratio: 2 (max single spend 900.0 / total 1070.0 = 84% > 50%)
        # spending_trend: 2 MoM spending spike (1070 vs 200)
        # expense_stability: 2 (cv of 190, 200, 1070 = 1.037 > 0.50)
        # Total raw: 4+0+0+2+2+2 = 10. Normalized: 10/60 * 100 = 16
        assert res["breakdown"]["budget_adherence"] == 4
        assert res["breakdown"]["savings_capacity"] == 0
        assert res["breakdown"]["category_balance"] == 0
        assert res["breakdown"]["large_expense_ratio"] == 2
        assert res["breakdown"]["spending_trend"] == 2
        assert res["breakdown"]["expense_stability"] == 2
        assert res["financial_health_score"] == 16
        print("Verify Test 2 Passed!")
        
        # --- TEST 3: Validation checks ---
        print("\n--- Test 3: Parameter validation check ---")
        res_error = await health.financial_health_score_impl(conn, user_id, reference_month="invalid_format")
        assert res_error["status"] == "error"
        print("Verify Test 3 Passed!")

        # Clean up database records
        print("\nCleaning up test budgets and expenses...")
        await conn.execute("DELETE FROM budgets WHERE user_id = $1", user_id)
        await conn.execute("DELETE FROM expenses WHERE user_id = $1", user_id)
        print("Cleanup done!")
        
    print("\nAll tests completed successfully!")

if __name__ == "__main__":
    asyncio.run(run_tests())
