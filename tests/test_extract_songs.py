from infrastructure.setlistfm_client import SetlistFMClient


def make_setlist(songs):
    return {"sets": {"set": [{"song": songs}]}}


def test_basic_song():
    setlist = make_setlist([{"name": "Song A"}])
    songs = SetlistFMClient._extract_songs(setlist, include_taped=False)
    assert songs == [
        {"name": "Song A", "cover_artist": None, "is_medley_candidate": False, "is_tape": False}
    ]


def test_empty_name_skipped():
    setlist = make_setlist([{"name": "  "}, {"name": ""}, {"name": "Real"}])
    songs = SetlistFMClient._extract_songs(setlist, include_taped=False)
    assert [s["name"] for s in songs] == ["Real"]


def test_taped_excluded_by_default():
    setlist = make_setlist([{"name": "Intro", "tape": True}, {"name": "Live"}])
    songs = SetlistFMClient._extract_songs(setlist, include_taped=False)
    assert [s["name"] for s in songs] == ["Live"]


def test_taped_included_when_requested():
    setlist = make_setlist([{"name": "Intro", "tape": True}])
    songs = SetlistFMClient._extract_songs(setlist, include_taped=True)
    assert songs[0]["name"] == "Intro"
    assert songs[0]["is_tape"] is True


def test_cover_artist_extracted():
    setlist = make_setlist([{"name": "Hurt", "cover": {"name": "Nine Inch Nails"}}])
    songs = SetlistFMClient._extract_songs(setlist, include_taped=False)
    assert songs[0]["cover_artist"] == "Nine Inch Nails"


def test_medley_detection():
    setlist = make_setlist([{"name": "Part One / Part Two"}, {"name": "No/Slash"}])
    songs = SetlistFMClient._extract_songs(setlist, include_taped=False)
    assert songs[0]["is_medley_candidate"] is True
    assert songs[1]["is_medley_candidate"] is False


def test_multiple_sets_flattened():
    setlist = {"sets": {"set": [
        {"song": [{"name": "A"}]},
        {"song": [{"name": "B"}]},
    ]}}
    songs = SetlistFMClient._extract_songs(setlist, include_taped=False)
    assert [s["name"] for s in songs] == ["A", "B"]


def test_empty_setlist():
    assert SetlistFMClient._extract_songs({}, include_taped=False) == []
