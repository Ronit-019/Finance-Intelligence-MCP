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
        print("Save original handlers...")
        orig_get_headers = main.get_http_headers
        
        try:
            # --- TEST 1: Simulate local connection ---
            print("\n--- Test 1: Simulate local developer connection ---")
            main.get_http_headers = lambda: None  # mock local run
            
            user_id = await main.get_authenticated_user_id(conn)
            print(f"Local auth succeeded! User ID resolved: {user_id}")
            assert user_id > 0
            
            # --- TEST 2: Simulate cloud connection without token ---
            print("\n--- Test 2: Simulate cloud connection without token ---")
            main.get_http_headers = lambda: {}  # mock cloud request with no headers
            main.get_http_request = lambda: None  # mock no request query params
            
            try:
                await main.get_authenticated_user_id(conn)
                assert False, "Should have failed authentication!"
            except PermissionError as e:
                print("Correctly rejected cloud connection:", str(e))
                assert "Authentication Required" in str(e)
                
            # --- TEST 3: Call register_user tool ---
            print("\n--- Test 3: Invoke register_user tool ---")
            res = await main.register_user()
            print("Registration result:", res)
            assert res["status"] == "ok"
            assert "token" in res
            
            registered_token = res["token"]
            
            # Check database entry
            db_user = await conn.fetchrow("SELECT id, username, token FROM users WHERE token = $1", registered_token)
            print("DB User record:", dict(db_user))
            assert db_user is not None
            assert db_user["token"] == registered_token
            assert db_user["username"] == registered_token
            
            # --- TEST 4: Simulate cloud connection using headers ---
            print("\n--- Test 4: Simulate cloud connection using x-token header ---")
            main.get_http_headers = lambda: {"x-token": registered_token}
            
            resolved_id = await main.get_authenticated_user_id(conn)
            print(f"Cloud header auth succeeded! Resolved ID: {resolved_id}")
            assert resolved_id == db_user["id"]
            
            # --- TEST 5: Simulate cloud connection with tool parameter argument ---
            print("\n--- Test 5: Simulate cloud connection with token parameter passed as tool argument ---")
            main.get_http_headers = lambda: {}  # Cloud env (headers exist but no token)
            
            resolved_id_param = await main.get_authenticated_user_id(conn, registered_token)
            print(f"Cloud parameter auth succeeded! Resolved ID: {resolved_id_param}")
            assert resolved_id_param == db_user["id"]
            
            # Clean up the generated test user
            print("\nCleaning up registered test user...")
            await conn.execute("DELETE FROM users WHERE token = $1", registered_token)
            print("Cleanup done!")
            
        finally:
            print("Restore original handlers...")
            main.get_http_headers = orig_get_headers
            
    print("\nAll tests completed successfully!")

if __name__ == "__main__":
    asyncio.run(run_tests())
