"""Live chat word filter (SB-1309, App Store guideline 1.2).

Two properties matter, and they pull against each other: what is on the list
is caught however it is disguised, and the names of real clubs, players and
places that happen to contain those letters are not.
"""

import pytest

from services.content_filter import contains_objectionable_language, normalise


@pytest.mark.unit
class TestCaught:
    @pytest.mark.parametrize(
        "text",
        [
            "fuck off ref",
            "FUCK",
            "Fück this",  # accents stripped
            "FUUUUUCK",  # stretched
            "sh1t call",  # leetspeak
            "$hit",
            "that was shit!",  # trailing punctuation is not a letter
            "what a b!tch",
            "@sshole",
            "asssshole",  # stretched past the listed double
            "shitty refereeing",
            "motherfucker",
            "fuckin hell",
            "you retard",
            "dickhead",
            "wanker",
            "absolute cunt",
        ],
    )
    def test_listed_words_are_caught(self, text):
        assert contains_objectionable_language(text)

    def test_a_slur_is_caught(self):
        assert contains_objectionable_language("go home f4ggot")


@pytest.mark.unit
class TestNotCaught:
    @pytest.mark.parametrize(
        "text",
        [
            "Scunthorpe United away",
            "Dickson with the equaliser",
            "Cockburn header off the bar",
            "Hancock in goal",
            "Shittu at centre back",
            "Wankdorf stadium",
            "Cumming and Sexton both booked",
            "great assist from the class of 2011",
            "spicy game",
            "rapeseed fields by the pitch",
            "the therapist was right, grapes scraped",
            "Pakistan tour next year",
            "U15 2-1 at 45+2",
            "",
        ],
    )
    def test_ordinary_chat_and_names_pass(self, text):
        assert not contains_objectionable_language(text)


@pytest.mark.unit
class TestNormalise:
    def test_lowercases_strips_accents_and_splits_on_non_letters(self):
        assert normalise("Café, GOAL!!") == ["cafe", "goal"]

    def test_digits_become_letters_only_inside_words(self):
        assert normalise("sh1t") == ["shit"]
