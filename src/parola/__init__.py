"""P.A.R.O.L.A.: local, verbatim transcription of Italian and English audio and calls."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("parola")
except PackageNotFoundError:  # running from a source tree without install
    __version__ = "0.0.0"
