import json
from pathlib import Path

from parola.annotate import from_annotation
from parola.manifest import check_manifest

REF = (
    "# status: reviewed\n# audio_file: a.m4a\n# duration: 120.000\n\n"
    "[00:00:00.000 - 00:00:02.000] lang=it\nCiao a tutti.\n"
)


def record(**kw):
    base = dict(
        id="it-001",
        audio="data/private/a.m4a",
        reference="data/private/a.ref.json",
        reference_quality="gold",
        lang="it",
        duration=120.0,
        source="own recording",
        license="private",
        consent=True,
    )
    return {**base, **kw}


def write(tmp_path: Path, *records) -> Path:
    path = tmp_path / "test.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in records) + "\n")
    return path


def test_valid_manifest(tmp_path):
    report = check_manifest(
        write(tmp_path, record(), record(id="en-001", lang="en", duration=1800)), tmp_path
    )
    assert report.errors == []
    assert report.hours_by_lang() == {"it": 120 / 3600, "en": 0.5}
    assert report.summary() == "2 records (references: 2 gold); en 0.50 h, it 0.03 h"


def test_schema_errors(tmp_path):
    bad = [
        record(lang="fr"),
        record(id="x2", duration=0),
        record(id="x3", audio="/abs/a.m4a"),
        record(id="x4", audio="../a.m4a"),
        {"id": "x5"},
    ]
    report = check_manifest(write(tmp_path, *bad), tmp_path)
    assert len(report.errors) == 5
    assert report.records == []


def test_invalid_json_line(tmp_path):
    path = tmp_path / "m.jsonl"
    path.write_text("{not json\n")
    assert len(check_manifest(path, tmp_path).errors) == 1


def test_duplicate_ids(tmp_path):
    report = check_manifest(write(tmp_path, record(), record()), tmp_path)
    assert any("duplicate id" in e for e in report.errors)


def test_private_recording_requires_consent(tmp_path):
    report = check_manifest(write(tmp_path, record(consent=False)), tmp_path)
    assert any("without consent" in e for e in report.errors)
    public = record(audio="data/raw/kiparla/a.wav", consent=False, license="CC BY-NC-SA 4.0")
    assert check_manifest(write(tmp_path, public), tmp_path).errors == []


def test_check_files(tmp_path):
    private = tmp_path / "data" / "private"
    private.mkdir(parents=True)
    path = write(
        tmp_path,
        record(),
        record(id="it-002", audio="data/private/b.m4a", reference=None, reference_quality=None),
    )

    report = check_manifest(path, tmp_path, check_files=True)
    assert any("audio not found: data/private/a.m4a" in e for e in report.errors)
    assert any("reference not found" in e for e in report.errors)

    (private / "a.m4a").write_bytes(b"")
    (private / "b.m4a").write_bytes(b"")
    from_annotation(REF).save(private / "a.ref.json")
    report = check_manifest(path, tmp_path, check_files=True)
    assert report.errors == []
    assert report.warnings == ["line 2: 'it-002' has no reference yet"]


def test_check_files_duration_and_lint(tmp_path):
    private = tmp_path / "data" / "private"
    private.mkdir(parents=True)
    (private / "a.m4a").write_bytes(b"")
    from_annotation(REF.replace("Ciao", "Okay")).save(private / "a.ref.json")
    report = check_manifest(write(tmp_path, record(duration=200)), tmp_path, check_files=True)
    assert any("convention errors" in e for e in report.errors)
    assert any("differs from reference" in e for e in report.errors)


def test_reference_quality_goes_with_reference(tmp_path):
    bad = [
        record(reference_quality=None),
        record(id="x2", reference=None),
        record(id="x3", reference_quality="bronze"),
    ]
    report = check_manifest(write(tmp_path, *bad), tmp_path)
    assert len(report.errors) == 3


def test_gold_and_silver_count_for_disfluency_metrics(tmp_path):
    report = check_manifest(
        write(
            tmp_path,
            record(),
            record(id="it-002", reference_quality="silver"),
            record(id="it-003", reference=None, reference_quality=None),
        ),
        tmp_path,
    )
    assert report.errors == []
    assert [r.counts_for_disfluency_metrics for r in report.records] == [True, True, False]
    assert "references: 1 gold, 1 silver, 1 none" in report.summary()


def test_adjudicated_quality_and_derived_from(tmp_path):
    from parola.manifest import check_free_training_sources

    rec = record(reference_quality="adjudicated", derived_from=["crisperwhisper"])
    report = check_manifest(write(tmp_path, rec, record(id="it-002")), tmp_path)
    assert report.errors == []
    assert report.records[0].counts_for_disfluency_metrics
    assert "1 gold" in report.summary() and "1 adjudicated" in report.summary()
    errors = check_free_training_sources(report.records)
    assert len(errors) == 1 and errors[0].startswith("it-001: derived from crisperwhisper")
