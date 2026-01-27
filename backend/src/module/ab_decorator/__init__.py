import logging
import threading
import time

from .timeout import timeout

logger = logging.getLogger(__name__)
lock = threading.Lock()


def qb_connect_failed_wait(func):
    def wrapper(*args, **kwargs):
        times = 0
        while times < 5:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.debug(f"URL: {args[0]}")
                logger.warning(e)
                logger.warning("Cannot connect to qBittorrent. Wait 5 min and retry...")
                time.sleep(300)
                times += 1

    return wrapper


def api_failed(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.debug(f"URL: {args[0]}")
            logger.warning("Wrong API response.")
            logger.debug(e)

    return wrapper


def locked(func):
    def wrapper(*args, **kwargs):
        with lock:
            return func(*args, **kwargs)

    return wrapper


def pikpak_retry(max_retries: int = 3, initial_delay: float = 5.0):
    """Retry decorator for PikPak API calls with exponential backoff.

    Handles rate limiting (429) and temporary failures by retrying
    with increasing delays between attempts.

    Args:
        max_retries: Maximum number of retry attempts.
        initial_delay: Initial delay in seconds (doubles each retry).

    Returns:
        Decorated function with retry logic.
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    error_str = str(e).lower()

                    # Check for rate limiting or temporary errors
                    is_rate_limit = "too frequent" in error_str or "429" in error_str
                    is_temporary = "timeout" in error_str or "connection" in error_str

                    if attempt < max_retries and (is_rate_limit or is_temporary):
                        wait_time = delay * (2 if is_rate_limit else 1)
                        logger.warning(
                            f"PikPak API error: {e}. "
                            f"Retrying in {wait_time:.0f}s (attempt {attempt + 1}/{max_retries})"
                        )
                        time.sleep(wait_time)
                        delay *= 2  # Exponential backoff
                    else:
                        # Non-retryable error or max retries reached
                        raise

            raise last_exception

        return wrapper

    return decorator
