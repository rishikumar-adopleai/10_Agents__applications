"""Opportunity Analysis, Contact Ranking, and Outreach Synthesis Engine."""

import re
from typing import Any, Dict, List, Optional, Tuple

from backend.app.core.logging import logger
from backend.app.integrations.ai.gateway import LLMGateway


class OpportunityAnalyzer:
    """Analyzes company signals, ranks contacts by decision-maker role, and drafts outreach."""

    def __init__(self, llm_gateway: Optional[LLMGateway] = None):
        self.llm = llm_gateway or LLMGateway()

    def rank_and_select_contact(
        self,
        contacts: List[Dict[str, Any]],
        signal_type: str,
        why_now: str,
    ) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]], str]:
        """
        Rank contacts according to buying signal and role relevance.
        Returns: (primary_contact, alternative_contacts, selection_rationale)
        """
        if not contacts:
            return None, [], "No contacts found for account"

        signal_str = f"{signal_type} {why_now}".lower()

        # Priority role mappings according to business specifications
        if "ai" in signal_str or "hiring" in signal_str or "engineer" in signal_str:
            target_keywords = ["cto", "vp of engineering", "vp engineering", "director of ai", "head of ai"]
        elif "data" in signal_str or "science" in signal_str:
            target_keywords = ["chief data officer", "head of data science", "director of data", "vp data"]
        elif "modernization" in signal_str or "document" in signal_str:
            target_keywords = [
                "chief technology officer",
                "cto",
                "cio",
                "head of document operations",
                "director of operations",
                "vp technology",
            ]
        elif "expansion" in signal_str or "logistics" in signal_str:
            target_keywords = [
                "chief operating officer",
                "coo",
                "director of operations",
                "vp operations",
                "head of operations",
            ]
        else:
            target_keywords = ["cto", "coo", "vp", "director", "head"]

        scored_contacts = []
        for c in contacts:
            title = (c.get("job_title") or c.get("title") or "").lower()
            seniority = (c.get("seniority") or "").lower()
            email = c.get("email")
            phone = c.get("phone")
            is_suppressed = c.get("is_suppressed", False)
            eligibility = c.get("contact_eligibility", "eligible")

            # Base relevance score
            score = 10
            for idx, kw in enumerate(target_keywords):
                if re.search(r"\b" + re.escape(kw) + r"\b", title):
                    score = 100 - (idx * 10)
                    break

            # Seniority boost
            if "c-level" in seniority or re.search(r"\bchief\b", title):
                score += 15
            elif "vp" in seniority or re.search(r"\bvp\b", title):
                score += 10
            elif "director" in seniority or re.search(r"\bdirector\b", title):
                score += 5

            # Deductions for incomplete/unreachable contacts
            has_method = bool(email or phone)
            if not has_method or eligibility == "blocked_missing_address":
                # Heavy penalty if contact method is missing so reachable contacts are preferred
                score -= 60

            if is_suppressed:
                score -= 100

            scored_contacts.append({
                "contact": c,
                "score": score,
                "has_method": has_method,
                "is_suppressed": is_suppressed,
                "eligibility": eligibility,
            })

        # Sort descending by score
        # pyrefly: ignore[no-matching-overload]
        scored_contacts.sort(key=lambda x: x["score"], reverse=True)

        # Pick best eligible contact with communication method
        primary = None
        alternatives = []
        for item in scored_contacts:
            c = item["contact"]
            if not primary and item["has_method"] and not item["is_suppressed"]:
                primary = c
            else:
                alternatives.append(c)

        # Fallback if no reachable contact exists
        if not primary and scored_contacts:
            primary = scored_contacts[0]["contact"]
            alternatives = [item["contact"] for item in scored_contacts[1:]]
            rationale = "Selected highest-ranking title; however, contact method is incomplete or missing."
        else:
            # pyrefly: ignore[missing-attribute]
            p_title = primary.get("job_title") or primary.get("title") if primary else "N/A"
            rationale = f"Selected {p_title} as primary decision-maker aligned with {signal_type} signal."

        # pyrefly: ignore[bad-return]
        return primary, alternatives, rationale

    def synthesize_research_brief(
        self,
        company_data: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]]:
        """
        Synthesize facts vs. hypotheses with provenance.
        Returns: (facts, hypotheses, sources, evidence_refs)
        """
        company_name = company_data.get("company_name", "Unknown Company")
        industry = company_data.get("industry", "Technology")
        domain = company_data.get("domain", "")
        signals = company_data.get("signals", [])
        priority = company_data.get("priority", {})

        # 1. Verified Facts
        observed_facts = [s.get("observed_fact") for s in signals if s.get("observed_fact")]
        facts = {
            "company_name": company_name,
            "domain": domain,
            "industry": industry,
            "priority_tier": priority.get("tier", "medium"),
            "priority_score": priority.get("score", 70),
            "observed_signals": observed_facts,
            "data_mode": "synthetic_fixture" if company_data.get("is_synthetic") else "verified_live",
        }

        # 2. Potential Business Needs (Hypotheses)
        primary_why = priority.get("why_now", "Scaling operations")
        hypotheses = {
            "primary_driver": primary_why,
            "hypothesized_pain_points": [
                f"Operational latency during {primary_why.lower()}",
                "Need for rapid response automation and consistent qualification workflows",
            ],
            "recommended_value_prop": "Shorten sales response time to under 60 seconds with grounded AI agents",
        }

        # 3. Sources & Evidence References
        sources: Dict[str, Any] = {}
        evidence_refs: List[Dict[str, Any]] = []

        for idx, s in enumerate(signals):
            src = s.get("source", {})
            url = src.get("url") or f"https://{domain}/signal-{idx+1}"
            src_type = src.get("source_type") or "radar_signal"
            sources[f"signal_{idx+1}"] = url
            evidence_refs.append({
                "source_url": url,
                "source_type": src_type,
                "excerpt": s.get("observed_fact") or primary_why,
                "confidence": 1.0 if not company_data.get("is_synthetic") else 0.85,
            })

        return facts, hypotheses, sources, evidence_refs

    @staticmethod
    def get_target_role_titles(signal_type: str, why_now: str) -> List[str]:
        """Return prioritized decision-maker titles aligned with the company's buying signal."""
        signal_str = f"{signal_type} {why_now}".lower()
        if "ai" in signal_str or "hiring" in signal_str or "engineer" in signal_str:
            return ["CTO", "VP of Engineering", "VP Engineering", "Director of AI", "Head of AI"]
        if "data" in signal_str or "science" in signal_str:
            return ["Chief Data Officer", "Head of Data Science", "Director of Data", "VP Data"]
        if "modernization" in signal_str or "document" in signal_str:
            return [
                "Chief Technology Officer",
                "CTO",
                "CIO",
                "Head of Document Operations",
                "Director of Operations",
                "VP Technology",
            ]
        if "expansion" in signal_str or "logistics" in signal_str:
            return [
                "Chief Operating Officer",
                "COO",
                "Director of Operations",
                "VP Operations",
                "Head of operations",
            ]
        return ["CTO", "COO", "VP", "Director", "Head"]

    async def generate_opportunity_analysis(
        self,
        company_data: Dict[str, Any],
        selected_contact: Optional[Dict[str, Any]],
        facts: Dict[str, Any],
        hypotheses: Dict[str, Any],
        mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate structured opportunity analysis conforming to Section 5 requirements.
        """
        company_name = company_data.get("company_name", "Target Company")
        industry = company_data.get("industry", "Enterprise")
        signals = company_data.get("signals", [])
        signal_type = signals[0].get("type", "growth") if signals else "growth"
        contact_name = (
            selected_contact.get("full_name")
            or f"{selected_contact.get('first_name', '')} {selected_contact.get('last_name', '')}".strip()
            if selected_contact
            else "Decision Maker"
        )
        contact_title = (
            selected_contact.get("job_title") or selected_contact.get("title") if selected_contact else "Leader"
        )

        # Determine approved service offering
        if "hiring" in signal_type or "ai" in signal_type:
            service_offering = "Autonomous Enterprise Demo & Inbound Qualification Platform"
            potential_needs = "Accelerating technical evaluation cycles and eliminating demo turnaround bottlenecks"
        elif "expansion" in signal_type or "logistics" in signal_type:
            service_offering = "Operational Workflow Automation & Multi-Site Coordination Suite"
            potential_needs = "Managing multi-site operational expansion without linear staffing overhead"
        elif "modernization" in signal_type or "document" in signal_type:
            service_offering = "Intelligent Document Automation & Compliance Extraction Suite"
            potential_needs = "Automating document ingestion, data extraction, and verification pipelines"
        else:
            service_offering = "Enterprise Sales & Inbound Workflow Automation"
            potential_needs = "Increasing sales velocity and automating inbound deal progression"

        system_prompt = (
            "You are an enterprise sales strategist. Produce a structured JSON opportunity analysis "
            "based strictly on verified company evidence. Do not fabricate facts or customer requirements."
        )
        user_prompt = (
            f"Generate opportunity_analysis for company: {company_name} ({industry}).\n"
            f"Buying signals: {facts.get('observed_signals')}\n"
            f"Contact: {contact_name}, {contact_title}\n"
            f"Service Offering: {service_offering}\n"
            f"Requirements: Return valid JSON containing company_overview, verified_business_info, "
            f"buying_signal_analysis, potential_business_needs, relevant_service_offering, "
            f"supporting_evidence, suggested_contact, unverified_assumptions."
        )

        try:
            llm_result = await self.llm.generate_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_format="json_object",
                mode=mode,
            )
        except Exception as e:
            logger.warning(
                f"LLM generation failed ({type(e).__name__}): {str(e)}. Using grounded fallback analysis."
            )
            llm_result = {}

        # Merge with grounded deterministic baseline to guarantee schema integrity
        analysis = {
            "company_overview": llm_result.get(
                "company_overview",
                f"{company_name} is an enterprise organization in {industry} currently scaling operations.",
            ),
            "verified_business_info": {
                "name": company_name,
                "industry": industry,
                "domain": company_data.get("domain", ""),
                "priority_tier": company_data.get("priority", {}).get("tier", "medium"),
            },
            "buying_signal_analysis": llm_result.get(
                "buying_signal_analysis",
                f"Observed recent activity: {'; '.join(facts.get('observed_signals', []))}.",
            ),
            "potential_business_needs": llm_result.get("potential_business_needs", potential_needs),
            "relevant_service_offering": service_offering,
            "supporting_evidence": facts.get("observed_signals", []),
            "suggested_contact": {
                "name": contact_name,
                "title": contact_title,
                "rationale": f"Key leader for {service_offering} adoption.",
            },
            "unverified_assumptions": [
                "Specific internal software dependencies require confirmation during discovery"
            ],
        }
        return analysis

    def evaluate_demo_suitability(
        self,
        company_data: Dict[str, Any],
        opportunity_analysis: Dict[str, Any],
    ) -> Tuple[bool, Optional[str]]:
        """
        Step 8: Determine whether company justifies a personalized demonstration.
        High priority accounts (tier == 'high' or score >= 80) qualify for demo.
        """
        priority = company_data.get("priority", {})
        tier = priority.get("tier", "medium")
        score = priority.get("score", 0)

        if tier == "high" or score >= 80:
            template = "enterprise_sales_automation_v1"
            return True, template
        return False, None

    def generate_personalized_outreach_draft(
        self,
        company_data: Dict[str, Any],
        selected_contact: Optional[Dict[str, Any]],
        opportunity_analysis: Dict[str, Any],
        demo_reference: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Step 9: Generate evidence-backed, personalized outreach message.
        """
        company_name = company_data.get("company_name", "your team")
        signals = company_data.get("signals", [])
        signal_fact = (
            signals[0].get("observed_fact")
            if signals
            else "your recent expansion"
        )
        service_offering = opportunity_analysis.get(
            "relevant_service_offering", "our enterprise automation platform"
        )

        first_name = "there"
        if selected_contact:
            if selected_contact.get("first_name"):
                first_name = selected_contact["first_name"]
            elif selected_contact.get("full_name"):
                first_name = selected_contact["full_name"].split()[0]

        # Construct message body
        if demo_reference and demo_reference.get("access_url"):
            demo_url = demo_reference["access_url"]
            draft_body = (
                f"Hi {first_name}, noticed {company_name}'s {signal_fact.lower()}. "
                f"We built {service_offering} to help teams streamline operations and accelerate turnaround times. "
                f"I prepared a tailored 2-minute demonstration for your team here: {demo_url}. "
                f"Would you be open to a brief 10-minute conversation next week to see how this fits your roadmap?"
            )
        else:
            draft_body = (
                f"Hi {first_name}, noticed {company_name}'s {signal_fact.lower()}. "
                f"We built {service_offering} to help organizations accelerate operational throughput "
                f"and automate response workflows in under 60 seconds. "
                f"Would you be open to a brief 10-minute conversation next week to discuss this?"
            )

        subject = (
            f"Tailored {company_name} demo — {service_offering}"
            if demo_reference and demo_reference.get("access_url")
            else f"Idea for {company_name} — {service_offering}"
        )

        return {
            "subject": subject,
            "draft_body": draft_body,
            "recipient_name": first_name,
            "recipient_email": selected_contact.get("email") if selected_contact else None,
            "contact_id": selected_contact.get("contact_id") if selected_contact else None,
            "company_name": company_name,
            "reason_for_contact": f"Aligning {service_offering} with {signal_fact}",
            "call_to_action": "10-minute discovery conversation",
            "has_demo": bool(demo_reference),
        }
