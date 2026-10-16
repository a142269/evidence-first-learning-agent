"""Versioned salted password hashes with login-time legacy migration."""
import hashlib
import hmac
import secrets

ITERATIONS = 600_000
PREFIX = "pbkdf2_sha256"


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS)
    return f"{PREFIX}${ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        if "$" not in encoded:
            return len(encoded) == 64 and hmac.compare_digest(
                hashlib.sha256(password.encode()).hexdigest(), encoded,
            )
        algorithm, iterations, salt, digest = encoded.split("$")
        rounds = int(iterations)
        if algorithm != PREFIX or not 100_000 <= rounds <= 2_000_000:
            return False
        if len(salt) != 32 or len(digest) != 64:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), rounds)
        return hmac.compare_digest(actual.hex(), digest)
    except (ValueError, TypeError):
        return False


def needs_rehash(encoded: str) -> bool:
    return not encoded.startswith(f"{PREFIX}${ITERATIONS}$")
