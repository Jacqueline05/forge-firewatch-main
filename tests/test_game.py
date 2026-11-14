import json
import re

import pytest

from src.firewatch.game import GAME_AREAS, GAME_TEXT, haze_patrol_html


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


def test_practice_map_uses_fictional_locations_not_a_fixed_region():
    page = haze_patrol_html()

    assert "Delhi" in page
    assert "Kuching" not in page
    assert "Sarawak" not in page


@pytest.mark.parametrize("area", GAME_AREAS)
def test_practice_map_uses_selected_area(area):
    page = haze_patrol_html(area=area)

    assert f'const REGION = "{area}";' in page


def test_unknown_practice_area_is_rejected():
    with pytest.raises(ValueError, match="Unknown Haze Patrol area"):
        haze_patrol_html(area="Borneo")


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


def test_player_must_choose_a_continent_before_starting():
    page = haze_patrol_html()

    assert '<button id="startBtn" disabled>' in page
    assert 'for (const name of ["Asia", "America", "Europe"])' in page
    assert "if (!chosenArea) return;" in page


@pytest.mark.parametrize("language", ["en", "ms"])
def test_continent_names_are_translated(language):
    text = GAME_TEXT[language]

    assert set(text["areas"]) == set(GAME_AREAS)
    assert text["chooseArea"] and text["changeArea"]
