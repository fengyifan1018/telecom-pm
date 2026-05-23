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

    model_config = {"from_attributes": True}
