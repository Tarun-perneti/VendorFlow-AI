"""
email_draft.py — Email generation for VendorFlow AI

Generates professional email drafts based on the workflow decision.
Uses the LLM for a polished email, with a template-based fallback.

Why not just hardcode templates?
- LLM-generated emails sound more natural and professional.
- They can incorporate specific details from the validation results.

Why have a fallback?
- The app must work even if the LLM API is down.
- Templates ensure we always produce SOME email draft.
"""

from core.models import WorkflowDecision
from core.llm import ask_llm


def generate_email_draft(
    company_name: str,
    decision: WorkflowDecision,
) -> str:
    """
    Generate a professional email draft to send to the vendor.
    
    Tries LLM first for a polished result, falls back to a template.
    
    Args:
        company_name: The vendor's company name.
        decision: The WorkflowDecision containing status and details.
    
    Returns:
        A formatted email string ready for human review.
    """
    # Try LLM-generated email first
    llm_email = _generate_llm_email(company_name, decision)
    if llm_email:
        return llm_email

    # Fallback: template-based email
    return _generate_template_email(company_name, decision)


def _generate_llm_email(company_name: str, decision: WorkflowDecision) -> str | None:
    """
    Ask the LLM to draft a professional vendor communication email.
    Returns None if the LLM is unavailable.
    """
    # Build context for the LLM
    failed_items = "\n".join(
        f"- {c.message}" for c in decision.failed_checks
    ) or "None"

    missing_items = "\n".join(
        f"- {item}" for item in decision.missing_info
    ) or "None"

    next_steps = "\n".join(
        f"- {action}" for action in decision.next_actions
    ) or "None"

    prompt = f"""Draft a professional email to a vendor regarding their onboarding application.

Company Name: {company_name}
Application Status: {decision.status}
Decision Explanation: {decision.explanation}

Issues Found:
{failed_items}

Missing Information:
{missing_items}

Suggested Next Steps:
{next_steps}

Requirements for the email:
- Professional and courteous tone.
- Clearly state the application status.
- If APPROVED: congratulate and explain next steps.
- If PENDING: explain what information is needed and how to provide it.
- If REJECTED: explain the reason clearly and suggest how to resubmit.
- Keep it concise (under 200 words).
- Include a placeholder for the sender name: [Your Name].
- Include a placeholder for contact email: [contact@company.com].
- Do not include a subject line.
"""

    system_instruction = (
        "You are a professional business communication writer. "
        "Write clear, courteous vendor onboarding emails."
    )

    return ask_llm(prompt, system_instruction)


def _generate_template_email(company_name: str, decision: WorkflowDecision) -> str:
    """
    Fallback: generate an email using templates.
    Used when the LLM is unavailable.
    """
    if decision.status == "APPROVED":
        return (
            f"Dear {company_name} Team,\n\n"
            f"We are pleased to inform you that your vendor onboarding application "
            f"has been APPROVED.\n\n"
            f"All verification checks have passed successfully. "
            f"You will be added to our approved vendor list shortly.\n\n"
            f"Next steps:\n"
            + "\n".join(f"  • {a}" for a in decision.next_actions)
            + "\n\n"
            f"If you have any questions, please contact us at [contact@company.com].\n\n"
            f"Best regards,\n[Your Name]"
        )

    elif decision.status == "REJECTED":
        return (
            f"Dear {company_name} Team,\n\n"
            f"Thank you for submitting your vendor onboarding application. "
            f"After review, we are unable to approve your application at this time.\n\n"
            f"Reason: {decision.explanation}\n\n"
            f"To resubmit:\n"
            + "\n".join(f"  • {a}" for a in decision.next_actions)
            + "\n\n"
            f"If you believe this is an error, please contact us at [contact@company.com].\n\n"
            f"Best regards,\n[Your Name]"
        )

    else:  # PENDING
        missing = "\n".join(f"  • {m}" for m in decision.missing_info) or "  • Please review flagged items."
        return (
            f"Dear {company_name} Team,\n\n"
            f"Thank you for submitting your vendor onboarding application. "
            f"Your application is currently PENDING and requires additional "
            f"information or review.\n\n"
            f"Items requiring attention:\n{missing}\n\n"
            f"Next steps:\n"
            + "\n".join(f"  • {a}" for a in decision.next_actions)
            + "\n\n"
            f"Please provide the requested information at your earliest convenience.\n\n"
            f"Best regards,\n[Your Name]"
        )

