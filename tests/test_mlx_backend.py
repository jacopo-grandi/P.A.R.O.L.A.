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
