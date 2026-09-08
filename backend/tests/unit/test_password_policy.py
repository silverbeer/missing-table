"""Password policy (SB-640).

A working prod admin account had an eight-character dictionary word plus
`123`, and nothing in the app rejected it. These tests pin the shape of
password that must not be accepted again, and — just as important — the
ones that must still be, so the policy does not push people toward
predictable variants.
"""

import pytest

from constants.passwords import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH, validate_password
from models.auth import ResetPasswordRequest, UserSignup


@pytest.mark.unit
class TestTheRule:
    def test_a_long_ordinary_passphrase_is_accepted(self):
        # No composition rules: length is what is asked for.
        assert validate_password("correct horse battery") == "correct horse battery"

    def test_too_short_is_rejected_however_complex(self):
        # 11 characters with every character class, still short.
        with pytest.raises(ValueError, match="at least"):
            validate_password("Aa1!Bb2@Cc3")

    def test_the_minimum_length_is_accepted(self):
        assert validate_password("a" * MIN_PASSWORD_LENGTH)

    def test_the_password_found_in_production_is_rejected(self):
        # An eight-character dictionary word plus digits. Length alone stops
        # this one; the blocklist below is what stops the longer variants.
        with pytest.raises(ValueError):
            validate_password("password123")

    def test_a_common_word_padded_to_length_is_still_rejected(self):
        # Long enough to pass the length floor, so only the blocklist can
        # catch these — which is the point of having one.
        for weak in ("password1234", "soccer123456", "letmein12345", "welcome123456", "qwerty123456"):
            with pytest.raises(ValueError, match="too common"):
                validate_password(weak)

    def test_a_common_word_inside_a_longer_phrase_is_fine(self):
        # The blocklist matches the whole password, not a substring: banning
        # every password containing "test" would reject good passphrases.
        assert validate_password("the greatest testament")

    def test_a_password_containing_the_username_is_rejected(self):
        with pytest.raises(ValueError, match="username"):
            validate_password("gabe_ifa_35_rocks", username="gabe_ifa_35")

    def test_a_short_username_does_not_poison_the_check(self):
        # A two-character username would otherwise reject half of everything.
        assert validate_password("about a hundred", username="ab")

    def test_an_over_long_password_is_rejected(self):
        # bcrypt truncates past 72 bytes, so longer is not stronger, and
        # hashing an unbounded string on a public endpoint is a free CPU sink.
        with pytest.raises(ValueError, match="at most"):
            validate_password("a" * (MAX_PASSWORD_LENGTH + 1))

    def test_multibyte_length_is_measured_in_bytes(self):
        # 30 emoji are 120 bytes: under the character cap, over the byte one.
        with pytest.raises(ValueError, match="at most"):
            validate_password("🔒" * 30)


@pytest.mark.unit
class TestSignupModel:
    def _signup(self, password, username="gabe_ifa_35"):
        return UserSignup(username=username, password=password, email="a@b.com")

    def test_a_weak_password_fails_the_model(self):
        with pytest.raises(ValueError):
            self._signup("password123")

    def test_a_good_password_passes(self):
        assert self._signup("correct horse battery").password

    def test_the_username_rule_reaches_the_model(self):
        # The reason this is a model validator and not a field one.
        with pytest.raises(ValueError, match="username"):
            self._signup("gabe_ifa_35_extra")


@pytest.mark.unit
class TestResetModel:
    def test_reset_enforces_the_same_policy_as_signup(self):
        # Reset used to accept six characters, which made it the way around
        # whatever signup asked for.
        with pytest.raises(ValueError):
            ResetPasswordRequest(token="t", new_password="abc123")  # pragma: allowlist secret
        with pytest.raises(ValueError, match="too common"):
            ResetPasswordRequest(token="t", new_password="password1234")  # pragma: allowlist secret

    def test_a_good_reset_password_passes(self):
        assert ResetPasswordRequest(
            token="t",
            new_password="correct horse battery",  # pragma: allowlist secret
        ).new_password
