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
        # overall budget
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
        
        # category budget
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
        
        # subcategory budget
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
        
        # --- TEST 1: Delete specific budget by ID ---
        print("\n--- Test 1: Delete specific budget by ID ---")
        res = await budget.delete_budgets_impl(
            conn, user_id,
            budget_ids=[overall_id]
        )
        print("Delete response:", res)
        assert res["status"] == "ok"
        assert res["deleted_count"] == 1
        assert res["deleted_ids"] == [overall_id]
        
        # Verify it is deleted from DB
        row = await conn.fetchrow("SELECT id FROM budgets WHERE id = $1", overall_id)
        assert row is None
        print("Verify Test 1 Passed!")
        
        # --- TEST 2: Bulk delete by type filter ---
        print("\n--- Test 2: Bulk delete by type filter ---")
        res = await budget.delete_budgets_impl(
            conn, user_id,
            budget_type="category"
        )
        print("Delete response:", res)
        assert res["status"] == "ok"
        assert res["deleted_count"] == 1
        assert res["deleted_ids"] == [cat_id]
        
        row = await conn.fetchrow("SELECT id FROM budgets WHERE id = $1", cat_id)
        assert row is None
        
        # Verify subcategory budget is unaffected
        row_sub = await conn.fetchrow("SELECT id FROM budgets WHERE id = $1", sub_id)
        assert row_sub is not None
        print("Verify Test 2 Passed!")
        
        # --- TEST 3: Safety filter limit check ---
        print("\n--- Test 3: Safety filter limit check ---")
        res = await budget.delete_budgets_impl(
            conn, user_id
        )
        print("Delete response:", res)
        assert res["status"] == "error"
        assert "target filter" in res["message"]
        print("Verify Test 3 Passed!")
        
        # --- TEST 4: Isolation boundary check ---
        print("\n--- Test 4: Isolation boundary check ---")
        # Try to delete sub_id as user_id + 999
        res = await budget.delete_budgets_impl(
            conn, user_id + 999,
            budget_ids=[sub_id]
        )
        print("Delete response:", res)
        assert res["status"] == "ok"
        assert res["deleted_count"] == 0  # Should not delete anything
        
        # Verify budget still exists
        row_sub = await conn.fetchrow("SELECT id FROM budgets WHERE id = $1", sub_id)
        assert row_sub is not None
        print("Verify Test 4 Passed!")

        # --- TEST 5: Date range filter check ---
        print("\n--- Test 5: Date range filter check ---")
        # Create a temporary budget starting in future
        res_temp = await budget.create_budget_impl(
            conn, user_id,
            budget_type="overall",
            amount=200.0,
            period="weekly",
            start_date="2026-08-01",
            end_date="2026-08-07"
        )
        temp_id = res_temp["created_ids"][0]
        
        # Delete budgets ending in August or before, starting in August or after
        res = await budget.delete_budgets_impl(
            conn, user_id,
            start_date="2026-08-01",
            end_date="2026-08-07"
        )
        print("Delete response:", res)
        assert res["status"] == "ok"
        assert res["deleted_count"] == 1
        assert res["deleted_ids"] == [temp_id]
        
        row_temp = await conn.fetchrow("SELECT id FROM budgets WHERE id = $1", temp_id)
        assert row_temp is None
        print("Verify Test 5 Passed!")

        # Clean up database
        print("\nCleaning up leftover test budgets...")
        await conn.execute("DELETE FROM budgets WHERE id = $1", sub_id)
        print("Cleanup done!")
        
    print("\nAll tests completed successfully!")

if __name__ == "__main__":
    asyncio.run(run_tests())
