from fastapi import HTTPException, status
from pydantic import ValidationError


def validate_payload(model, payload: dict | None):
    """
    Validate an incoming payload against a Pydantic model and raise
    a 400 HTTPException with serialized errors on failure.
    """
    try:
        return model.model_validate(payload or {})
    except ValidationError as exc:
        serialized_errors = []
        for err in exc.errors():
            ctx = err.get("ctx") or {}
            ctx_serialized = {k: str(v) for k, v in ctx.items()} if ctx else None
            err_copy = {k: v for k, v in err.items() if k != "ctx"}
            if ctx_serialized:
                err_copy["ctx"] = ctx_serialized
            serialized_errors.append(err_copy)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=serialized_errors)
