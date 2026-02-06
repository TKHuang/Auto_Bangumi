"""Fixtures and mocks for service tests."""

import sys
from unittest.mock import MagicMock

# Mock statemachine module before any imports
statemachine_mock = MagicMock()
statemachine_mock.exceptions = MagicMock()
statemachine_mock.exceptions.TransitionNotAllowed = Exception
sys.modules["statemachine"] = statemachine_mock
sys.modules["statemachine.exceptions"] = statemachine_mock.exceptions

# Mock pydantic.fields.Undefined for FastAPI compatibility
try:
    from pydantic import fields
    if not hasattr(fields, "Undefined"):
        fields.Undefined = None
except ImportError:
    pass
