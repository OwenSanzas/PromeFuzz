#!/usr/bin/env python3
"""
Normalize coverage measurement for all PromeFuzz cases.
Both Gold and PF harnesses are compiled against the SAME PF-built library
and measured with the same llvm-cov pipeline.
"""

import json
import os
import subprocess
import sys
import re
import tempfile
import shutil
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import os
_PF = os.environ.get("PROMEFUZZ_DIR") or os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(_PF, "database")
WORKDIR = _PF
PF_EXP = os.environ.get("PROMEFUZZ_EXPERIMENT_DIR", os.path.join(_PF, "experiment", "promefuzz_600s"))
GOLD_EXP = os.environ.get("GOLD_EXPERIMENT_DIR", os.path.join(_PF, "experiment", "gold_only_600s"))
JSONL = os.environ.get("BENCHMARK_CASES") or os.path.join(_PF, "benchmark_cases.jsonl")
_REPORT_DIR = os.environ.get("PROMEFUZZ_REPORT_DIR", _PF)

# Special project->database mapping
PROJECT_DB_MAP = {
    "iperf": "cjson",
    # Add other mappings if needed
}

# Extra include paths per project (for gold harnesses that include project-specific fuzz helpers)
EXTRA_INCLUDE_PATHS = {
    "ndpi": [
        "-Idatabase/ndpi/latest/code/fuzz",
    ],
    "harfbuzz": [
        "-Idatabase/harfbuzz/latest/code/test/fuzzing",
        "-Idatabase/harfbuzz/latest/code/src",
    ],
    "openssl": [
        "-Idatabase/openssl/latest/code/fuzz",
    ],
    "libxslt": [
        "-Idatabase/libxslt/latest/code/tests/fuzz",
    ],
    "openssh": [
        "-Idatabase/openssh/latest/code/regress/misc/fuzz-harness",
    ],
    "binutils": [
        "-Idatabase/binutils/latest/code/opcodes",
        "-Idatabase/binutils/latest/code/gas",
    ],
    "draco": [
        "-Idatabase/draco/latest/code",  # Gold includes "draco/src/draco/..."
    ],
    "quickjs": [
        "-Idatabase/quickjs/latest/code",
    ],
    "brotli": [
        "-Idatabase/brotli/latest/code/c/include/brotli",
    ],
    "mbedtls": [
        "-Idatabase/mbedtls/latest/bin_cov/include",
    ],
    "curl": [
        "-Idatabase/curl/latest/code/tests/fuzz",  # for curl_fuzzer.h
    ],
    "libcoap": [
        "-Idatabase/libcoap/latest/code/include/coap3",
        "-Idatabase/libcoap/latest/code/include",
        "-Idatabase/libcoap/latest/build_cov/include",
        "-Idatabase/libcoap/latest/bin_cov/include/coap3",
    ],
    "libical": [
        "-Idatabase/libical/latest/bin_cov/include",
        "-Idatabase/libical/latest/bin_cov/include/libical",
    ],
}

# Extra source files needed to compile gold harnesses (project-specific fuzz helpers)
EXTRA_SOURCES = {
    "ndpi": [
        "database/ndpi/latest/code/fuzz/fuzz_common_code.c",
    ],
    "openssl": [
        "database/openssl/latest/code/fuzz/driver.c",
        "database/openssl/latest/code/fuzz/fuzz_rand.c",
    ],
    "quickjs": [
        "database/quickjs/latest/code/fuzz/fuzz_common.c",
        "database/quickjs/latest/code/quickjs-libc.c",
        "database/quickjs/latest/code/cutils.c",
    ],
    "libxslt": [
        "database/libxslt/latest/code/tests/fuzz/fuzz.c",
    ],
}

# Extra libs per project (beyond driver_build_args) - these are .a files to add
EXTRA_LIBS = {
    "glslang": [
        "database/glslang/latest/build_cov/glslang/libglslang-default-resource-limits.a",
    ],
}

# Extra link flags per project (beyond driver_build_args)
EXTRA_LINK_FLAGS = {
    "openssl": ["-lpthread", "-ldl"],
    "glslang": ["-lstdc++", "-lpthread", "-lm"],
    "pjsip": ["-luuid", "-lssl", "-lcrypto"],
    "openssh": ["-lcrypto", "-lz"],
}

