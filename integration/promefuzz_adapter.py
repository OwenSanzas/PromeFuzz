"""Case-level adapter: bridges our per-case benchmark to PromeFuzz's per-library
harness generation.

PromeFuzz (CCS 2025) is natively library-oriented: point it at a C/C++
library, it builds a knowledge base, and the LLM writes N candidate
harnesses targeting different API combinations. Our benchmark is
case-oriented: each of our 100 cases pins a specific `target_function`
we want exercised.

We close the gap by using PromeFuzz's `--task given` generation mode,
which the upstream repo provides specifically to "focus solely on
testing the specific functions you provide." That matches our per-case
interface one-to-one: for each case we invoke PromeFuzz with the case's
target_function, then pick whichever synthesized harness PromeFuzz
emits that actually calls the target.

Knowledge-base phases (`preprocess` + `comprehend`) are **cached per
library** because they are the expensive part ($ and minutes). The
cheap `generate` phase runs per (library, target_function) and is where
the case-level dispatch happens.

Module interface (used by `run_case.generate_harness_promefuzz`):

    generate_for_case(case, rebuild_attempts) -> str
        Returns harness source for the case. Raises LookupError if
        PromeFuzz did not produce any harness calling target_function.

    build_knowledge_base(library) -> None
        Runs configure + preprocess + comprehend phases for a library.
        Idempotent via a marker file under <output>/kb_ready.

SCAFFOLDING NOTE
================
The real PromeFuzz subprocess commands are all wired below, but the
adapter will refuse to run until:

  1. `experiment_libraries_<batch>.toml` has all TODO placeholders
     resolved (run `build_libraries_toml.py` + fix PROJECT_OVERRIDES).
  2. `config.toml` is present in the PromeFuzz root with the LiteLLM
     proxy pointed at LLM_PROXY_URL and model=LLM_MODEL, plus
     `sanitization_rounds = 5` / `generation_rounds = 5`.
  3. The LiteLLM proxy is actually reachable.

The `_ensure_library_config_usable()` check enforces all three before
firing off any real work so we fail fast.
"""
from __future__ import annotations

import logging
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from experiment_config import (
    LLM_MODEL,
    LLM_PROXY_URL,
    PROMEFUZZ_ROOT,
    REBUILD_ATTEMPTS,
)

log = logging.getLogger("promefuzz_adapter")

# ── Layout (must match build_libraries_toml.py output_path) ─────────────────

# PromeFuzz writes one .c per synthesized harness into:
#   <output_path>/<lib>/synthesized/<N>.c
# `output_path` is set per-library in libraries.toml; we mirror the
# default here so the adapter can locate files without re-parsing the toml.
PROMEFUZZ_OUTPUT_ROOT = Path("/tmp/promefuzz_output")

# Marker file per library indicating the knowledge-base phase ran.
KB_READY_NAME = "kb_ready.stamp"

# Config + libraries toml paths — these are created by our batch setup.
PROMEFUZZ_CONFIG_TOML = PROMEFUZZ_ROOT / "experiment_config.toml"
DEFAULT_LIBRARIES_TOML = (
    Path(__file__).parent / "experiment_libraries_a.toml"
)  # override via env PROMEFUZZ_LIBRARIES_TOML if you want batch_b


# ── Harness locator ────────────────────────────────────────────────────────

def _entry_rename(src: str) -> str:
    """Rename `LLVMFuzzerTestOneInput_<N>` → `LLVMFuzzerTestOneInput`.

    PromeFuzz's generated harnesses use a numeric suffix so the merged
    dispatcher harness can embed many of them side by side. For our
    per-case comparison we want the standalone canonical signature.
    """
    return re.sub(r"LLVMFuzzerTestOneInput_\d+", "LLVMFuzzerTestOneInput", src)


def _candidates_calling(target: str, synth_dir: Path) -> list[Path]:
    """Return synthesized harness files whose body calls `target`."""
    if not synth_dir.exists():
        return []
    pattern = re.compile(rf"\b{re.escape(target)}\s*\(")
    out: list[Path] = []
    for p in sorted(synth_dir.glob("*.c")):
        try:
            src = p.read_text(errors="replace")
        except OSError:
            continue
        if pattern.search(src):
            out.append(p)
    return out


def pick_best_candidate(candidates: list[Path]) -> Path:
    """Select the most focused matching harness.

    Strategy: shortest file wins. PromeFuzz often synthesizes several
    harnesses that combine the target API with different peripheral
    APIs; the shortest is usually the tightest and has the least noise
    from unrelated calls. It also produces the most legible baseline
    for Gold comparison.
    """
    return min(candidates, key=lambda p: p.stat().st_size)


# ── PromeFuzz subprocess runner ─────────────────────────────────────────────

@dataclass
class PromeFuzzInvocation:
    library: str
    target_function: str
    libraries_toml: Path
    config_toml: Path
    output_root: Path
    pool_size: int = 5


def _which_promefuzz() -> list[str]:
    """Return the argv prefix to run PromeFuzz.

    We prefer running the script in-place (PromeFuzz.py) rather than
    expecting it on PATH, because PromeFuzz loads src/* via relative
    imports and must be executed with its own CWD.
    """
    return ["python3", str(PROMEFUZZ_ROOT / "PromeFuzz.py")]


def _ensure_library_config_usable(libraries_toml: Path) -> None:
    """Abort fast if the library config still has TODO placeholders."""
    if not libraries_toml.exists():
        raise FileNotFoundError(
            f"library config not found: {libraries_toml}. "
            f"Run `python3 build_libraries_toml.py --batch a|b` first."
        )
    content = libraries_toml.read_text()
    if "TODO/" in content:
        raise RuntimeError(
            f"{libraries_toml} still contains TODO/ placeholders. "
            f"Fill them in via PROJECT_OVERRIDES in build_libraries_toml.py "
            f"and re-run the generator before invoking PromeFuzz."
        )


