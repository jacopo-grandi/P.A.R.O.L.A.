"""parola doctor: nothing personal in it, and one probe failing does not hide the others."""

from parola import doctor


def test_device_kind_keeps_the_kind_and_drops_the_name():
    airpods = {"_name": "AirPods Pro di Mario", "coreaudio_device_srate": 24000,
               "coreaudio_device_transport": "coreaudio_device_type_bluetooth"}  # fmt: skip
    assert doctor.device_kind(airpods) == "Bluetooth (AirPods), 24000 Hz"
    built_in = {"_name": "Microfono MacBook Pro", "coreaudio_device_srate": 48000,
                "coreaudio_device_transport": "coreaudio_device_type_builtin"}  # fmt: skip
    assert doctor.device_kind(built_in) == "Built-in, 48000 Hz"
    assert "Mario" not in doctor.device_kind(airpods)


def test_airpods_are_recognised_by_their_source_name_too():
    device = {"coreaudio_output_source": "AirPods di Giulia",
              "coreaudio_device_transport": "coreaudio_device_type_bluetooth"}  # fmt: skip
    assert doctor.device_kind(device) == "Bluetooth (AirPods)"


def test_the_log_shows_only_warnings_and_errors(tmp_path):
    log = tmp_path / "engine.log"
    log.write_text("parola: http://127.0.0.1:5000\nmic: 3 doubtful words out of 90\n"
                   "warning: the system channel is silent\n"
                   "Traceback (most recent call last):\n")  # fmt: skip
    assert doctor.log_tail(log) == ["warning: the system channel is silent",
                                    "Traceback (most recent call last):"]  # fmt: skip
    assert "no engine log" in doctor.log_tail(tmp_path / "missing.log")[0]


def test_a_failing_probe_is_reported_and_the_rest_still_runs(monkeypatch):
    def broken():
        raise RuntimeError("no sysctl here")

    monkeypatch.setattr(doctor, "PROBES", [("Mac", broken), ("Tools", lambda: "ffmpeg 9")])
    out = doctor.report()
    assert "**Mac:** could not check (RuntimeError: no sysctl here)" in out
    assert "**Tools:** ffmpeg 9" in out
