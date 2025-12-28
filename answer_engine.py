from app.services.phi_cleaner import redact_text


def generate_answer(question: str, retrieved_docs: list[str]) -> dict:
    """Generate a PHI-safe, non-diagnostic clinical-style summary from retrieved documents.

    Returns a dict with:
      - summary: short narrative (non-diagnostic)
      - patterns: list of observed patterns or recurring findings
      - red_flags: list of findings that may warrant urgent evaluation (non-prescriptive)
      - follow_up: neutral follow-up considerations or tests to consider
      - note: clear non-diagnostic disclaimer
    """

    if not retrieved_docs:
        return {
            "summary": "No relevant patient information found in the uploaded records.",
            "patterns": [],
            "red_flags": [],
            "follow_up": [],
            "note": "This is an informational summary only and does not constitute medical advice or a diagnosis."
        }

    # PHI-safe: redact likely identifiers before any processing/view
    cleaned_docs = [redact_text(d) for d in retrieved_docs]
    context = " ".join(cleaned_docs).lower()
    q = question.lower()

    summary_parts = []
    patterns = set()
    red_flags = set()
    follow_up = set()

    # Focused logic for chest pain / cardiopulmonary concerns
    if "chest pain" in q or "chest" in q:
        if "chest pain" in context or "chest discomfort" in context:
            summary_parts.append("Chest pain or chest discomfort is documented in the available records.")
            patterns.add("chest pain documented")

        # Patterns and red flags
        if any(tok in context for tok in ["shortness of breath", "sob", "dyspnea", "difficulty breathing"]):
            patterns.add("breathing difficulty noted")
            red_flags.add("new or worsening shortness of breath")

        if any(tok in context for tok in ["radiat", "radiating", "left arm", "jaw pain", "neck pain"]):
            patterns.add("pain radiating to arm/jaw/neck")
            red_flags.add("pain radiating to arm/jaw/neck")

        if any(tok in context for tok in ["sweat", "diaphor", "lightheaded", "syncope", "collapse", "near syncope"]):
            red_flags.add("sudden diaphoresis, fainting, or lightheadedness")

        if any(tok in context for tok in ["palpitation", "irregular heartbeat", "tachycardia"]):
            patterns.add("palpitations or irregular heartbeat")
            follow_up.add("consider cardiac monitoring or rhythm assessment")

        # Non-diagnostic follow ups
        follow_up.add("consider ECG and vital signs assessment")
        follow_up.add("consider urgent evaluation if red flags are present")

    # Breathing / respiratory concerns
    if "breath" in q or "breathing" in q or "dyspnea" in q or "sob" in q:
        if any(tok in context for tok in ["shortness of breath", "dyspnea", "difficulty breathing", "wheeze", "wheezing", "cough"]):
            summary_parts.append("Breathing difficulty or dyspnea is documented in the available records.")
            patterns.add("breathing difficulty noted")

        if any(tok in context for tok in ["oxygen saturation", "o2 sat", "o2sat", "saturation"]):
            patterns.add("oxygen saturation recorded")
            follow_up.add("review oxygen saturation and vital signs")

        if any(tok in context for tok in ["severe", "sudden", "worse", "worsening"]):
            red_flags.add("new or rapidly worsening shortness of breath")

        # non-diagnostic follow-ups
        follow_up.add("consider pulse oximetry and respiratory assessment")
        follow_up.add("consider chest auscultation and imaging if clinically indicated")

    # Generic supportive checks for other query types
    if "fever" in q or "temperature" in q:
        if "fever" in context:
            patterns.add("fever documented")
            follow_up.add("consider infectious workup and monitoring")

    if "headache" in q:
        if "headache" in context:
            patterns.add("headache documented")
            follow_up.add("consider neuro exam and pain management; escalate if new focal deficits")

    # Final composition
    summary = " ".join(summary_parts) if summary_parts else (
        "Relevant findings were noted in the available records that may relate to the query."
    )

    note = (
        "This summary is informational only and is not a diagnosis or medical advice. "
        "Consider clinical correlation, physical examination, and appropriate diagnostic testing."
    )

    return {
        "summary": summary,
        "patterns": sorted(patterns),
        "red_flags": sorted(red_flags),
        "follow_up": sorted(follow_up),
        "note": note
    }
