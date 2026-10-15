from ilat.asr.mlx_whisper_backend import convert_result

# Shape of the dict returned by mlx_whisper.transcribe(..., word_timestamps=True).
SAMPLE = {
    "text": " Ehm, allora iniziamo.",
    "language": "it",
    "segments": [
        {
            "id": 0,
            "start": 0.0,
            "end": 2.4,
            "text": " Ehm, allora iniziamo.",
            "words": [
                {"word": " Ehm,", "start": 0.0, "end": 0.5, "probability": 0.61},
                {"word": " allora", "start": 0.6, "end": 1.2, "probability": 0.97},
                {"word": " ", "start": 1.2, "end": 1.2, "probability": 0.1},
                {"word": " iniziamo.", "start": 1.3, "end": 1.29, "probability": 0.95},
            ],
        }
    ],
}


def test_convert_result():
    result = convert_result(SAMPLE)
    assert result.language == "it"
    [seg] = result.segments
    assert seg.text == "Ehm, allora iniziamo."
    assert seg.lang == "it"
    assert [w.text for w in seg.words] == ["Ehm,", "allora", "iniziamo."]
    assert seg.words[0].probability == 0.61


def test_convert_result_clamps_inverted_word_times():
    last = convert_result(SAMPLE).segments[0].words[-1]
    assert last.start == 1.3
    assert last.end == 1.3


def test_convert_result_empty():
    result = convert_result({"text": "", "segments": [], "language": "en"})
    assert result.segments == []
    assert result.language == "en"


def test_convert_result_merges_elisions():
    raw = {
        "language": "it",
        "segments": [
            {
                "start": 0.0,
                "end": 2.0,
                "text": " Sei d'accordo?",
                "words": [
                    {"word": " Sei", "start": 0.0, "end": 0.3, "probability": 0.9},
                    {"word": " d", "start": 0.4, "end": 0.5, "probability": 0.8},
                    {"word": "'accordo?", "start": 0.5, "end": 1.1, "probability": 0.6},
                ],
            }
        ],
    }
    [seg] = convert_result(raw).segments
    assert [w.text for w in seg.words] == ["Sei", "d'accordo?"]
    merged = seg.words[1]
    assert (merged.start, merged.end, merged.probability) == (0.4, 1.1, 0.6)
    assert " ".join(w.text for w in seg.words) == seg.text


def test_convert_result_keeps_segments_sorted():
    raw = {
        "language": "it",
        "segments": [
            {"start": 10.0, "end": 10.5, "text": " creare", "words": []},
            {"start": 9.0, "end": 9.4, "text": " passare", "words": []},
            {"start": 11.0, "end": 12.0, "text": " poi", "words": []},
        ],
    }
    segs = convert_result(raw).segments
    assert [s.text for s in segs] == ["creare", "passare", "poi"]
    assert [(s.start, s.end) for s in segs] == [(10.0, 10.5), (10.0, 10.0), (11.0, 12.0)]


def test_sound_share():
    from ilat.asr.mlx_whisper_backend import sound_share

    regions = [(1.0, 2.0), (4.0, 6.0)]
    assert sound_share(0.0, 4.0, regions) == 0.25
    assert sound_share(4.5, 5.5, regions) == 1.0
    assert sound_share(2.5, 3.5, regions) == 0.0
    assert sound_share(1.5, 1.5, regions) == 1.0 and sound_share(3.0, 3.0, regions) == 0.0


def test_has_sound_keeps_long_segments_with_some_speech():
    from ilat.asr.mlx_whisper_backend import has_sound
    from ilat.schema import Segment, Word

    regions = [(10.0, 15.0)]
    long_seg = Segment(
        start=0,
        end=30,
        text="a b",
        words=[Word(text="a", start=11.0, end=11.5), Word(text="b", start=12.0, end=12.4)],
    )
    assert has_sound(long_seg, regions)  # little sound overall, but its words are on sound
    invented = Segment(
        start=0,
        end=8,
        text="Grazie a tutti.",
        words=[
            Word(text="Grazie", start=0.0, end=3.0),
            Word(text="a", start=3.0, end=5.0),
            Word(text="tutti.", start=5.0, end=8.0),
        ],
    )
    assert not has_sound(invented, regions)
    assert has_sound(
        Segment(start=9.8, end=9.9, text="x", words=[Word(text="x", start=9.75, end=9.8)]), regions
    )