# Projects where opencv lib names differ between build modes
OPENCV_LIB_FIXUP = True  # flag to enable opencv fixup


def parse_toml_simple(path):
    """Parse a simple TOML file without external library."""
    result = {}
    current_section = None
    multiline_key = None
    multiline_val = ""

    with open(path) as f:
        for line in f:
            stripped = line.strip()

            # Continue multiline array
            if multiline_key is not None:
                multiline_val += line
                if "]" in stripped:
                    # Parse the accumulated value
                    try:
                        result[current_section][multiline_key] = json.loads(
                            multiline_val.strip().rstrip(",")
                        )
                    except json.JSONDecodeError:
                        # Try fixing common TOML-isms
                        val = multiline_val.strip().rstrip(",")
                        # Remove trailing commas before ]
                        val = re.sub(r",\s*\]", "]", val)
                        try:
                            result[current_section][multiline_key] = json.loads(val)
                        except:
                            result[current_section][multiline_key] = []
                    multiline_key = None
                    multiline_val = ""
                continue

            if not stripped or stripped.startswith("#"):
                continue

            if stripped.startswith("[") and not stripped.startswith("[["):
                current_section = stripped.strip("[]").strip()
                if current_section not in result:
                    result[current_section] = {}
                continue

            if "=" in stripped and current_section:
                key, _, val = stripped.partition("=")
                key = key.strip()
                val = val.strip()

                if val.startswith("[") and "]" not in val:
                    # Multiline array
                    multiline_key = key
                    multiline_val = val + "\n"
                    continue

                # Try to parse as JSON
                try:
                    result[current_section][key] = json.loads(val)
                except:
                    # Remove surrounding quotes
                    if val.startswith('"') and val.endswith('"'):
                        result[current_section][key] = val[1:-1]
                    else:
                        result[current_section][key] = val

    return result


def get_project_config(project):
    """Get build configuration for a project."""
    db_project = PROJECT_DB_MAP.get(project, project)
    toml_path = os.path.join(DB, db_project, "latest", "lib.toml")
    if not os.path.exists(toml_path):
        return None

    config = parse_toml_simple(toml_path)
    # Get the first (only) section
    section = list(config.values())[0] if config else {}
    section["_db_project"] = db_project
    return section


def get_cov_build_args(config):
    """Convert asan build args to cov build args."""
    args = config.get("driver_build_args", [])
    if not isinstance(args, list):
        return []

    cov_args = []
    for arg in args:
        # Replace bin_asan -> bin_cov, build_asan -> build_cov
        arg = arg.replace("bin_asan", "bin_cov").replace("build_asan", "build_cov")
        cov_args.append(arg)
    return cov_args


def get_include_args(config):
    """Get include path args from header_paths."""
    headers = config.get("header_paths", [])
    if not isinstance(headers, list):
        return []

    include_dirs = set()
    for h in headers:
        # Get directory of header file
        d = os.path.dirname(h)
        if d:
            include_dirs.add(f"-I{d}")
    return list(include_dirs)


