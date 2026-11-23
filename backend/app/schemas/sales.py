"""Sales Domain Pydantic Schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# Account Schemas
class AccountBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    domain: str = Field(min_length=3, max_length=255)
    industry: Optional[str] = None
    employee_count: Optional[int] = None
    fit_score: float = 0.0
    status: str = "prospect"
    owner_id: Optional[str] = None


class AccountCreate(AccountBase):
    pass


class AccountUpdate(BaseModel):
    name: Optional[str] = None
    domain: Optional[str] = None
    industry: Optional[str] = None
    employee_count: Optional[int] = None
    fit_score: Optional[float] = None
    status: Optional[str] = None
    owner_id: Optional[str] = None


class AccountResponse(AccountBase):
    id: str
    organization_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Contact Schemas
class ContactBase(BaseModel):
    account_id: str
    first_name: str
    last_name: str
    email: EmailStr
    phone: Optional[str] = None
    title: Optional[str] = None


class ContactCreate(ContactBase):
    pass


class ContactResponse(ContactBase):
    id: str
    organization_id: str
    logical_outreach_attempts: int
    is_suppressed: bool
    suppression_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Opportunity Schemas
class OpportunityBase(BaseModel):
    account_id: str
    name: str
    amount: Optional[float] = None
    stage: str = "qualification"
    discovery_completed: bool = False
    discovery_notes: Optional[str] = None
    owner_id: Optional[str] = None


class OpportunityCreate(OpportunityBase):
    pass


class OpportunityResponse(OpportunityBase):
    id: str
    organization_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Campaign Schemas
class CampaignBase(BaseModel):
    name: str
    channel: str = "sms"
    status: str = "draft"
    max_logical_attempts: int = 3


class CampaignCreate(CampaignBase):
    pass


class CampaignResponse(CampaignBase):
    id: str
    organization_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
