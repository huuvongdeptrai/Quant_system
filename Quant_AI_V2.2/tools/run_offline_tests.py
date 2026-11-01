"""Run the offline suite with one Qt application lifetime per test module.

Usage: python tools/run_offline_tests.py --output verification
Install requirements-dev.txt first. This never connects to a live MT5 terminal.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="verification")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ, QT_QPA_PLATFORM="offscreen",
                       VECTRA_OFFLINE_TESTS="1", QUANT_TESTING="1")
    results = []
    for module in sorted((root / "tests").glob("test_*.py")):
        start = time.monotonic()
        xml_path = output / (module.stem + ".xml")
        xml_path.unlink(missing_ok=True)
        command = [sys.executable, "-m", "pytest", str(module), "-q",
                   "--timeout=25", "--tb=short", "--junitxml=" + str(xml_path)]
        with (output / (module.stem + ".log")).open("w") as log:
            try:
                code = subprocess.run(command, cwd=root, env=environment,
                                      stdout=log, stderr=subprocess.STDOUT,
                                      timeout=90).returncode
            except subprocess.TimeoutExpired:
                code = 124
        result = {"module": module.name, "exit_code": code,
                  "seconds": round(time.monotonic() - start, 3)}
        if xml_path.exists():
            suites = ET.parse(xml_path).getroot().iter("testsuite")
            for key in ("tests", "failures", "errors", "skipped"):
                result[key] = sum(int(s.attrib.get(key, 0)) for s in suites)
                suites = ET.parse(xml_path).getroot().iter("testsuite")
            result["passed"] = (result["tests"] - result["failures"] -
                                result["errors"] - result["skipped"])
        results.append(result)
        (output / "results.json").write_text(json.dumps(results, indent=2))
        print(f"{module.name}: exit={code}", flush=True)
    summary = {key: sum(r.get(key, 0) for r in results)
               for key in ("tests", "passed", "failures", "errors", "skipped")}
    summary["modules"] = len(results)
    summary["failed_processes"] = sum(r["exit_code"] != 0 for r in results)
    (output / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return int(summary["failed_processes"] > 0)


if __name__ == "__main__":
    raise SystemExit(main())
