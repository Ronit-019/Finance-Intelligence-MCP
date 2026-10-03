import hashlib
import secrets
import hmac


def hash_password(password: str) -> str:
    """
    Hash a password using PBKDF2-HMAC-SHA256.
    """

    salt = secrets.token_bytes(32)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        600_000
    )

    return (
        f"pbkdf2_sha256$600000$"
        f"{salt.hex()}$"
        f"{password_hash.hex()}"
    )


def verify_password(password: str, stored_hash: str) -> bool:
    """
    Verify a password against a stored PBKDF2 hash.
    """

    try:
        algorithm, iterations, salt_hex, hash_hex = stored_hash.split("$")

        if algorithm != "pbkdf2_sha256":
            return False

        iterations = int(iterations)

        salt = bytes.fromhex(salt_hex)
        expected_hash = bytes.fromhex(hash_hex)

        actual_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations
        )

        return hmac.compare_digest(
            actual_hash,
            expected_hash
        )

    except (ValueError, TypeError):
        return False


def generate_token() -> str:
    """
    Generate a cryptographically secure authentication token.
    """

    return secrets.token_urlsafe(48)


async def create_user(
    conn,
    email: str,
    password: str,
    username: str = None
):
    """
    Create a new application user.
    """

    email = email.strip().lower()

    if not email:
        raise ValueError("Email is required.")

    if len(password) < 8:
        raise ValueError(
            "Password must be at least 8 characters long."
        )

    existing = await conn.fetchrow(
        """
        SELECT id
        FROM users
        WHERE email = $1
        """,
        email
    )

    if existing:
        raise ValueError(
            "An account with this email already exists."
        )

    password_hash = hash_password(password)
    token = generate_token()

    if not username:
        username = email.split("@")[0]

    username = username.strip()

    user_id = await conn.fetchval(
        """
        INSERT INTO users (
            username,
            token,
            email,
            password_hash
        )
        VALUES ($1, $2, $3, $4)
        RETURNING id
        """,
        username,
        token,
        email,
        password_hash
    )

    return {
        "user_id": user_id,
        "username": username,
        "email": email,
        "token": token
    }


async def authenticate_user(
    conn,
    email: str,
    password: str
):
    """
    Authenticate a user using email and password.
    """

    email = email.strip().lower()

    user = await conn.fetchrow(
        """
        SELECT
            id,
            username,
            email,
            password_hash
        FROM users
        WHERE email = $1
        """,
        email
    )

    if user is None:
        raise ValueError("Invalid email or password.")

    if not user["password_hash"]:
        raise ValueError(
            "This account does not have password "
            "authentication configured."
        )

    if not verify_password(
        password,
        user["password_hash"]
    ):
        raise ValueError("Invalid email or password.")

    token = generate_token()

    await conn.execute(
        """
        UPDATE users
        SET token = $1
        WHERE id = $2
        """,
        token,
        user["id"]
    )

    return {
        "user_id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "token": token
    }


async def get_user_from_token(
    conn,
    token: str
):
    """
    Resolve an authenticated application user
    from their access token.
    """

    if not token:
        return None

    token = token.strip()

    row = await conn.fetchrow(
        """
        SELECT
            id,
            username,
            email
        FROM users
        WHERE token = $1
        """,
        token
    )

    if row is None:
        return None

    return dict(row)