"""Sales Core SQLAlchemy Models."""

from typing import List, Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import BaseModel, OrganizationScopedMixin


class Account(BaseModel, OrganizationScopedMixin):
    """Company / Prospect Account."""

    __tablename__ = "accounts"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    employee_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fit_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="prospect", nullable=False
    )  # prospect, prioritized, contacted, discovery, proposal, customer, dormant
    owner_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    annual_revenue: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    apollo_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    why_now: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    cik: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    short_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    contacts: Mapped[List["Contact"]] = relationship(
        "Contact", back_populates="account", cascade="all, delete-orphan"
    )
    opportunities: Mapped[List["Opportunity"]] = relationship(
        "Opportunity", back_populates="account", cascade="all, delete-orphan"
    )


class Contact(BaseModel, OrganizationScopedMixin):
    """Contact Person at an Account."""

    __tablename__ = "contacts"

    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)

    # Critical Business Rules: central attempt count and suppression
    logical_outreach_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_suppressed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    suppression_reason: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    apollo_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    account: Mapped["Account"] = relationship("Account", back_populates="contacts")


class Campaign(BaseModel, OrganizationScopedMixin):
    """Outreach and Acquisition Campaign."""

    __tablename__ = "campaigns"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    channel: Mapped[str] = mapped_column(
        String(50), default="email", nullable=False
    )  # email, sms, linkedin
    status: Mapped[str] = mapped_column(
        String(50), default="draft", nullable=False
    )  # draft, active, paused, completed
    max_logical_attempts: Mapped[int] = mapped_column(
        Integer, default=3, nullable=False
    )  # Strict rule: max 3 attempts

    # Campaign Template & Product Details
    subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    template_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    product_slug: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    product_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    demo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Aggregated Performance Metrics
    target_companies_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    target_contacts_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    emails_sent_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    replies_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    positive_replies_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    recipients: Mapped[List["CampaignRecipient"]] = relationship(
        "CampaignRecipient", back_populates="campaign", cascade="all, delete-orphan"
    )


class CampaignRecipient(BaseModel, OrganizationScopedMixin):
    """Individual contact recipient within a campaign."""

    __tablename__ = "campaign_recipients"

    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    account_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    contact_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False)
    job_title: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    personalized_subject: Mapped[str] = mapped_column(String(500), nullable=False)
    personalized_body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="pending", nullable=False
    )  # pending, approved, sent, failed, suppressed
    sent_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    outlook_message_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Reply Monitoring
    reply_status: Mapped[str] = mapped_column(
        String(50), default="no_reply", nullable=False
    )  # no_reply, received, positive, negative, neutral
    reply_snippet: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reply_received_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="recipients")


class Opportunity(BaseModel, OrganizationScopedMixin):
    """Sales Deal / Opportunity."""

    __tablename__ = "opportunities"

    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    stage: Mapped[str] = mapped_column(
        String(50), default="qualification", nullable=False
    )  # qualification, discovery, proposal, negotiation, closed_won, closed_lost

    # Discovery gate: proposals can only start after verified completed discovery
    discovery_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    discovery_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    account: Mapped["Account"] = relationship("Account", back_populates="opportunities")


class Partner(BaseModel, OrganizationScopedMixin):
    """Co-selling, referral or solution partner."""

    __tablename__ = "partners"

    firm_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    partner_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # referral, co_sell, white_label
    tier: Mapped[str] = mapped_column(
        String(50), default="prospective", nullable=False
    )  # prospective, verified, certified
    agreement_status: Mapped[str] = mapped_column(
        String(50), default="pending", nullable=False
    )  # pending, executed, active
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False)


class Referral(BaseModel, OrganizationScopedMixin):
    """Partner referral attribution."""

    __tablename__ = "referrals"

    partner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("partners.id", ondelete="CASCADE"), nullable=False, index=True
    )
    referred_account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(50), default="submitted", nullable=False
    )  # submitted, accepted, qualified, closed
    attribution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class MarketplaceProduct(BaseModel):
    """Product catalog item from marketplace.adople.ai."""

    __tablename__ = "marketplace_products"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    product_url: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    overview: Mapped[str] = mapped_column(Text, nullable=False)
    key_features: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON-serialized list of features
    demo_video_url: Mapped[str] = mapped_column(String(500), nullable=False)
    target_pain_points: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON-serialized list of pain points
    target_roles: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON-serialized list of target roles