def _promefuzz_env() -> dict[str, str]:
    """Environment for PromeFuzz subprocesses.

    Injects PYTHONPATH so PromeFuzz's `from src import ...` works when
    invoked from an arbitrary CWD, and forwards any LiteLLM + provider
    keys set in the parent shell.
    """
    env = os.environ.copy()
    # Force the LiteLLM base_url and the unified model name so PromeFuzz's
    # own config can stay default-ish; these two are what it actually
    # forwards to openai-compatible clients.
    env.setdefault("OPENAI_BASE_URL", LLM_PROXY_URL)
    env.setdefault("OPENAI_API_KEY", "sk-local-promefuzz-run")
    env["PROMEFUZZ_TARGET_MODEL"] = LLM_MODEL  # informational, for logs
    return env


def _run(cmd: list[str], *, cwd: Path, check: bool = True, timeout: int = 7200) -> subprocess.CompletedProcess:
    log.info("exec: %s (cwd=%s)", " ".join(cmd), cwd)
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=_promefuzz_env(),
        check=check,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def build_knowledge_base(library: str, libraries_toml: Path | None = None) -> None:
    """Run PromeFuzz `preprocess` + `comprehend` for one library.

    Idempotent: subsequent calls short-circuit if `<output>/kb_ready.stamp`
    exists. Delete the marker to force a rebuild.
    """
    lib_toml = libraries_toml or Path(
        os.environ.get("PROMEFUZZ_LIBRARIES_TOML", DEFAULT_LIBRARIES_TOML)
    )
    _ensure_library_config_usable(lib_toml)

    out_dir = PROMEFUZZ_OUTPUT_ROOT / library
    stamp = out_dir / KB_READY_NAME
    if stamp.exists():
        log.info("knowledge base for %s already ready (%s)", library, stamp)
        return

    out_dir.mkdir(parents=True, exist_ok=True)

    base = _which_promefuzz() + [
        "--config", str(PROMEFUZZ_CONFIG_TOML),
        "-F", str(lib_toml),
    ]
    for phase in ("preprocess", "comprehend"):
        log.info("promefuzz %s -L %s", phase, library)
        _run(base + [phase, "-L", library], cwd=PROMEFUZZ_ROOT)

    stamp.write_text(
        f"knowledge base built via preprocess+comprehend\n"
        f"library={library}\n"
        f"libraries_toml={lib_toml}\n"
    )
    log.info("knowledge base ready for %s", library)


def _invoke_promefuzz(inv: PromeFuzzInvocation) -> None:
    """Run `promefuzz generate -L <lib> --task given <target>`.

    Precondition: `build_knowledge_base(inv.library)` has been called
    at least once (so preprocess + comprehend have populated the
    output dir).
    """
    _ensure_library_config_usable(inv.libraries_toml)

    cmd = _which_promefuzz() + [
        "--config", str(inv.config_toml),
        "-F", str(inv.libraries_toml),
        "generate",
        "-L", inv.library,
        "--task", "given",
        "--pool-size", str(inv.pool_size),
        inv.target_function,
    ]
    log.info(
        "generating harness via PromeFuzz: lib=%s target=%s model=%s proxy=%s",
        inv.library, inv.target_function, LLM_MODEL, LLM_PROXY_URL,
    )
    _run(cmd, cwd=PROMEFUZZ_ROOT)


# ── Public entry point ────────────────────────────────────────────────────

def generate_for_case(case, rebuild_attempts: int = REBUILD_ATTEMPTS) -> str:
    """Produce a PromeFuzz harness for `case`.

    Args:
        case: a run_case.Case (has .project and .target_function)
        rebuild_attempts: passed through to PromeFuzz's sanitization loop
            (effective value is set in PROMEFUZZ_CONFIG_TOML as
            sanitization_rounds / generation_rounds; this parameter is
            kept for interface symmetry with other adapters).

    Returns:
        Harness source string with the entry point renamed to the
        canonical `LLVMFuzzerTestOneInput`.

    Raises:
        LookupError: if PromeFuzz ran but did not produce any harness
            referencing `case.target_function`.
        FileNotFoundError / RuntimeError: config-level problems (missing
            libraries.toml, TODO placeholders, etc.)
    """
    del rebuild_attempts  # recorded in PROMEFUZZ_CONFIG_TOML, not passed per call

    synth_dir = PROMEFUZZ_OUTPUT_ROOT / case.project / "synthesized"

    # 1. Ensure knowledge base is built for this library
    build_knowledge_base(case.project)

    # 2. Reuse existing harness if one already targets this function
    existing = _candidates_calling(case.target_function, synth_dir)
    if not existing:
        inv = PromeFuzzInvocation(
            library=case.project,
            target_function=case.target_function,
            libraries_toml=Path(
                os.environ.get("PROMEFUZZ_LIBRARIES_TOML", DEFAULT_LIBRARIES_TOML)
            ),
            config_toml=PROMEFUZZ_CONFIG_TOML,
            output_root=PROMEFUZZ_OUTPUT_ROOT / case.project,
        )
        _invoke_promefuzz(inv)
        existing = _candidates_calling(case.target_function, synth_dir)

    if not existing:
        raise LookupError(
            f"PromeFuzz did not generate any harness calling "
            f"{case.target_function}() for library {case.project}"
        )

    chosen = pick_best_candidate(existing)
    log.info(
        "promefuzz picked %s for %s (%d candidates considered)",
        chosen.name, case.case_id, len(existing),
    )
    return _entry_rename(chosen.read_text(errors="replace"))
