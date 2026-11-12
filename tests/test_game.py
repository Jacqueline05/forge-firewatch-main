import json
import re

import pytest

from src.firewatch.game import GAME_TEXT, haze_patrol_html


def embedded_text(page: str) -> dict:
    match = re.search(r"const T = (\{.*?\});\n", page, re.S)
    assert match, "game text not embedded"
    return json.loads(match.group(1).replace("<\\/", "</"))


@pytest.mark.parametrize("language", ["en", "ms"])
def test_game_page_embeds_text_for_language(language):
    page = haze_patrol_html(language)

    assert "__TEXT__" not in page
    assert "<canvas" in page
    assert embedded_text(page)["title"] == GAME_TEXT[language]["title"]


def test_unknown_language_falls_back_to_english():
    assert embedded_text(haze_patrol_html("xx"))["title"] == "Haze Patrol"


def test_both_languages_have_the_same_text_keys():
    english, malay = GAME_TEXT["en"], GAME_TEXT["ms"]

    assert english.keys() == malay.keys()
    for key in ("rules", "compass", "ranks", "facts"):
        assert len(english[key]) == len(malay[key]), key
    assert len(english["compass"]) == 8


def test_ranks_start_at_zero_and_increase():
    for language in GAME_TEXT:
        thresholds = [threshold for threshold, _ in GAME_TEXT[language]["ranks"]]
        assert thresholds[0] == 0
        assert thresholds == sorted(thresholds)


def test_text_cannot_break_out_of_the_script_tag(monkeypatch):
    monkeypatch.setitem(GAME_TEXT["en"], "title", "</script><b>x</b>")

    page = haze_patrol_html("en")

    assert page.count("</script>") == 1
    assert embedded_text(page)["title"] == "</script><b>x</b>"
