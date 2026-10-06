from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DocumentRole = Literal["purchase_order", "invoice", "payment_request"]


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field_key: str
    value_type: Literal["identifier", "text", "number", "money", "date"]
    raw_value: str | None
    page_id: str
    block_ids: list[str] = Field(default_factory=list)
    quote: str
    group_key: str | None
    role: str | None = None
    unit: str | None = None

    @model_validator(mode="after")
    def item_requires_row_group(self):
        if self.field_key.startswith("item.") and not self.group_key:
            raise ValueError(
                "Every item.* observation requires a non-null group_key shared by that row's cells"
            )
        return self


class Extraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_type: Literal[
        "purchase_order", "invoice", "payment_request", "purchase_request", "unknown", "mixed"
    ]
    mixed_document: bool = False
    observations: list[Observation]
    uncertainties: list[str] = Field(default_factory=list)
    page_coverage: list[str]
