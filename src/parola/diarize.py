"""Who speaks when, on one channel: sherpa-onnx pieces regrouped by spectral clustering.

Two models, run on the CPU with onnxruntime (decision 0026): pyannote segmentation 3.0 (MIT)
finds where someone speaks, WeSpeaker VoxCeleb ResNet34-LM (CC BY 4.0) gives each stretch a
voice print. sherpa-onnx's own grouping of voice prints mixes speakers up (AMI DER 34-61%), so
its output is used only as many small pieces: each piece is cut into 3 s windows, every window
gets a voice print, and the prints are grouped by spectral clustering with the number of voices
taken from the largest eigengap (NME-SC, as in NeMo). Each piece takes the voice most of its
windows have. On two AMI test meetings: DER 30% (results/2026-10-16-diarization-sherpa.md).

The models are downloaded once into ``~/.cache/parola/diarization`` and checked by SHA-256.
Without sherpa-onnx or the models, ``available()`` is False and calls keep the side labels.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from collections import Counter
from collections.abc import Callable
from pathlib import Path

import numpy as np

CACHE = Path.home() / ".cache" / "parola" / "diarization"
SAMPLE_RATE = 16_000
RELEASES = "https://github.com/k2-fsa/sherpa-onnx/releases/download"
SEGMENTATION = CACHE / "segmentation" / "sherpa-onnx-pyannote-segmentation-3-0" / "model.onnx"
EMBEDDING = CACHE / "embedding" / "wespeaker_en_voxceleb_resnet34_LM.onnx"
MODELS = {
    SEGMENTATION: (
        f"{RELEASES}/speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2",
        "220ad67ca923bef2fa91f2390c786097bf305bceb5e261d4af67b38e938e1079",
    ),
    EMBEDDING: (
        f"{RELEASES}/speaker-recongition-models/wespeaker_en_voxceleb_resnet34_LM.onnx",
        "e9848563da86f263117134dfd7ad63c92355b37de492b55e325400c9d9c39012",
    ),
}
PIECE_THRESHOLD = 0.5  # sherpa-onnx's own grouping, kept loose: many small, clean pieces
WINDOW, STEP, MIN_WINDOW = 3.0, 1.5, 0.8  # seconds
MAX_SPEAKERS = 10
THREADS = 4

Turn = tuple[float, float, int]  # start, end, voice (0, 1, ...)
Progress = Callable[[float], None]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def installed() -> bool:
    try:
        import sherpa_onnx  # noqa: F401
    except ImportError:
        return False
    return True


def available() -> bool:
    return installed() and all(p.exists() for p in MODELS)


def ensure_models() -> None:
    """Download the two models the first time (about 32 MB), checking their SHA-256."""
    for path, (url, digest) in MODELS.items():
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="parola-diarize-") as tmp:
            download = Path(tmp) / url.rsplit("/", 1)[-1]
            urllib.request.urlretrieve(url, download)  # a fixed https URL, checked by SHA-256
            if download.suffix == ".bz2":
                with tarfile.open(download) as tar:
                    member = next(m for m in tar.getmembers() if m.name.endswith("/model.onnx"))
                    with (
                        tar.extractfile(member) as src,
                        (Path(tmp) / "model.onnx").open("wb") as dst,
                    ):
                        shutil.copyfileobj(src, dst)
                download = Path(tmp) / "model.onnx"
            if _sha256(download) != digest:
                raise RuntimeError(f"{path.name}: checksum mismatch, not installed")
            shutil.move(download, path)


def load_audio(path: Path) -> np.ndarray:
    pcm = subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-i", str(path), "-vn", "-ac", "1",
         "-ar", str(SAMPLE_RATE), "-f", "f32le", "-"],
        capture_output=True, check=True,
    ).stdout  # fmt: skip
    return np.frombuffer(pcm, dtype=np.float32)


def _pieces(samples: np.ndarray, progress: Progress | None) -> list[tuple[float, float]]:
    import sherpa_onnx

    config = sherpa_onnx.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(
                model=str(SEGMENTATION)
            ),
            num_threads=THREADS,
        ),
        embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(
            model=str(EMBEDDING), num_threads=THREADS
        ),
        clustering=sherpa_onnx.FastClusteringConfig(num_clusters=-1, threshold=PIECE_THRESHOLD),
        min_duration_on=0.3,
        min_duration_off=0.5,
    )

    def report(done: int, total: int) -> int:
        if progress and total:
            progress(0.8 * done / total)  # the regrouping after it is the other fifth
        return 0

    result = sherpa_onnx.OfflineSpeakerDiarization(config).process(samples, callback=report)
    return [(r.start, r.end) for r in result.sort_by_start_time()]


def _windows(a: float, b: float) -> list[tuple[float, float]]:
    if b - a < MIN_WINDOW:
        return []
    if b - a <= WINDOW:
        return [(a, b)]
    out = [(t, t + WINDOW) for t in np.arange(a, b - WINDOW + 1e-6, STEP)]
    if out[-1][1] < b - 0.25:
        out.append((b - WINDOW, b))
    return out


def spectral_clusters(X: np.ndarray, max_k: int = MAX_SPEAKERS) -> np.ndarray:
    """Group unit vectors; the number of groups comes from the largest eigengap of a pruned
    affinity graph, the pruning chosen to make that gap clearest (NME-SC)."""
    from scipy.cluster.vq import kmeans2

    n = len(X)
    if n < 3:
        return np.zeros(n, dtype=int)
    affinity = np.clip(X @ X.T, 0, 1)
    best = None
    for p in sorted({max(1, int(n * f)) for f in np.linspace(0.02, 0.25, 12)}):
        graph = np.zeros_like(affinity)
        np.put_along_axis(graph, np.argsort(-affinity, axis=1)[:, :p], 1.0, axis=1)
        graph = (graph + graph.T) / 2
        laplacian = np.diag(graph.sum(1)) - graph
        eig = np.linalg.eigvalsh(laplacian)
        gaps = np.diff(eig[: min(max_k, n - 1) + 1])
        k = int(np.argmax(gaps)) + 1
        ratio = p / (gaps[k - 1] / (eig[-1] + 1e-9) + 1e-9)
        if best is None or ratio < best[0]:
            best = (ratio, k, laplacian)
    _, k, laplacian = best
    if k == 1:
        return np.zeros(n, dtype=int)
    vectors = np.linalg.eigh(laplacian)[1][:, :k]
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-9
    return kmeans2(vectors, k, minit="++", seed=0)[1]


def diarize(audio: Path | np.ndarray, progress: Progress | None = None) -> list[Turn]:
    """Turns (start, end, voice) of one channel, voices numbered by first appearance."""
    import sherpa_onnx

    samples = load_audio(audio) if isinstance(audio, Path) else audio
    pieces = _pieces(samples, progress)
    extractor = sherpa_onnx.SpeakerEmbeddingExtractor(
        sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(EMBEDDING), num_threads=THREADS)
    )

    def embed(a: float, b: float) -> np.ndarray:
        stream = extractor.create_stream()
        stream.accept_waveform(SAMPLE_RATE, samples[int(a * SAMPLE_RATE) : int(b * SAMPLE_RATE)])
        stream.input_finished()
        v = np.array(extractor.compute(stream))
        return v / (np.linalg.norm(v) + 1e-9)

    prints, owner = [], []
    for i, (a, b) in enumerate(pieces):
        for wa, wb in _windows(a, b):
            prints.append(embed(wa, wb))
            owner.append(i)
    if progress:
        progress(0.95)
    if not prints:
        return [(a, b, 0) for a, b in pieces]
    X = np.array(prints)
    labels = spectral_clusters(X)
    votes = [Counter() for _ in pieces]
    for o, label in zip(owner, labels, strict=True):
        votes[o][int(label)] += 1
    centroids = np.array([X[labels == c].mean(0) for c in range(int(labels.max()) + 1)])
    turns: list[Turn] = []
    for i, (a, b) in enumerate(pieces):
        if votes[i]:
            turns.append((a, b, votes[i].most_common(1)[0][0]))
        elif b - a >= 0.3:  # too short for a window: the nearest voice
            turns.append((a, b, int(np.argmax(centroids @ embed(a, b)))))
    # Voices in order of first appearance: "Altri 1" is whoever speaks first.
    order: dict[int, int] = {}
    for _, _, v in turns:
        order.setdefault(v, len(order))
    if progress:
        progress(1.0)
    return [(a, b, order[v]) for a, b, v in turns]
