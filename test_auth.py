import asyncio

from main import get_pool, get_authenticated_user_id


async def main():

    token = None

    pool = await get_pool()

    async with pool.acquire() as conn:

        user_id = await get_authenticated_user_id(
            conn,
            token
        )

        print("AUTHENTICATED USER ID:")
        print(user_id)


asyncio.run(main())