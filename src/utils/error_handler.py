"""Error handling utilities and decorators."""

import functools
import logging
from typing import Callable, TypeVar, Any
from ..exceptions import LitmusGraphQLError, LitmusRestError

logger = logging.getLogger(__name__)

T = TypeVar('T')


def handle_graphql_errors(operation_name: str) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to handle common GraphQL API errors with consistent logging.
    
    Args:
        operation_name: Human-readable name of the operation for error messages.
        
    Returns:
        Decorator function that wraps the target function with error handling.
        
    Example:
        @handle_graphql_errors("retrieve environment ID")
        def get_environment_id(client, env_name, project_id):
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return func(*args, **kwargs)
            except KeyError as e:
                logger.error(f"Missing required key in {operation_name} response: {e}")
                raise LitmusGraphQLError(f"Invalid response structure: missing key {e}") from e
            except (AttributeError, TypeError) as e:
                logger.error(f"Error during {operation_name}: {e}")
                raise LitmusGraphQLError(f"Error during {operation_name}: {e}") from e
        return wrapper
    return decorator


def handle_rest_errors(operation_name: str) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to handle common REST API errors with consistent logging.
    
    Args:
        operation_name: Human-readable name of the operation for error messages.
        
    Returns:
        Decorator function that wraps the target function with error handling.
        
    Example:
        @handle_rest_errors("retrieve project ID")
        def get_project_id(client, project_name):
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return func(*args, **kwargs)
            except KeyError as e:
                logger.error(f"Missing required key in {operation_name} response: {e}")
                raise LitmusRestError(f"Invalid response structure: missing key {e}") from e
            except (AttributeError, TypeError) as e:
                logger.error(f"Error during {operation_name}: {e}")
                raise LitmusRestError(f"Error during {operation_name}: {e}") from e
        return wrapper
    return decorator
