import asyncio
import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main
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
        
        # 2. Create test budgets
        print("Creating test budgets...")
        # Overall monthly budget
        res_overall = await budget.create_budget_impl(
            conn, user_id,
            budget_type="overall",
            amount=1000.0,
            period="monthly",
            start_date="2026-07-01",
            end_date="2026-07-31"
        )
        overall_id = res_overall["created_ids"][0]
        
        # Category weekly budget
        res_cat = await budget.create_budget_impl(
            conn, user_id,
            budget_type="category",
            amount=100.0,
            period="weekly",
            start_date="2026-07-01",
            end_date="2026-07-07",
            category="food"
        )
        cat_id = res_cat["created_ids"][0]
        
        # Subcategory monthly budget
        res_sub = await budget.create_budget_impl(
            conn, user_id,
            budget_type="subcategory",
            amount=50.0,
            period="monthly",
            start_date="2026-07-01",
            end_date="2026-07-31",
            category="food",
            subcategory="groceries"
        )
        sub_id = res_sub["created_ids"][0]
        
        # 3. Insert expenses
        print("Creating test expenses...")
        # July 2: food - dining_out, 60.0 (inside overall, inside category food, NOT subcategory groceries)
        await main.add_expense("2026-07-02", 60.0, "food", "dining_out", "Dinner")
        # July 3: food - groceries, 40.0 (inside overall, inside category food, inside subcategory groceries)
        await main.add_expense("2026-07-03", 40.0, "food", "groceries", "Supermarket")
        # July 4: utilities - electricity, 30.0 (inside overall, NOT food category)
        await main.add_expense("2026-07-04", 30.0, "utilities", "electricity", "Power bill")
        # July 10: food - dining_out, 50.0 (inside overall, OUTSIDE weekly category budget window, NOT subcategory groceries)
        await main.add_expense("2026-07-10", 50.0, "food", "dining_out", "Lunch")
        
        # --- TEST 1: Check status on Reference Date 2026-07-02 ---
        print("\n--- Test 1: Retrieve status comparing budgets and expenses ---")
        res = await budget.compare_budget_vs_expenses_impl(conn, user_id, reference_date="2026-07-02")
        print("Status response:", res)
        assert res["status"] == "ok"
        
        budgets_res = {b["budget_id"]: b for b in res["budgets"]}
        
        # Check Overall Budget status
        # Limit = 1000.0, Spent = 60 (dining_out) + 40 (groceries) + 30 (electricity) + 50 (dining_out) = 180.0
        b_overall = budgets_res[overall_id]
        print("b_overall:", b_overall)
        assert b_overall["limit_amount"] == 1000.0
        assert b_overall["total_spent"] == 180.0
        assert b_overall["remaining"] == 820.0
        assert b_overall["percentage_spent"] == 18.0
        assert b_overall["status"] == "under_budget"
        
        # Check Category Budget status (Food)
        # Limit = 100.0, Spent in range [July 1, July 7] = 60.0 (July 2) + 40.0 (July 3) = 100.0 (July 10 is outside)
        b_cat = budgets_res[cat_id]
        print("b_cat:", b_cat)
        assert b_cat["limit_amount"] == 100.0
        assert b_cat["total_spent"] == 100.0
        assert b_cat["remaining"] == 0.0
        assert b_cat["percentage_spent"] == 100.0
        assert b_cat["status"] == "under_budget"
        
        # Check Subcategory Budget status (Food - Groceries)
        # Limit = 50.0, Spent in range [July 1, July 31] = 40.0 (groceries on July 3)
        b_sub = budgets_res[sub_id]
        print("b_sub:", b_sub)
        assert b_sub["limit_amount"] == 50.0
        assert b_sub["total_spent"] == 40.0
        assert b_sub["remaining"] == 10.0
        assert b_sub["percentage_spent"] == 80.0
        assert b_sub["status"] == "under_budget"
        
        print("Verify Test 1 Passed!")
        
        # --- TEST 2: Add expense to go OVER category limit ---
        print("\n--- Test 2: Add expense and check over budget status ---")
        await main.add_expense("2026-07-05", 15.0, "food", "snacks", "Snacks")
        
        res = await budget.compare_budget_vs_expenses_impl(conn, user_id, reference_date="2026-07-02")
        budgets_res = {b["budget_id"]: b for b in res["budgets"]}
        
        # Food category budget is now 60 + 40 + 15 = 115.0 (limit 100.0) -> over_budget
        b_cat = budgets_res[cat_id]
        print("b_cat after new expense:", b_cat)
        assert b_cat["total_spent"] == 115.0
        assert b_cat["remaining"] == -15.0
        assert b_cat["percentage_spent"] == 115.0
        assert b_cat["status"] == "over_budget"
        print("Verify Test 2 Passed!")
        
        # --- TEST 3: Filters option testing ---
        print("\n--- Test 3: Filter parameters check ---")
        # Filter by budget type overall
        res_filtered = await budget.compare_budget_vs_expenses_impl(conn, user_id, reference_date="2026-07-02", budget_type="overall")
        assert len(res_filtered["budgets"]) == 1
        assert res_filtered["budgets"][0]["budget_id"] == overall_id
        
        # Filter by category utilities (no active utility budgets)
        res_empty = await budget.compare_budget_vs_expenses_impl(conn, user_id, reference_date="2026-07-02", category="utilities")
        assert len(res_empty["budgets"]) == 0
        print("Verify Test 3 Passed!")
        
        # --- TEST 4: Date bounds testing ---
        print("\n--- Test 4: Date boundary check ---")
        # Check on August 1st -> No active budgets should match
        res_aug = await budget.compare_budget_vs_expenses_impl(conn, user_id, reference_date="2026-08-01")
        assert len(res_aug["budgets"]) == 0
        print("Verify Test 4 Passed!")

        # Clean up database records
        print("\nCleaning up test budgets and expenses...")
        await conn.execute("DELETE FROM budgets WHERE user_id = $1", user_id)
        await conn.execute("DELETE FROM expenses WHERE user_id = $1", user_id)
        print("Cleanup done!")
        
    print("\nAll tests completed successfully!")

if __name__ == "__main__":
    asyncio.run(run_tests())
