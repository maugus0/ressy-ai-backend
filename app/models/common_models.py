from pydantic import BaseModel, ConfigDict


class PaginationResponse(BaseModel):
    page: int
    limit: int
    total: int
    pages: int
    model_config = ConfigDict(extra="ignore")
