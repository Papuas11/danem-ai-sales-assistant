from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class AnalysisPayload(BaseModel):
    summary: str = ""
    known_info: List[str] = Field(default_factory=list)
    missing_info: List[str] = Field(default_factory=list)
    questions_for_client: List[str] = Field(default_factory=list)
    recommended_services: List[str] = Field(default_factory=list)
    upsell_suggestions: List[str] = Field(default_factory=list)
    action_plan: List[str] = Field(default_factory=list)
    deal_probability: str = "unknown"
    potential_revenue: str = ""
    estimated_cost: str = ""
    estimated_profit: str = ""
    estimated_timeline: str = ""
    recommended_next_step: str = ""
    draft_message_to_client: str = ""


class DealCreateRequest(BaseModel):
    title: str
    client_name: str
    contact_name: str = ""
    raw_input: str


class DealNoteCreateRequest(BaseModel):
    source: str = "manager"
    content: str


class DealResponse(BaseModel):
    id: int
    title: str
    client_name: str
    contact_name: str
    status: str
    raw_input: str
    current_summary: str
    deal_probability: str
    potential_revenue: float
    estimated_cost: float
    estimated_profit: float
    estimated_timeline: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DealDetailResponse(DealResponse):
    analysis: AnalysisPayload
    notes: list[dict]
