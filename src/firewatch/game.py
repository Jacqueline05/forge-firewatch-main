"""Haze Patrol: a 60-second arcade game about Sarawak fires and haze.

The game itself runs in the browser (``haze_patrol.html``, plain canvas and
JavaScript). Python only fills in the text for the chosen language.
"""
from __future__ import annotations

import json
from pathlib import Path


GAME_FILE = Path(__file__).with_name("haze_patrol.html")

GAME_TEXT = {
    "en": {
        "title": "Haze Patrol",
        "sub": "60 seconds to protect Sarawak's towns from haze.",
        "rules": [
            "🔥 <b>Tap fires</b> to drop water. Small fires give bonus points.",
            "🟤 <b>Peat fires</b> grow faster and make more smoke: get them first!",
            "💨 <b>Smoke drifts with the wind.</b> Each puff that reaches a town "
            "costs ❤️ clean air.",
            "🏭 <b>Gas flares are false alarms.</b> Don't tap them (−50).",
        ],
        "start": "▶ Start patrol",
        "again": "🔄 Play again",
        "over": "Patrol over",
        "stopped": "Patrol stopped",
        "pause": "Pause",
        "stop": "Stop",
        "stopGame": "Stop game",
        "resume": "Resume",
        "paused": "Paused",
        "pausedSub": "Take a breath. The fires will wait for you.",
        "go": "Go! Protect the towns",
        "windChange": "Wind changed:",
        "wind": "Wind",
        "level": "Level",
        "air": "Clean air",
        "peat": "PEAT",
        "combo": "Combo",
        "falseAlarm": "False alarm! −50",
        "lostAir": "Out of clean air",
        "saved": "Fires out:",
        "falseTaps": "False alarms:",
        "best": "Best:",
        "compass": ["north", "north-east", "east", "south-east",
                    "south", "south-west", "west", "north-west"],
        "key": [
            ["🔥", "Tap fires to put them out"],
            ["🟤", "Peat fires: put out first"],
            ["🏭", "Gas flare: don't tap"],
            ["💨", "Smoke follows the wind arrow"],
        ],
        "ranks": [
            [0, "🌱 Junior Ranger"],
            [2000, "🚒 Fire Fighter"],
            [5000, "🛰️ Haze Hunter"],
            [9000, "🔥 Haze Hero"],
        ],
        "facts": [
            "Peat fires can smoulder underground for weeks, which is why they cause "
            "most of Borneo's haze.",
            "MODIS and VIIRS are NASA satellite sensors. When both see the same heat, "
            "a real fire is more likely.",
            "Gas flares and factories show up as heat too. That's why FireWatch "
            "filters known heat sources.",
            "Smoke follows the wind. During the south-west monsoon (June to "
            "September) haze often drifts north-east.",
            "A satellite hotspot is a heat signal, not proof of a fire. Ground "
            "reports help confirm what is really happening.",
        ],
    },
    "ms": {
        "title": "Peronda Jerebu",
        "sub": "60 saat untuk melindungi bandar di Sarawak daripada jerebu.",
        "rules": [
            "🔥 <b>Ketik kebakaran</b> untuk menjatuhkan air. Api kecil beri mata bonus.",
            "🟤 <b>Kebakaran gambut</b> membesar lebih cepat dan menghasilkan lebih "
            "banyak asap: padamkan dahulu!",
            "💨 <b>Asap hanyut mengikut angin.</b> Setiap kepulan yang sampai ke "
            "bandar mengurangkan ❤️ udara bersih.",
            "🏭 <b>Suar gas ialah amaran palsu.</b> Jangan ketik (−50).",
        ],
        "start": "▶ Mula meronda",
        "again": "🔄 Main semula",
        "over": "Rondaan tamat",
        "stopped": "Rondaan dihentikan",
        "pause": "Jeda",
        "stop": "Henti",
        "stopGame": "Hentikan permainan",
        "resume": "Sambung",
        "paused": "Dijeda",
        "pausedSub": "Tarik nafas. Api akan menunggu anda.",
        "go": "Mula! Lindungi bandar",
        "windChange": "Angin bertukar:",
        "wind": "Angin",
        "level": "Tahap",
        "air": "Udara bersih",
        "peat": "GAMBUT",
        "combo": "Kombo",
        "falseAlarm": "Amaran palsu! −50",
        "lostAir": "Udara bersih habis",
        "saved": "Api dipadam:",
        "falseTaps": "Amaran palsu:",
        "best": "Terbaik:",
        "compass": ["utara", "timur laut", "timur", "tenggara",
                    "selatan", "barat daya", "barat", "barat laut"],
        "key": [
            ["🔥", "Ketik api untuk memadamkannya"],
            ["🟤", "Api gambut: padam dahulu"],
            ["🏭", "Suar gas: jangan ketik"],
            ["💨", "Asap mengikut anak panah angin"],
        ],
        "ranks": [
            [0, "🌱 Renjer Muda"],
            [2000, "🚒 Ahli Bomba"],
            [5000, "🛰️ Pemburu Jerebu"],
            [9000, "🔥 Wira Jerebu"],
        ],
        "facts": [
            "Kebakaran gambut boleh membara di bawah tanah berminggu-minggu, sebab "
            "itu ia punca utama jerebu di Borneo.",
            "MODIS dan VIIRS ialah pengesan satelit NASA. Jika kedua-duanya mengesan "
            "haba yang sama, kebakaran sebenar lebih berkemungkinan.",
            "Suar gas dan kilang juga dikesan sebagai haba. Sebab itu FireWatch "
            "menapis sumber haba yang diketahui.",
            "Asap mengikut angin. Semasa monsun barat daya (Jun hingga September) "
            "jerebu sering hanyut ke timur laut.",
            "Titik panas satelit ialah isyarat haba, bukan bukti kebakaran. Laporan "
            "lapangan membantu mengesahkannya.",
        ],
    },
}


def haze_patrol_html(language: str = "en") -> str:
    """The game page with its text in English ("en") or Bahasa Malaysia ("ms")."""
    text = GAME_TEXT.get(language, GAME_TEXT["en"])
    # Escape "</" so the text can never close the <script> tag early.
    payload = json.dumps(text, ensure_ascii=False).replace("</", "<\\/")
    return GAME_FILE.read_text(encoding="utf-8").replace("__TEXT__", payload)
