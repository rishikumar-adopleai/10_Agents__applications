"""Deterministic Account Scoring Engine conforming to Section 15."""

from typing import Any, Dict, List, Tuple

from backend.app.models.sales import Account


class ScoringEngine:
    """Calculates deterministic ICP Fit and Why Now priority scores using versioned rubrics."""

    def __init__(self, rubric_version: str = "demo-v1"):
        self.rubric_version = rubric_version

    def calculate_icp_fit(
        self, account: Account, criteria: Dict[str, Any]
    ) -> Tuple[float, Dict[str, float]]:
        """Calculate ICP fit score between 0.0 and 1.0 based on approved criteria."""
        breakdown = {
            "country_match": 0.0,
            "industry_match": 0.0,
            "size_match": 0.0,
            "operational_fit": 0.0,
        }

        # 1. Country Check (Must be explicitly verified, never assumed US if unknown)
        target_country = (criteria.get("country") or "United States").lower().strip()
        raw_country = (account.country or "").lower().strip()

        if not raw_country:
            # Unknown country must not automatically be assumed US
            breakdown["country_match"] = 0.0
        else:
            us_synonyms = ["united states", "united states of america", "us", "usa", "u.s.", "u.s.a."]
            if target_country in us_synonyms:
                if raw_country in us_synonyms:
                    breakdown["country_match"] = 1.0
                elif any(s == raw_country for s in us_synonyms):
                    breakdown["country_match"] = 1.0
                else:
                    breakdown["country_match"] = 0.0
            else:
                if target_country in raw_country or raw_country in target_country:
                    breakdown["country_match"] = 1.0
                else:
                    breakdown["country_match"] = 0.0

        # Hard gate: if country does not match approved target country, ICP fit is 0.0
        if breakdown["country_match"] == 0.0:
            return 0.0, breakdown

        # 2. Industry & Subindustry Check
        ind_list = (criteria.get("industries") or []) + (criteria.get("target_industries") or [])
        raw_industries = list(dict.fromkeys(ind_list))
        target_industries = [i.lower().strip() for i in raw_industries if i]
        target_subindustries = [s.lower().strip() for s in criteria.get("target_subindustries", []) if s]
        acc_industry = (account.industry or "").lower().strip()

        industry_matched = False
        if not target_industries:
            # If no industry constraint is set, accept all
            industry_matched = True
            breakdown["industry_match"] = 1.0
        elif not acc_industry:
            # Unknown industry
            breakdown["industry_match"] = 0.0
        else:
            # Exact or substring match in target industries
            for ti in target_industries:
                if ti in acc_industry or acc_industry in ti:
                    industry_matched = True
                    break

            # Subindustries check
            if not industry_matched:
                for tsub in target_subindustries:
                    if tsub in acc_industry or acc_industry in tsub:
                        industry_matched = True
                        break

            if industry_matched:
                breakdown["industry_match"] = 1.0
            else:
                # Controlled semantic affinity strictly per target category
                is_fin_target = any(
                    f in ti for ti in target_industries for f in ["financial", "finance", "bank", "banking"]
                )
                is_health_target = any(
                    h in ti for ti in target_industries for h in ["health", "hospital", "medical", "clinic"]
                )

                if is_fin_target and any(
                    k in acc_industry for k in ["banking", "credit union", "insurance", "financial services", "lending"]
                ):
                    breakdown["industry_match"] = 0.85
                elif is_health_target and any(
                    k in acc_industry for k in ["hospital & health care", "medical practice", "health, wellness", "clinics"]
                ):
                    breakdown["industry_match"] = 0.85
                else:
                    # Non-matching industry (e.g. Retail, Software, or Healthcare when targeting Finance)
                    breakdown["industry_match"] = 0.0

        # Hard gate: if industry does not match approved target industries, fail ICP
        if breakdown["industry_match"] == 0.0:
            return 0.0, breakdown

        # 3. Employee Size Match
        emp_range = str(criteria.get("employee_range", "")).lower().strip()
        if emp_range in ["any", "all", "none", "*", ""]:
            breakdown["size_match"] = 1.0
        else:
            emp_min = criteria.get("employee_min", 20)
            emp_max = criteria.get("employee_max", 500000)
            if account.employee_count is not None:
                if emp_min <= account.employee_count <= emp_max:
                    breakdown["size_match"] = 1.0
                elif account.employee_count > emp_max:
                    breakdown["size_match"] = 0.85
                else:
                    breakdown["size_match"] = 0.40
            else:
                breakdown["size_match"] = 0.70

        # 4. Operational Match
        short_desc = f"{account.short_description or ''} {account.name or ''}".lower()
        raw_ops = criteria.get("operational_focus") or criteria.get("target_operations") or []
        target_ops = [op.lower().replace("_", " ").strip() for op in raw_ops if op]

        if not target_ops:
            breakdown["operational_fit"] = 1.0
        else:
            matches = [op for op in target_ops if op in short_desc]
            if matches:
                breakdown["operational_fit"] = min(1.0, 0.60 + (len(matches) * 0.20))
            else:
                # No operational keyword match
                breakdown["operational_fit"] = 0.20

        # Weighted ICP Fit: country 0.25, industry 0.35, size 0.20, operational 0.20
        total_icp = (
            0.25 * breakdown["country_match"]
            + 0.35 * breakdown["industry_match"]
            + 0.20 * breakdown["size_match"]
            + 0.20 * breakdown["operational_fit"]
        )
        return round(total_icp, 3), breakdown

    def calculate_why_now(
        self, evidences: List[Dict[str, Any]]
    ) -> Tuple[float, Dict[str, float], str, str]:
        """Calculate Why Now priority score and generate concise one-line reason."""
        breakdown = {
            "growth_score": 0.0,
            "hiring_score": 0.0,
            "regulatory_score": 0.0,
            "sec_score": 0.0,
            "interest_score": 0.0,
        }

        reasons = []
        primary_signal = "general_fit"

        # Tally active verified signals
        verified_evidences = [e for e in evidences if e.get("verification_status") == "VERIFIED"]

        growth_evidences = [e for e in verified_evidences if e.get("signal_type") == "growth"]
        hiring_evidences = [e for e in verified_evidences if e.get("signal_type") == "hiring"]
        reg_evidences = [e for e in verified_evidences if e.get("signal_type") == "regulatory"]
        sec_evidences = [e for e in verified_evidences if e.get("signal_type") == "sec_filing"]
        interest_evidences = [e for e in verified_evidences if e.get("signal_type") == "interest"]

        # Growth Signals (highest weighting per proposal guidelines)
        if growth_evidences:
            breakdown["growth_score"] = min(1.0, 0.6 + (len(growth_evidences) * 0.2))
            reasons.append(growth_evidences[0]["observed_fact"])
            primary_signal = "growth"

        # Hiring Signals (Manual work piling up)
        if hiring_evidences:
            breakdown["hiring_score"] = min(1.0, 0.5 + (len(hiring_evidences) * 0.15))
            reasons.append(hiring_evidences[0]["observed_fact"])
            if primary_signal == "general_fit":
                primary_signal = "hiring"

        # Regulatory Deadlines (Calibrated to compliance urgency without overshadowing active company signals)
        if reg_evidences:
            breakdown["regulatory_score"] = min(0.70, 0.50 + (len(reg_evidences) * 0.10))
            reasons.append(reg_evidences[0]["observed_fact"])
            if primary_signal == "general_fit":
                primary_signal = "regulatory"

        # SEC Filings (Material weakness affirmative disclosure)
        if sec_evidences:
            breakdown["sec_score"] = min(0.85, 0.70 + (len(sec_evidences) * 0.10))
            reasons.append(sec_evidences[0]["observed_fact"])
            if primary_signal == "general_fit":
                primary_signal = "sec_filing"

        # Interest in Us (HubSpot verified inbound engagement)
        if interest_evidences:
            breakdown["interest_score"] = min(0.85, 0.65 + (len(interest_evidences) * 0.10))
            reasons.append(interest_evidences[0]["observed_fact"])
            if primary_signal == "general_fit":
                primary_signal = "interest"

        # Compound Why Now score: highest verified signal + multi-signal compound urgency
        active_scores = [v for v in breakdown.values() if v > 0]
        if active_scores:
            max_score = max(active_scores)
            compound_bonus = min(0.20, (len(active_scores) - 1) * 0.10)
            why_now_score = min(1.0, max_score * 0.75 + compound_bonus + 0.05)
        else:
            # Strictly zero if no verified buying signals exist
            why_now_score = 0.0

        # Build one-line reason
        if reasons:
            one_liner = " | ".join(reasons[:2])
        else:
            one_liner = "No verified buying signals observed."

        return round(why_now_score, 3), breakdown, one_liner, primary_signal

    def compute_account_ranking(
        self,
        account: Account,
        criteria: Dict[str, Any],
        evidences: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Compute complete combined score, ranking priority, and reason."""
        icp_score, icp_breakdown = self.calculate_icp_fit(account, criteria)
        why_now_score, why_now_breakdown, why_now_reason, primary_signal = self.calculate_why_now(evidences)

        # Combined Total: 35% ICP Fit + 65% Why Now Urgency
        total_score = round(0.35 * icp_score + 0.65 * why_now_score, 3)

        return {
            "account_id": account.id,
            "account_name": account.name,
            "domain": account.domain,
            "industry": account.industry,
            "icp_score": icp_score,
            "why_now_score": why_now_score,
            "total_score": total_score,
            "why_now_reason": why_now_reason,
            "primary_signal_type": primary_signal,
            "score_breakdown": {
                "rubric_version": self.rubric_version,
                "icp_breakdown": icp_breakdown,
                "why_now_breakdown": why_now_breakdown,
            },
        }
