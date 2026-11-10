"""Password hashing with the standard library, in the format that Werkzeug used.

The format is `method$salt$hexdigest`, where the method is `scrypt:n:r:p` or `pbkdf2:digest:iterations`,
so hashes created before the move away from Werkzeug keep working.
"""

import hashlib
import hmac
import secrets
import string

SALT_CHARS = string.ascii_letters + string.digits
SALT_LENGTH = 16
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**15, 8, 1


def _digest(method: str, salt: str, password: str) -> str:
    name, *params = method.split(":")
    if name == "scrypt":
        n, r, p = (int(param) for param in params) if params else (SCRYPT_N, SCRYPT_R, SCRYPT_P)
        return hashlib.scrypt(password.encode(), salt=salt.encode(), n=n, r=r, p=p, maxmem=132 * n * r * p).hex()
    if name == "pbkdf2":
        digest, iterations = params[0], int(params[1])
        return hashlib.pbkdf2_hmac(digest, password.encode(), salt.encode(), iterations).hex()
    raise ValueError(f"Unknown password hashing method: {name!r}")


def generate_password_hash(password: str) -> str:
    """Hash a password with scrypt and a random salt."""
    method = f"scrypt:{SCRYPT_N}:{SCRYPT_R}:{SCRYPT_P}"
    salt = "".join(secrets.choice(SALT_CHARS) for _ in range(SALT_LENGTH))
    return f"{method}${salt}${_digest(method, salt, password)}"


def check_password_hash(password_hash: str, password: str) -> bool:
    """Check a password against a hash, in constant time. A malformed hash never matches."""
    try:
        method, salt, expected = password_hash.split("$", 2)
        actual = _digest(method, salt, password)
    except ValueError, IndexError:
        return False
    return hmac.compare_digest(actual, expected)
