"""
Password policy (SB-640).

A working prod admin account had an eight-character dictionary word plus
`123`. Nothing in the app rejected it: Supabase's own minimum is low and the
API added nothing on top.

The policy follows NIST SP 800-63B in shape — **length first, no composition
rules** — because forcing a symbol turns `password` into `Password1!` and
buys nothing. What actually stops the password that was found is a length
floor plus a blocklist that ignores decorative digits.

Deliberately not here: expiry, forced rotation, and a "must contain one of
each" rule. All three push people toward predictable variants.
"""

MIN_PASSWORD_LENGTH = 12

# bcrypt (what Supabase Auth uses) silently truncates past 72 bytes, so a
# longer password is not stronger, and hashing an unbounded string is a cheap
# way to burn CPU on a public endpoint.
MAX_PASSWORD_LENGTH = 72

# Bases that appear at the top of every credential list. Compared after
# stripping trailing digits and punctuation, so `soccer123!` is caught by
# `soccer`. Not a substitute for a breach corpus — it is the cheap half that
# catches the shape of password this policy exists to reject.
COMMON_PASSWORD_BASES = frozenset(
    {
        "password",
        "passwd",
        "pass",
        "letmein",
        "welcome",
        "admin",
        "administrator",
        "qwerty",
        "qwertyuiop",
        "asdfgh",
        "zxcvbn",
        "iloveyou",
        "monkey",
        "dragon",
        "football",
        "baseball",
        "basketball",
        "soccer",
        "sunshine",
        "princess",
        "trustno",
        "master",
        "shadow",
        "superman",
        "batman",
        "michael",
        "jennifer",
        "jordan",
        "hockey",
        "ranger",
        "abc",
        "abcd",
        "test",
        "testing",
        "changeme",
        "secret",
        "login",
        "starwars",
        "whatever",
        "freedom",
        "missingtable",
        "mlsnext",
    }
)


def _base(password: str) -> str:
    """The word under the decoration: lowercased, trailing digits/symbols cut."""
    return password.lower().rstrip("0123456789!@#$%^&*()_+-=.,?")


def validate_password(password: str, *, username: str | None = None) -> str:
    """Raise ValueError when a password is too weak to accept.

    Applied wherever a password is *set* — signup and reset — and never at
    login: an existing weak password must still authenticate, or rotating it
    would be impossible. Rotating the accounts that already have one is a
    separate, human step.
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    if len(password.encode("utf-8")) > MAX_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at most {MAX_PASSWORD_LENGTH} bytes")
    if _base(password) in COMMON_PASSWORD_BASES:
        raise ValueError("Password is too common — adding digits to a common word does not make it stronger")
    if username and len(username) >= 3 and username.lower() in password.lower():
        raise ValueError("Password must not contain your username")
    return password
