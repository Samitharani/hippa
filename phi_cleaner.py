import re

def redact_text(text: str) -> str:
    # Normalize spacing: do not globally replace colons (breaks patterns).
    # We'll match labels flexibly and preserve surrounding punctuation.
    patterns = {
        "NAME": r"(?:Patient\s+)?Name\s*:\s*[A-Za-z ,.'-]+",
        "AGE": r"Age\s*:\s*\d{1,3}",
        "GENDER": r"Gender\s*:\s*(Male|Female|Other|M|F)",
        "DOB": r"DOB\s*:\s*\d{1,2}/\d{1,2}/\d{4}",
        "PHONE": r"Phone\s*:\s*[\d\-\(\) ]{7,15}",
    }

    for label, pattern in patterns.items():
        text = re.sub(
            pattern,
            f"[REDACTED:{label}]",
            text,
            flags=re.IGNORECASE
        )

    # Catch cases where a numeric age remains after a nearby redaction (e.g. "[REDACTED:NAME] : 29")
    text = re.sub(r"\]\s*:\s*(\d{1,3})", r"]\n[REDACTED:AGE]", text)
    # Fallback: redact any leftover loose "Age: 29" patterns
    text = re.sub(
        r"(?<!\w)Age\s*[:\-]?\s*\n?\s*\d{1,3}",
        "[REDACTED:AGE]",
        text,
        flags=re.IGNORECASE
    )

    # 🔥 FORCE CLEAN LINE STRUCTURE
    text = re.sub(r"\s*\[REDACTED:", r"\n[REDACTED:", text)
    text = re.sub(r"\]\s*", "]\n", text)

    # Remove extra blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()
