from datetime import datetime

from pydantic import BaseModel


class TemplateResponse(BaseModel):
    id: int
    product_type: str
    name: str
    version: int
    is_active: bool
    phases: list
    created_at: datetime
    usage_count: int = 0

    model_config = {"from_attributes": True}
