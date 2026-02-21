try:
    from pydantic import fields
    if not hasattr(fields, "Undefined"):
        fields.Undefined = None
except ImportError:
    pass
