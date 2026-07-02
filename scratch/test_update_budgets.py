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
    # 1. Initialize DB pool
    print("Initializing database pool...")
    pool = await main.get_pool()
    
    async with pool.acquire() as conn:
        # Resolve user
        user_id = await main.get_authenticated_user_id(conn)
        print(f"Authenticated as test user ID: {user_id}")
        
        # 2. Cleanup any pre-existing test budgets
        print("Cleaning up old test budgets...")
        await conn.execute("DELETE FROM budgets WHERE user_id = $1", user_id)
        
        # 3. Create initial test budgets
        print("Creating test budgets...")
        # Create an overall budget
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
        
        # Create a category budget
        res_cat = await budget.create_budget_impl(
            conn, user_id,
            budget_type="category",
            amount=500.0,
            period="weekly",
            start_date="2026-07-01",
            end_date="2026-07-07",
            category="food"
        )
        assert res_cat["status"] == "ok"
        cat_id = res_cat["created_ids"][0]
        
        # Create a subcategory budget
        res_sub = await budget.create_budget_impl(
            conn, user_id,
            budget_type="subcategory",
            amount=100.0,
            period="monthly",
            start_date="2026-07-01",
            end_date="2026-07-31",
            category="food",
            subcategory="groceries"
        )
        assert res_sub["status"] == "ok"
        sub_id = res_sub["created_ids"][0]
        
        print(f"Created budgets: Overall={overall_id}, Category={cat_id}, Subcategory={sub_id}")
        
        # --- TEST 1: Update overall budget amount and period ---
        print("\n--- Test 1: Update single budget fields ---")
        res = await budget.update_budgets_impl(
            conn, user_id,
            budget_ids=[overall_id],
            amount=1200.0,
            period="yearly"
        )
        print("Update response:", res)
        assert res["status"] == "ok"
        assert res["updated_count"] == 1
        
        # Verify changes in DB
        row = await conn.fetchrow("SELECT amount, period FROM budgets WHERE id = $1", overall_id)
        assert row["amount"] == 1200.0
        assert row["period"] == "yearly"
        print("Verify Test 1 Passed!")
        
        # --- TEST 2: Bulk update budgets of a specific period ---
        print("\n--- Test 2: Bulk update by filter ---")
        res = await budget.update_budgets_impl(
            conn, user_id,
            filter_period="monthly",
            amount=150.0
        )
        print("Update response:", res)
        assert res["status"] == "ok"
        # overall_id was changed to yearly, so only sub_id should be changed
        assert res["updated_count"] == 1
        assert res["updated_ids"] == [sub_id]
        
        row = await conn.fetchrow("SELECT amount FROM budgets WHERE id = $1", sub_id)
        assert row["amount"] == 150.0
        print("Verify Test 2 Passed!")
        
        # --- TEST 3: Validation checks - Safety filter limit ---
        print("\n--- Test 3: Safety filter limit check ---")
        res = await budget.update_budgets_impl(
            conn, user_id,
            amount=2000.0
        )
        print("Update response:", res)
        assert res["status"] == "error"
        assert "filter" in res["message"]
        print("Verify Test 3 Passed!")
        
        # --- TEST 4: Validation checks - Empty updates ---
        print("\n--- Test 4: Empty updates check ---")
        res = await budget.update_budgets_impl(
            conn, user_id,
            budget_ids=[overall_id]
        )
        print("Update response:", res)
        assert res["status"] == "error"
        assert "field" in res["message"]
        print("Verify Test 4 Passed!")
        
        # --- TEST 5: Category & Subcategory normalizations ---
        print("\n--- Test 5: Category casing normalization check ---")
        res = await budget.update_budgets_impl(
            conn, user_id,
            budget_ids=[cat_id],
            category="FOOD"
        )
        print("Update response:", res)
        assert res["status"] == "ok"
        
        row = await conn.fetchrow("SELECT category FROM budgets WHERE id = $1", cat_id)
        # Verify it normalized to "food" (lowercase key from categories.json)
        assert row["category"] == "food"
        print("Verify Test 5 Passed!")

        # --- TEST 6: Invalid category update ---
        print("\n--- Test 6: Invalid category check ---")
        res = await budget.update_budgets_impl(
            conn, user_id,
            budget_ids=[cat_id],
            category="invalid_category"
        )
        print("Update response:", res)
        assert res["status"] == "error"
        assert "invalid" in res["message"].lower()
        print("Verify Test 6 Passed!")
        
        # --- TEST 7: Chronology checks ---
        print("\n--- Test 7: Date chronology check ---")
        res = await budget.update_budgets_impl(
            conn, user_id,
            budget_ids=[overall_id],
            start_date="2026-08-01",
            end_date="2026-07-01"
        )
        print("Update response:", res)
        assert res["status"] == "error"
        assert "cannot be after" in res["message"]
        print("Verify Test 7 Passed!")
        
        # --- TEST 8: Database constraints validation (Scope mismatch) ---
        print("\n--- Test 8: DB check constraint validation check ---")
        # Try to set category on an overall budget
        res = await budget.update_budgets_impl(
            conn, user_id,
            budget_ids=[overall_id],
            category="Food"
        )
        print("Update response:", res)
        assert res["status"] == "error"
        assert "Update failed" in res["message"]
        print("Verify Test 8 Passed!")
        
        # --- TEST 9: Isolation boundary verification ---
        print("\n--- Test 9: Isolation boundary check ---")
        # Call as a different user (e.g. user_id + 999)
        res = await budget.update_budgets_impl(
            conn, user_id + 999,
            budget_ids=[overall_id],
            amount=5000.0
        )
        print("Update response:", res)
        assert res["status"] == "ok"
        assert res["updated_count"] == 0  # Should not update anything since it's owned by user_id
        
        # Confirm value wasn't changed
        row = await conn.fetchrow("SELECT amount FROM budgets WHERE id = $1", overall_id)
        assert row["amount"] == 1200.0
        print("Verify Test 9 Passed!")

        # Clean up database
        print("\nCleaning up test budgets...")
        await conn.execute("DELETE FROM budgets WHERE id = ANY($1::integer[])", [overall_id, cat_id, sub_id])
        print("Cleanup done!")
        
    print("\nAll tests completed successfully!")

if __name__ == "__main__":
    asyncio.run(run_tests())
