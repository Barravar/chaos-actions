"""Serialization utilities for converting dataclasses to dictionaries."""

from typing import Any


def serialize(dataclass_instance: Any) -> dict[str, Any] | Any:
  """
  Convert a dataclass instance to a dictionary suitable for JSON serialization.
  
  Recursively processes dataclass fields, handling nested dataclasses and lists.
  Skips None values to keep payloads clean.
  
  Args:
    dataclass_instance: A dataclass instance to serialize, or any other value.
    
  Returns:
    A dictionary if input is a dataclass, otherwise the value as-is.
    None values are skipped in the output dictionary.
    
  Examples:
    >>> @dataclass
    ... class MyData:
    ...   name: str
    ...   value: int = None
    >>> serialize(MyData(name="test", value=None))
    {'name': 'test'}
  """
  if dataclass_instance is None:
    return None
  
  if not hasattr(dataclass_instance, '__dataclass_fields__'):
    return dataclass_instance  # Not a dataclass, return as is

  result = {}
  for field_name in dataclass_instance.__dataclass_fields__:
    value = getattr(dataclass_instance, field_name)
    if value is None:
      continue
    
    if isinstance(value, list):
      result[field_name] = [serialize(item) for item in value]
    elif hasattr(value, '__dataclass_fields__'):
      result[field_name] = serialize(value)
    else:
      result[field_name] = value
  return result
