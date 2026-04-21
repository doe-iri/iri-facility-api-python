"""Request context management for API versioning."""
from contextvars import ContextVar

# Context variable to track the current API version path
current_api_version: ContextVar[str] = ContextVar('api_version', default='/api/v1')


def get_api_base_url(url_root: str) -> str:
    """Get the full API base URL including version from current context."""
    api_version = current_api_version.get()
    return f"{url_root}{api_version}"
