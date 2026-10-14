import hmac


def authenticate(
    username: str,
    password: str,
    expected_username: str,
    expected_password: str,
) -> bool:
    """Compare credentials without storing or logging them."""
    if not expected_username or not expected_password:
        return False
    return hmac.compare_digest(username, expected_username) and hmac.compare_digest(
        password, expected_password
    )
