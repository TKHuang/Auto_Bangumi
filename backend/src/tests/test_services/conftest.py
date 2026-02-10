"""Fixtures and mocks for service tests."""

# Mock pydantic.fields.Undefined for FastAPI compatibility
try:
    from pydantic import fields
    if not hasattr(fields, "Undefined"):
        fields.Undefined = None
except ImportError:
    pass
