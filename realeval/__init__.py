"""realeval — Real Computation Library (v4.2)

QAD-MultiGuard H100 real evaluation suite.
Restructured for paper-grade experiment authenticity.

Modules: real_backend, metrics, statistics, audit, benchmark, runner, report, data,
         models, privacy, specdec, gguf_backend, paths, io, validation, limits, runlog
"""

__version__ = "4.2.0"

__all__ = [
    "__version__",
    # Core: always available
    "statistics", "metrics", "benchmark", "runner", "report",
    # Data & models
    "data", "models", "paths",
    # Hardware & deployment
    "hwenv", "real_backend", "gguf_backend",
    # Safety & reproducibility
    "audit", "runlog", "envreport", "io", "validation", "limits",
    # Specialized
    "privacy", "specdec",
]

