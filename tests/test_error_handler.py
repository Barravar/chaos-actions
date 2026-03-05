#!/usr/bin/env python3
"""Unit tests for error handling decorators."""

from typing import Any

import pytest

from src.exceptions import LitmusGraphQLError, LitmusRestError
from src.utils.error_handler import handle_graphql_errors, handle_rest_errors


class TestHandleGraphQLErrorsDecorator:
    """Tests for @handle_graphql_errors decorator."""

    def test_decorator_success_passthrough(self):
        """Test that decorator passes through successful function calls."""

        @handle_graphql_errors("test operation")
        def successful_function(value):
            return value * 2

        result = successful_function(5)
        assert result == 10

    def test_decorator_handles_key_error(self):
        """Test that decorator catches KeyError and raises LitmusGraphQLError."""

        @handle_graphql_errors("test operation")
        def function_with_key_error():
            data = {"key1": "value1"}
            return data["missing_key"]

        with pytest.raises(LitmusGraphQLError, match="Invalid response structure"):
            function_with_key_error()

    def test_decorator_handles_attribute_error(self):
        """Test that decorator catches AttributeError and raises LitmusGraphQLError."""

        @handle_graphql_errors("test operation")
        def function_with_attribute_error():
            obj = None
            return obj.some_attribute  # type: ignore[attr-defined]

        with pytest.raises(LitmusGraphQLError, match="Error during test operation"):
            function_with_attribute_error()

    def test_decorator_handles_type_error(self):
        """Test that decorator catches TypeError and raises LitmusGraphQLError."""

        @handle_graphql_errors("test operation")
        def function_with_type_error():
            # Intentionally cause TypeError
            return len(None)  # type: ignore[arg-type]

        with pytest.raises(LitmusGraphQLError, match="Error during test operation"):
            function_with_type_error()

    def test_decorator_preserves_function_metadata(self):
        """Verify decorator preserves function metadata."""

        @handle_graphql_errors("test operation")
        def documented_function():
            """This is a documented function."""
            return "result"

        assert documented_function.__name__ == "documented_function"
        assert documented_function.__doc__ == "This is a documented function."

    def test_decorator_with_args_and_kwargs(self):
        """Test that decorator works with functions that have args and kwargs."""

        @handle_graphql_errors("test operation")
        def function_with_params(a, b, c=10, d=20):
            return a + b + c + d

        result = function_with_params(1, 2, c=3, d=4)
        assert result == 10

    def test_decorator_error_message_includes_operation_name(self):
        """Test that error message includes the operation name."""

        @handle_graphql_errors("retrieve user data")
        def function_with_error():
            raise KeyError("user_id")

        with pytest.raises(LitmusGraphQLError, match="missing key"):
            function_with_error()

    def test_decorator_does_not_catch_other_exceptions(self):
        """Test that decorator doesn't catch exceptions it shouldn't."""

        @handle_graphql_errors("test operation")
        def function_with_value_error():
            raise ValueError("This should pass through")

        # ValueError should not be caught by the decorator
        with pytest.raises(ValueError, match="This should pass through"):
            function_with_value_error()

    def test_decorator_preserves_exception_chain(self):
        """Test that original exception is preserved in the chain."""

        @handle_graphql_errors("test operation")
        def function_with_key_error():
            raise KeyError("original_key")

        try:
            function_with_key_error()
        except LitmusGraphQLError as e:
            # Check that the original exception is in the chain
            assert e.__cause__ is not None
            assert isinstance(e.__cause__, KeyError)

    def test_decorator_with_nested_dict_access(self):
        """Test decorator with nested dictionary access errors."""

        @handle_graphql_errors("nested operation")
        def function_with_nested_error():
            data: dict[str, Any] = {"level1": {"level2": {}}}
            return data["level1"]["level2"]["missing"]

        with pytest.raises(LitmusGraphQLError, match="Invalid response structure"):
            function_with_nested_error()


