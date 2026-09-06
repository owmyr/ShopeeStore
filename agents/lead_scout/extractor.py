import re


def is_valid_cnpj(cnpj: str) -> bool:
    """Validate a Brazilian CNPJ."""
    digits = re.sub(r"\D", "", cnpj)
    if len(digits) != 14:
        return False

    if len(set(digits)) == 1:
        return False

    def calculate_digit(c: str, weights: list[int]) -> int:
        s = sum(int(d) * w for d, w in zip(c, weights))
        rem = s % 11
        return 0 if rem < 2 else 11 - rem

    w1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    w2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

    d1 = calculate_digit(digits[:12], w1)
    if int(digits[12]) != d1:
        return False

    d2 = calculate_digit(digits[:13], w2)
    if int(digits[13]) != d2:
        return False

    return True


def extract_cnpj(text: str) -> str | None:
    """Extract a valid CNPJ from text."""
    pattern = r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b"
    matches = re.findall(pattern, text)
    for match in matches:
        digits = re.sub(r"\D", "", match)
        if is_valid_cnpj(digits):
            return digits
    return None


def extract_instagram(text: str) -> str | None:
    """Extract an Instagram handle from text."""
    pattern = r"(?<![a-zA-Z0-9._%+-])@([a-zA-Z0-9._]{3,30})|instagram\.com/([a-zA-Z0-9._]{3,30})"
    for m in re.finditer(pattern, text):
        handle = m.group(1) or m.group(2)
        if handle:
            # check if it looks like an email domain
            if handle.lower() in {"gmail", "hotmail", "outlook", "yahoo", "uol", "bol"}:
                continue
            if handle.lower().endswith((".com", ".com.br")):
                continue
            return handle
    return None


def extract_email(text: str) -> str | None:
    """Extract an email from text."""
    pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    for match in re.findall(pattern, text):
        email = match.lower()
        if "example@" in email or email.endswith("@shopee.com"):
            continue
        return match
    return None
