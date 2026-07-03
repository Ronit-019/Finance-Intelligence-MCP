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
        
        # 2. Insert 55 test expenses (exceeds threshold 50)
        print("Creating 55 test expenses...")
        for i in range(1, 56):
            await main.add_expense("2026-07-02", 10.0, "food", "groceries", f"Item {i}")
            
        # 3. Call list_expenses
        print("Calling list_expenses...")
        res = await main.list_expenses(start_date="2026-07-01", end_date="2026-07-31")
        
        # Assertions
        assert isinstance(res, dict)
        assert res["status"] == "ok"
        assert "truncated" in res["message"]
        assert len(res["data"]) == 50
        
        export_path = res["export_url"].replace("file:///", "").replace("/", os.sep)
        print(f"Checking exported file path: {export_path}")
        assert os.path.exists(export_path)
        
        # Open XLSX and check workbook rows
        import openpyxl
        wb = openpyxl.load_workbook(export_path)
        ws = wb.active
        rows_list = list(ws.rows)
        print(f"XLSX has {len(rows_list)} lines (including header)")
        # 1 header + 55 data lines = 56 lines
        assert len(rows_list) == 56
            
        print("Verify XLSX Excel Export Test Passed!")
        
        # 4. Cleanup
        print("\nCleaning up test expenses...")
        await conn.execute("DELETE FROM expenses WHERE user_id = $1", user_id)
        # delete csv file
        if os.path.exists(export_path):
            os.remove(export_path)
        print("Cleanup done!")
        
    print("\nAll tests completed successfully!")

if __name__ == "__main__":
    asyncio.run(run_tests())