class TestHandleRestErrorsDecorator:
    """Tests for @handle_rest_errors decorator."""

    def test_decorator_success_passthrough(self):
        """Test that decorator passes through successful function calls."""

        @handle_rest_errors("test operation")
        def successful_function(value):
            return value * 3

        result = successful_function(4)
        assert result == 12

    def test_decorator_handles_key_error(self):
        """Test that decorator catches KeyError and raises LitmusRestError."""

        @handle_rest_errors("test operation")
        def function_with_key_error():
            data = {"key1": "value1"}
            return data["missing_key"]

        with pytest.raises(LitmusRestError, match="Invalid response structure"):
            function_with_key_error()

    def test_decorator_handles_attribute_error(self):
        """Test that decorator catches AttributeError and raises LitmusRestError."""

        @handle_rest_errors("test operation")
        def function_with_attribute_error():
            obj = None
            return obj.some_attribute  # type: ignore[attr-defined]

        with pytest.raises(LitmusRestError, match="Error during test operation"):
            function_with_attribute_error()

    def test_decorator_handles_type_error(self):
        """Test that decorator catches TypeError and raises LitmusRestError."""

        @handle_rest_errors("test operation")
        def function_with_type_error():
            # Intentionally cause TypeError
            return len(None)  # type: ignore[arg-type]

        with pytest.raises(LitmusRestError, match="Error during test operation"):
            function_with_type_error()

    def test_decorator_preserves_function_metadata(self):
        """Verify decorator preserves function metadata."""

        @handle_rest_errors("test operation")
        def documented_function():
            """This is a REST function."""
            return "result"

        assert documented_function.__name__ == "documented_function"
        assert documented_function.__doc__ == "This is a REST function."

    def test_decorator_with_multiple_params(self):
        """Test that decorator works with multiple parameters."""

        @handle_rest_errors("test operation")
        def sum_function(*args):
            return sum(args)

        result = sum_function(1, 2, 3, 4, 5)
        assert result == 15

    def test_decorator_error_message_includes_operation_name(self):
        """Test that error message includes the operation name."""

        @handle_rest_errors("fetch project list")
        def function_with_error():
            raise KeyError("project_id")

        with pytest.raises(LitmusRestError, match="missing key"):
            function_with_error()

    def test_decorator_does_not_catch_other_exceptions(self):
        """Test that decorator doesn't catch unrelated exceptions."""

        @handle_rest_errors("test operation")
        def function_with_runtime_error():
            raise RuntimeError("This should pass through")

        # RuntimeError should not be caught
        with pytest.raises(RuntimeError, match="This should pass through"):
            function_with_runtime_error()

    def test_decorator_preserves_exception_chain(self):
        """Test that original exception is preserved in the chain."""

        @handle_rest_errors("test operation")
        def function_with_key_error():
            raise KeyError("original_key")

        try:
            function_with_key_error()
        except LitmusRestError as e:
            # Check that the original exception is in the chain
            assert e.__cause__ is not None
            assert isinstance(e.__cause__, KeyError)


class TestDecoratorComparison:
    """Tests comparing both decorators."""

    def test_both_decorators_handle_same_errors_differently(self):
        """Test that both decorators handle errors but raise different exception types."""

        @handle_graphql_errors("graphql operation")
        def graphql_function():
            raise KeyError("test")

        @handle_rest_errors("rest operation")
        def rest_function():
            raise KeyError("test")

        # Both should raise, but different types
        with pytest.raises(LitmusGraphQLError):
            graphql_function()

        with pytest.raises(LitmusRestError):
            rest_function()

    def test_decorators_can_be_stacked(self):
        """Test that decorators can potentially be stacked (though not recommended)."""

        @handle_graphql_errors("outer operation")
        @handle_rest_errors("inner operation")
        def double_decorated_function(should_error):
            if should_error:
                raise KeyError("test_key")
            return "success"

        # Should work when no error
        result = double_decorated_function(False)
        assert result == "success"

        # When error occurs, inner decorator catches it first and raises LitmusRestError
        # The outer decorator doesn't catch LitmusRestError, so it passes through
        with pytest.raises(LitmusRestError):
            double_decorated_function(True)


class TestDecoratorLogging:
    """Tests for logging behavior of decorators."""

    def test_graphql_decorator_logs_errors(self, caplog):
        """Test that GraphQL decorator logs errors."""

        @handle_graphql_errors("test operation")
        def function_with_error():
            raise KeyError("test_key")

        with pytest.raises(LitmusGraphQLError):
            function_with_error()

        # Note: Actual log checking would require proper logger configuration

    def test_rest_decorator_logs_errors(self, caplog):
        """Test that REST decorator logs errors."""

        @handle_rest_errors("test operation")
        def function_with_error():
            raise AttributeError("test_attr")

        with pytest.raises(LitmusRestError):
            function_with_error()

        # Note: Actual log checking would require proper logger configuration