def compile_harness(source_path, output_path, config, is_gold=False, project=None):
    """Compile a harness with coverage instrumentation against cov library."""
    lang = config.get("language", "c++")
    compiler = "clang++" if lang == "c++" else "clang"

    # Check source extension to override
    if source_path.endswith(".cpp") or source_path.endswith(".cc"):
        compiler = "clang++"
    elif source_path.endswith(".c"):
        compiler = "clang"

    build_args = get_cov_build_args(config)
    include_args = get_include_args(config)

    # Fix opencv missing libzlib.a - it doesn't exist in either asan or cov
    fixed_build_args = []
    for arg in build_args:
        # Skip nonexistent .a files
        if arg.endswith(".a") and not arg.startswith("-"):
            full = os.path.join(WORKDIR, arg) if not os.path.isabs(arg) else arg
            if not os.path.exists(full):
                continue
        fixed_build_args.append(arg)
    build_args = fixed_build_args

    cmd = [
        compiler,
        source_path,
    ]

    # Add extra source files for gold harnesses (project-specific fuzz helpers)
    proj_key = project or config.get("_db_project", "")
    if is_gold and proj_key in EXTRA_SOURCES:
        for src in EXTRA_SOURCES[proj_key]:
            full_src = os.path.join(WORKDIR, src)
            if os.path.exists(full_src):
                cmd.append(full_src)

    cmd.extend([
        "-o", output_path,
        "-fprofile-instr-generate",
        "-fcoverage-mapping",
        "-fsanitize=fuzzer",
        "-g",
        "-w",  # Suppress warnings
    ])
    cmd.extend(include_args)

    # Add extra include paths
    if proj_key in EXTRA_INCLUDE_PATHS:
        cmd.extend(EXTRA_INCLUDE_PATHS[proj_key])

    cmd.extend(build_args)

    # Add extra libs
    if proj_key in EXTRA_LIBS:
        for lib in EXTRA_LIBS[proj_key]:
            full_lib = os.path.join(WORKDIR, lib) if not os.path.isabs(lib) else lib
            if os.path.exists(full_lib):
                cmd.append(lib)

    # Add extra link flags
    if proj_key in EXTRA_LINK_FLAGS:
        cmd.extend(EXTRA_LINK_FLAGS[proj_key])

    try:
        result = subprocess.run(
            cmd,
            cwd=WORKDIR,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return result.returncode == 0, " ".join(cmd), result.stderr
    except Exception as e:
        return False, " ".join(cmd), str(e)


def replay_corpus(binary_path, corpus_dir, profraw_path):
    """Replay corpus through a coverage binary."""
    if not os.path.isdir(corpus_dir):
        return False, "Corpus dir not found"

    corpus_files = os.listdir(corpus_dir)
    if not corpus_files:
        return False, "Corpus is empty"

    env = os.environ.copy()
    env["LLVM_PROFILE_FILE"] = profraw_path

    try:
        result = subprocess.run(
            [binary_path, corpus_dir, "-runs=0"],
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )
        return os.path.exists(profraw_path), result.stderr
    except subprocess.TimeoutExpired:
        # Timeout is OK if profraw was generated
        return os.path.exists(profraw_path), "TIMEOUT but profraw may exist"
    except Exception as e:
        return False, str(e)


def get_coverage(binary_path, profraw_path, profdata_path):
    """Get coverage from profraw using llvm-profdata + llvm-cov."""
    # Merge profile data
    try:
        subprocess.run(
            ["llvm-profdata", "merge", "-sparse", profraw_path, "-o", profdata_path],
            capture_output=True,
            timeout=60,
        )
    except Exception as e:
        return None, f"profdata merge failed: {e}"

    if not os.path.exists(profdata_path):
        return None, "profdata not created"

    # Export coverage
    try:
        result = subprocess.run(
            [
                "llvm-cov", "export", binary_path,
                f"-instr-profile={profdata_path}",
                "--format=text",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            return None, f"llvm-cov export failed: {result.stderr}"

        data = json.loads(result.stdout)
        totals = data["data"][0]["totals"]["lines"]
        return {
            "covered": totals["covered"],
            "count": totals["count"],
            "percent": totals["percent"],
        }, None
    except Exception as e:
        return None, f"coverage export failed: {e}"


def process_case(case_info, gold_source_code):
    """Process a single case: build both harnesses, replay, measure."""
    case_id = case_info["case_id"]
    project = case_info["project"]
    case_dir_name = case_id.replace("/", "__")
    source_file = case_info["source_file"]

    pf_case_dir = os.path.join(PF_EXP, case_dir_name)
    gold_case_dir_pattern = os.path.join(GOLD_EXP, case_dir_name, "gold-*")

    result = {
        "case_id": case_id,
        "project": project,
        "status": "UNKNOWN",
    }

    # Get project config
    config = get_project_config(project)
    if config is None:
        result["status"] = "NO_CONFIG"
        return result

    # Create temp dir for this case
    norm_dir = os.path.join(pf_case_dir, "normalized")
    os.makedirs(norm_dir, exist_ok=True)

    # --- PF Harness ---
    pf_harness_cpp = os.path.join(pf_case_dir, "harness.cpp")
    pf_harness_c = os.path.join(pf_case_dir, "harness.c")
    if os.path.exists(pf_harness_cpp):
        pf_harness = pf_harness_cpp
    elif os.path.exists(pf_harness_c):
        pf_harness = pf_harness_c
    else:
        result["status"] = "PF_FAILED"
        return result

    pf_corpus = os.path.join(pf_case_dir, "corpus")

    # --- Gold Harness ---
    # Determine gold harness extension
    if source_file.endswith(".cc") or source_file.endswith(".cpp"):
        gold_ext = ".cpp" if source_file.endswith(".cpp") else ".cc"
    elif source_file.endswith(".c"):
        gold_ext = ".c"
    else:
        # Default based on language
        lang = config.get("language", "c++")
        gold_ext = ".cpp" if lang == "c++" else ".c"

    gold_harness_path = os.path.join(norm_dir, f"gold_harness{gold_ext}")
    with open(gold_harness_path, "w") as f:
        f.write(gold_source_code)

    # Find gold corpus
    import glob
    gold_corpus_dirs = glob.glob(os.path.join(GOLD_EXP, case_dir_name, "gold-*", "corpus"))
    if not gold_corpus_dirs:
        # Try without the gold-* subdirectory
        gold_corpus_candidate = os.path.join(GOLD_EXP, case_dir_name, "corpus")
        if os.path.isdir(gold_corpus_candidate):
            gold_corpus_dirs = [gold_corpus_candidate]

    gold_corpus = gold_corpus_dirs[0] if gold_corpus_dirs else None

    # --- Compile PF harness ---
    pf_binary = os.path.join(norm_dir, "pf_cov_binary")
    pf_ok, pf_cmd, pf_err = compile_harness(pf_harness, pf_binary, config, is_gold=False, project=project)

    if not pf_ok:
        result["status"] = "PF_COV_BUILD_FAILED"
        result["pf_compile_cmd"] = pf_cmd
        result["pf_compile_err"] = pf_err[:500]
        # Still try gold

    # --- Compile Gold harness ---
    gold_binary = os.path.join(norm_dir, "gold_cov_binary")
    gold_ok, gold_cmd, gold_err = compile_harness(gold_harness_path, gold_binary, config, is_gold=True, project=project)

    if not gold_ok:
        result["status"] = "GOLD_COV_BUILD_FAILED" if pf_ok else "BOTH_COV_BUILD_FAILED"
        result["gold_compile_cmd"] = gold_cmd
        result["gold_compile_err"] = gold_err[:500]
        if not pf_ok:
            return result

    # --- Replay and measure PF ---
    pf_cov = None
    if pf_ok and os.path.isdir(pf_corpus):
        pf_profraw = os.path.join(norm_dir, "pf.profraw")
        pf_profdata = os.path.join(norm_dir, "pf.profdata")
        replay_ok, replay_msg = replay_corpus(pf_binary, pf_corpus, pf_profraw)
        if replay_ok:
            pf_cov, cov_err = get_coverage(pf_binary, pf_profraw, pf_profdata)
            if pf_cov is None:
                result["pf_cov_error"] = cov_err

    # --- Replay and measure Gold ---
    gold_cov = None
    if gold_ok and gold_corpus:
        gold_profraw = os.path.join(norm_dir, "gold.profraw")
        gold_profdata = os.path.join(norm_dir, "gold.profdata")
        replay_ok, replay_msg = replay_corpus(gold_binary, gold_corpus, gold_profraw)
        if replay_ok:
            gold_cov, cov_err = get_coverage(gold_binary, gold_profraw, gold_profdata)
            if gold_cov is None:
                result["gold_cov_error"] = cov_err
    elif gold_ok and not gold_corpus:
        result["gold_corpus_missing"] = True

    # --- Assemble result ---
    if pf_cov and gold_cov:
        result["status"] = "OK"
        result["gold_lines_pct"] = round(gold_cov["percent"], 2)
        result["gold_lines_covered"] = gold_cov["covered"]
        result["gold_lines_total"] = gold_cov["count"]
        result["pf_lines_pct"] = round(pf_cov["percent"], 2)
        result["pf_lines_covered"] = pf_cov["covered"]
        result["pf_lines_total"] = pf_cov["count"]
        result["same_library"] = True
    elif pf_cov and not gold_cov:
        result["status"] = "GOLD_MEASURE_FAILED" if gold_ok else result.get("status", "GOLD_COV_BUILD_FAILED")
        result["pf_lines_pct"] = round(pf_cov["percent"], 2)
        result["pf_lines_covered"] = pf_cov["covered"]
        result["pf_lines_total"] = pf_cov["count"]
        result["same_library"] = False
    elif gold_cov and not pf_cov:
        result["status"] = "PF_MEASURE_FAILED" if pf_ok else result.get("status", "PF_COV_BUILD_FAILED")
        result["gold_lines_pct"] = round(gold_cov["percent"], 2)
        result["gold_lines_covered"] = gold_cov["covered"]
        result["gold_lines_total"] = gold_cov["count"]
        result["same_library"] = False
    else:
        if result["status"] == "UNKNOWN":
            result["status"] = "BOTH_MEASURE_FAILED"
        result["same_library"] = False

    return result


def process_case_wrapper(args):
    """Wrapper for process pool."""
    case_info, gold_source = args
    case_id = case_info["case_id"]
    try:
        result = process_case(case_info, gold_source)
        print(f"[{'OK' if result['status'] == 'OK' else result['status']}] {case_id}", flush=True)
        return result
    except Exception as e:
        print(f"[ERROR] {case_id}: {e}", flush=True)
        return {
            "case_id": case_id,
            "project": case_info["project"],
            "status": f"EXCEPTION: {str(e)[:200]}",
            "same_library": False,
        }


def generate_report(results, output_path):
    """Generate the final comparison report."""
    ok_results = [r for r in results if r["status"] == "OK"]
    failed_results = [r for r in results if r["status"] != "OK"]

    # Count wins
    pf_wins = sum(1 for r in ok_results if r["pf_lines_pct"] > r["gold_lines_pct"])
    gold_wins = sum(1 for r in ok_results if r["gold_lines_pct"] > r["pf_lines_pct"])
    ties = sum(1 for r in ok_results if r["pf_lines_pct"] == r["gold_lines_pct"])

    avg_pf = sum(r["pf_lines_pct"] for r in ok_results) / len(ok_results) if ok_results else 0
    avg_gold = sum(r["gold_lines_pct"] for r in ok_results) / len(ok_results) if ok_results else 0

    # Group by project
    by_project = {}
    for r in ok_results:
        proj = r["project"]
        if proj not in by_project:
            by_project[proj] = []
        by_project[proj].append(r)

    lines = []
    lines.append("# PromeFuzz vs Gold: Normalized Coverage Comparison")
    lines.append("")
    lines.append("## Methodology")
    lines.append("Both Gold (OSS-Fuzz) and PromeFuzz harnesses are compiled against the **same**")
    lines.append("PromeFuzz-built coverage library (`bin_cov`/`build_cov`) and measured with the")
    lines.append("same `llvm-profdata` + `llvm-cov export` pipeline. This eliminates library-version")
    lines.append("differences that previously made coverage numbers incomparable.")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- **Cases measured**: {len(ok_results)} / {len(results)}")
    lines.append(f"- **PF wins**: {pf_wins} ({pf_wins/len(ok_results)*100:.1f}%)" if ok_results else "- **PF wins**: 0")
    lines.append(f"- **Gold wins**: {gold_wins} ({gold_wins/len(ok_results)*100:.1f}%)" if ok_results else "- **Gold wins**: 0")
    lines.append(f"- **Ties**: {ties}" if ok_results else "- **Ties**: 0")
    lines.append(f"- **Avg PF coverage**: {avg_pf:.2f}%")
    lines.append(f"- **Avg Gold coverage**: {avg_gold:.2f}%")
    lines.append("")

    lines.append("## Per-Case Results")
    lines.append("")
    lines.append("| Case | Gold % | Gold Lines | PF % | PF Lines | Total | Winner |")
    lines.append("|------|--------|-----------|------|---------|-------|--------|")

    for r in sorted(ok_results, key=lambda x: x["case_id"]):
        winner = "PF" if r["pf_lines_pct"] > r["gold_lines_pct"] else ("Gold" if r["gold_lines_pct"] > r["pf_lines_pct"] else "Tie")
        lines.append(
            f"| {r['case_id']} | {r['gold_lines_pct']:.2f} | {r['gold_lines_covered']} | "
            f"{r['pf_lines_pct']:.2f} | {r['pf_lines_covered']} | {r['pf_lines_total']} | {winner} |"
        )

    lines.append("")
    lines.append("## Per-Project Summary")
    lines.append("")
    lines.append("| Project | Cases | Avg Gold % | Avg PF % | PF Wins | Gold Wins |")
    lines.append("|---------|-------|-----------|---------|---------|-----------|")

    for proj in sorted(by_project.keys()):
        cases = by_project[proj]
        n = len(cases)
        ag = sum(c["gold_lines_pct"] for c in cases) / n
        ap = sum(c["pf_lines_pct"] for c in cases) / n
        pw = sum(1 for c in cases if c["pf_lines_pct"] > c["gold_lines_pct"])
        gw = sum(1 for c in cases if c["gold_lines_pct"] > c["pf_lines_pct"])
        lines.append(f"| {proj} | {n} | {ag:.2f} | {ap:.2f} | {pw} | {gw} |")

    if failed_results:
        lines.append("")
        lines.append("## Failed Cases")
        lines.append("")
        lines.append("| Case | Status |")
        lines.append("|------|--------|")
        for r in sorted(failed_results, key=lambda x: x["case_id"]):
            status = r["status"]
            extra = ""
            if "gold_compile_err" in r:
                extra = f" - {r['gold_compile_err'][:80]}"
            elif "pf_compile_err" in r:
                extra = f" - {r['pf_compile_err'][:80]}"
            lines.append(f"| {r['case_id']} | {status}{extra} |")

    report = "\n".join(lines) + "\n"
    with open(output_path, "w") as f:
        f.write(report)
    return report


def main():
    # Load all cases
    with open(JSONL) as f:
        all_cases = [json.loads(line) for line in f]

    print(f"Total cases in JSONL: {len(all_cases)}")

    # Filter to cases that have PF harnesses
    work_items = []
    skipped = []
    for case in all_cases:
        case_id = case["case_id"]
        case_dir = case_id.replace("/", "__")
        pf_dir = os.path.join(PF_EXP, case_dir)

        has_pf = (
            os.path.exists(os.path.join(pf_dir, "harness.c"))
            or os.path.exists(os.path.join(pf_dir, "harness.cpp"))
        )

        if not has_pf:
            skipped.append(case_id)
            continue

        work_items.append((case, case["source_code"]))

    print(f"Cases with PF harness: {len(work_items)}")
    print(f"Skipped (PF_FAILED): {len(skipped)}")

    # Process in parallel (8 at a time)
    results = []
    with ProcessPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(process_case_wrapper, item): item[0]["case_id"]
            for item in work_items
        }
        for future in as_completed(futures):
            case_id = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                print(f"[FATAL] {case_id}: {e}")
                results.append({
                    "case_id": case_id,
                    "status": f"FATAL: {e}",
                    "same_library": False,
                })

    # Add PF_FAILED cases to results
    for case_id in skipped:
        results.append({
            "case_id": case_id,
            "status": "PF_FAILED",
            "same_library": False,
        })

    # Save individual normalized_coverage.json files
    for r in results:
        if r["status"] == "OK":
            case_dir = r["case_id"].replace("/", "__")
            out_path = os.path.join(PF_EXP, case_dir, "normalized_coverage.json")
            out_data = {
                "gold_lines_pct": r["gold_lines_pct"],
                "gold_lines_covered": r["gold_lines_covered"],
                "gold_lines_total": r["gold_lines_total"],
                "pf_lines_pct": r["pf_lines_pct"],
                "pf_lines_covered": r["pf_lines_covered"],
                "pf_lines_total": r["pf_lines_total"],
                "same_library": True,
            }
            with open(out_path, "w") as f:
                json.dump(out_data, f, indent=2)

    # Generate report
    report_path = os.path.join(_REPORT_DIR, "promefuzz_vs_gold_final.md")
    report = generate_report(results, report_path)

    # Also save complete results JSON
    all_results_path = os.path.join(PF_EXP, "normalized_results_all.json")
    with open(all_results_path, "w") as f:
        json.dump(results, f, indent=2)

    # Print summary
    ok = [r for r in results if r["status"] == "OK"]
    print(f"\n{'='*60}")
    print(f"DONE: {len(ok)} OK, {len(results) - len(ok)} failed/skipped")
    if ok:
        pf_wins = sum(1 for r in ok if r["pf_lines_pct"] > r["gold_lines_pct"])
        gold_wins = sum(1 for r in ok if r["gold_lines_pct"] > r["pf_lines_pct"])
        print(f"PF wins: {pf_wins}, Gold wins: {gold_wins}, Ties: {len(ok) - pf_wins - gold_wins}")
    print(f"Report: {report_path}")
    print(f"All results: {all_results_path}")


if __name__ == "__main__":
    main()
