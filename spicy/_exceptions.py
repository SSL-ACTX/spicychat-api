# spicy/_exceptions.py

class SpicychatError(Exception):
    """Base exception for the Spicychat API library."""
    pass

class AuthenticationError(SpicychatError):
    """Raised for authentication failures."""
    pass

class APIError(SpicychatError):
    """Raised for general API errors."""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"API returned {status_code}: {message}")

class RateLimitError(APIError):
    """Raised when the API rate limit is exceeded."""
    pass

class NotFoundError(APIError):
    """Raised when a resource is not found (404)."""
    pass
