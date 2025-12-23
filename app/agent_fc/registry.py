"""Function registry with schema enforcement for handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Type

from pydantic import BaseModel

Handler = Callable[..., Any]


@dataclass
class RegisteredFunction:
    """Metadata for a registered function handler."""

    name: str
    handler: Handler
    arg_model: Type[BaseModel]

    def validate_arguments(self, arguments: Mapping[str, Any]) -> BaseModel:
        return self.arg_model.model_validate(arguments)


class FunctionRegistry:
    """Maintains the set of callable functions available to the agent."""

    def __init__(self) -> None:
        self._functions: Dict[str, RegisteredFunction] = {}

    def register(self, name: str, handler: Handler, arg_model: Type[BaseModel]) -> None:
        if name in self._functions:
            raise ValueError(f"Function '{name}' is already registered")
        if not callable(handler):
            raise TypeError("handler must be callable")
        if not isinstance(arg_model, type) or not issubclass(arg_model, BaseModel):
            raise TypeError("arg_model must be a Pydantic BaseModel subclass")

        registered_function = RegisteredFunction(
            name=name,
            handler=handler,
            arg_model=arg_model,
        )
        self._functions[name] = registered_function

    def get(self, name: str) -> RegisteredFunction:
        if name not in self._functions:
            raise KeyError(f"Function '{name}' is not registered")
        return self._functions[name]

    def list(self) -> List[str]:
        return sorted(self._functions.keys())
