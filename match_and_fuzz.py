#!/usr/bin/env python3
"""Match generated PromeFuzz drivers to benchmark cases and run fuzzing."""
import json, os, subprocess, sys, re, glob

PF = "/home/ze/agf/benchmark/oss_fuzz_harness/baselines/PromeFuzz"
EXPDIR = "/home/ze/agf/experiment/promefuzz_600s"
GOLD = "/home/ze/agf/benchmark/oss_fuzz_harness/data/benchmark_cases_gold_buildable.jsonl"
FUZZ_DURATION = 600

def load_cases():
    with open(GOLD) as f:
        return [json.loads(l) for l in f]

def find_best_driver(driver_dir, target_func):
    """Find the driver that best matches the target function."""
    best = None
    best_score = 0

    # Clean up target function for matching
    # Handle C++ namespaced functions: "jxl::ParseDescription" -> "ParseDescription"
    func_simple = target_func.split("::")[-1] if "::" in target_func else target_func
    # Handle special cases like "pt::read_info"
    func_parts = [target_func, func_simple]
    if "." in target_func:  # "glslang::TShader shader.parse" -> "parse"
        func_parts.append(target_func.split(".")[-1])

    for drv in sorted(glob.glob(os.path.join(driver_dir, "fuzz_driver_*.c")) +
                       glob.glob(os.path.join(driver_dir, "fuzz_driver_*.cpp"))):
        try:
            content = open(drv).read()
        except:
            continue

        score = 0
        for func in func_parts:
            score += content.count(func)

        if score > best_score:
            best_score = score
            best = drv

    return best, best_score

def run_fuzz(project, fuzzer_name, driver_src, duration=600):
    """Run fuzzing and coverage for a project/case."""
    outdir = os.path.join(EXPDIR, f"{project}__{fuzzer_name}")

    # Skip if already done
    status_file = os.path.join(outdir, "status.txt")
    if os.path.exists(status_file):
        with open(status_file) as f:
            status = f.read().strip()
        if status == "FUZZ_COMPLETE":
            print(f"  SKIP {project}/{fuzzer_name} - already done")
            return True

    print(f"  FUZZ {project}/{fuzzer_name} driver={driver_src}")

    result = subprocess.run(
        ["bash", os.path.join(PF, "run_fuzz_and_cov.sh"),
         project, fuzzer_name, driver_src, str(duration)],
        cwd=PF,
        capture_output=True,
        text=True,
        timeout=duration + 300
    )

    # Check if successful
    if os.path.exists(status_file):
        with open(status_file) as f:
            status = f.read().strip()
        if status == "FUZZ_COMPLETE":
            print(f"  OK {project}/{fuzzer_name}")
            return True

    print(f"  FAIL {project}/{fuzzer_name}")
    return False

def process_project(project, cases):
    """Process all cases for a project."""
    driver_dir = os.path.join(PF, f"database/{project}/latest/out/fuzz_driver")

    if not os.path.isdir(driver_dir):
        print(f"SKIP {project} - no fuzz_driver directory")
        return

    drivers = glob.glob(os.path.join(driver_dir, "fuzz_driver_*.c")) + \
              glob.glob(os.path.join(driver_dir, "fuzz_driver_*.cpp"))

    if not drivers:
        print(f"SKIP {project} - no drivers generated")
        return

    print(f"\n=== {project}: {len(drivers)} drivers, {len(cases)} cases ===")

    for case in cases:
        fuzzer_name = case["fuzzer_name"]
        target_func = case.get("target_function", "")

        outdir = os.path.join(EXPDIR, f"{project}__{fuzzer_name}")

        # Skip if already done
        status_file = os.path.join(outdir, "status.txt")
        if os.path.exists(status_file):
            with open(status_file) as f:
                status = f.read().strip()
            if status == "FUZZ_COMPLETE":
                print(f"  SKIP {fuzzer_name} - done")
                continue

        best, score = find_best_driver(driver_dir, target_func)

        if not best or score == 0:
            print(f"  NO_MATCH {fuzzer_name} ({target_func})")
            os.makedirs(outdir, exist_ok=True)
            with open(status_file, "w") as f:
                f.write("NO_MATCHING_DRIVER")
            continue

        print(f"  MATCH {fuzzer_name} -> {os.path.basename(best)} (score={score})")

        success = run_fuzz(project, fuzzer_name, best, FUZZ_DURATION)

        if not success:
            # Try alternative drivers
            for drv in sorted(drivers):
                if drv == best:
                    continue
                try:
                    content = open(drv).read()
                except:
                    continue

                func_simple = target_func.split("::")[-1] if "::" in target_func else target_func
                if func_simple in content:
                    print(f"  RETRY {fuzzer_name} -> {os.path.basename(drv)}")
                    # Remove failed status
                    if os.path.exists(status_file):
                        os.remove(status_file)
                    success = run_fuzz(project, fuzzer_name, drv, FUZZ_DURATION)
                    if success:
                        break

if __name__ == "__main__":
    projects = sys.argv[1:] if len(sys.argv) > 1 else None

    cases = load_cases()
    from collections import defaultdict
    by_proj = defaultdict(list)
    for c in cases:
        by_proj[c["project"]].append(c)

    if projects:
        for p in projects:
            if p in by_proj:
                process_project(p, by_proj[p])
    else:
        for p in sorted(by_proj.keys()):
            process_project(p, by_proj[p])
