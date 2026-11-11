"""Capture (--capture) or verify Stage1 evidence using the real CLI, stdlib only."""

import argparse
import csv
from datetime import datetime
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "evidence/stage_1"
MANIFEST = ROOT / "evidence/manifest.csv"
CAPTURE = STAGE / "capture.json"
CASES = (
    ("known", 0, None, 5, 25),
    ("We've succeeded!", 0, None, 16, 25),
    ("~¡256_-_aA&ñ", 0, None, 12, 25),
    ("From α to ɷ...", 1, "UNSUPPORTED_CHARACTER", None, 0),
    ("Sugarplum_Fairy_Nightmare", 1, "CAPACITY_EXCEEDED", 25, 1),
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources():
    paths = ([ROOT / "main_cli.py", ROOT / "requirements.txt"]
             + sorted((ROOT / "qr_app").rglob("*.py"))
             + sorted((ROOT / "qr_app/resources").glob("*.json"))
             + sorted((ROOT / "tests").rglob("*.py"))
             + sorted((ROOT / "tests/fixtures").glob("*.json")))
    return {path.relative_to(ROOT).as_posix(): digest(path) for path in paths}


def run(args, data=None):
    result = subprocess.run(args, input=data, cwd=ROOT, capture_output=True, timeout=120)
    return {"command": args, "exit_code": result.returncode,
            "stdout": result.stdout.decode("utf-8"), "stderr": result.stderr.decode("utf-8")}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, encoding="utf-8").strip()


def field(text, label):
    values = [line[len(label) + 2:] for line in text.splitlines() if line.startswith(label + ": ")]
    require(len(values) == 1, "Missing or duplicate field: " + label)
    return values[0]


def inspect_demo(path, case):
    text, expected_exit, error, length, steps = case
    raw = path.read_bytes()
    report = raw.decode("utf-8")
    require(raw.endswith(b"\n") and b"\r" not in raw, "Report must use UTF-8/LF")
    require(json.loads(field(report, "Input (JSON)")) == text, "Input was changed")
    require(field(report, "Source") == "cli" and field(report, "Mode") == "baseline", "Wrong mode")
    require(json.loads(field(report, "Requested settings")) == {
        "version": 1, "ecc_level": "L", "mask_id": 0, "options": {}, "capture_steps": True},
        "Unexpected request settings")
    require(field(report, "Generation") == ("SUCCESS" if expected_exit == 0 else "FAILED"), "Wrong result")
    require(json.loads(field(report, "Byte length")) == length, "Wrong byte count")
    require(int(field(report, "Captured steps")) == steps, "Wrong step count")
    recorded = re.findall(r"^\[(\d+)\] ([^\n]+)$", report, re.MULTILINE)
    require([int(number) for number, _ in recorded] == list(range(1, steps + 1)), "Step order/count mismatch")
    require(len({name for _, name in recorded}) == steps, "Duplicate steps")
    request_id = field(report, "Request ID")
    UUID(request_id)
    timestamp = field(report, "Timestamp")
    require(datetime.fromisoformat(timestamp).utcoffset() is not None, "Missing timezone")
    if error:
        require(field(report, "Error code") == error, "Wrong error code")
        for label in ("Actual plan", "Actual mask", "Final matrix"):
            require(field(report, label) == "null", "Invented failure result")
        require([name for _, name in recorded] == (["input.iso_8859_1"] if steps else []), "Invented failure steps")
        rows = None
    else:
        plan = json.loads(field(report, "Actual plan"))
        require((plan["version"], plan["ecc_level"], plan["data_codewords"],
                 plan["ecc_codewords_per_block"], plan["total_codewords"]) == (1, "L", 19, 7, 26), "Wrong plan")
        require(field(report, "Actual mask") == "0", "Wrong mask")
        require("Bits (15): 111011111000100\n" in report, "Wrong format bits")
        require(recorded[-1][1] == "mask0.final_matrix", "Missing final snapshot")
        header = "Final matrix: dtype=uint8, shape=(21, 21), 0=white, 1=black, no quiet zone\n"
        require(header in report, "Missing final matrix header")
        rows = report.split(header, 1)[1].splitlines()[:21]
        require(len(rows) == 21 and all(re.fullmatch(r"[01]( [01]){20}", row) for row in rows), "Invalid final matrix")
        if text == "known":
            reference = json.loads((ROOT / "tests/fixtures/format_mask0_reference_vectors.json").read_text(encoding="utf-8"))
            vector = next(item for item in reference["known_mask0_matrices"]
                          if (item["version"], item["ecc_level"]) == (1, "L"))
            require([row.replace(" ", "") for row in rows] == vector["final_matrix_rows"], "Reference matrix mismatch")
    return {"request_id": request_id, "timestamp": timestamp, "steps": [name for _, name in recorded],
            "result": error or "SUCCESS", "byte_length": length, "final_matrix_rows": rows}


def capture():
    require(sys.version_info[:3] == (3, 13, 9), "Capture requires Python 3.13.9")
    targets = [STAGE / f"demo_{index}.txt" for index in range(1, 6)] + [CAPTURE, MANIFEST]
    require(not any(path.exists() for path in targets), "Evidence already exists; archive it before a new capture")
    # The application and tests must match the named commit. New evidence/tool/docs are separate.
    require(not git("status", "--porcelain", "--", "main_cli.py", "qr_app", "requirements.txt", "tests"),
            "Commit application/test changes before capturing formal evidence")
    before = sources()
    record = {"schema_version": "1.0", "captured_at": datetime.now().astimezone().isoformat(),
              "operator": "automated_local_capture",
              "code_commit": git("rev-parse", "HEAD"), "branch": git("branch", "--show-current"),
              "source_dirty": False, "working_tree_dirty": bool(git("status", "--porcelain")),
              "source_dirty_scope": "main_cli.py, qr_app/, requirements.txt, tests/",
              "environment": {"python": platform.python_version(), "executable": sys.executable,
                              "platform": platform.platform(), "numpy": version("numpy"), "reedsolo": version("reedsolo")},
              "interface_version": "1.0", "rule_version": "input_rules_v1", "related_ci": None,
              "capture_tool_sha256": digest(Path(__file__)), "source_sha256": before, "cases": []}
    STAGE.mkdir(parents=True, exist_ok=True)
    for index, case in enumerate(CASES, 1):
        path = STAGE / f"demo_{index}.txt"
        actual = run([sys.executable, str(ROOT / "main_cli.py"), "--text", case[0], "--steps-out", str(path)])
        require(actual["exit_code"] == case[1], f"Unexpected exit for demo_{index}")
        if case[2]:
            require(case[2] in actual["stderr"], "Missing CLI error")
        observed = inspect_demo(path, case)
        record["cases"].append({"case_id": f"S1-{index:02d}", "artifact_path": path.relative_to(ROOT).as_posix(),
            "input": case[0], "expected_exit": case[1], "expected_error": case[2],
            "expected_steps": case[4], "actual": actual, "observed": observed,
            "sha256": digest(path), "conclusion": "PASS"})
        print(f"demo_{index}: PASS ({observed['result']}, {len(observed['steps'])} steps)", flush=True)
    interactive = run([sys.executable, str(ROOT / "main_cli.py")], b"known\n")
    require(interactive["exit_code"] == 0 and json.loads(field(interactive["stdout"], "Input (JSON)")) == "known",
            "Interactive CLI smoke check failed")
    record["interactive_cli"] = interactive
    unit = run([sys.executable, "-X", "utf8", "-m", "unittest", "discover", "-s", "tests", "-v"])
    require(unit["exit_code"] == 0, "Regression tests failed")
    count = re.search(r"Ran (\d+) tests?", unit["stderr"])
    require(count is not None, "Missing test count")
    unit["test_count"] = int(count.group(1))
    record["unit_tests"] = unit
    require(sources() == before, "Sources changed during capture")
    record["completed_at"] = datetime.now().astimezone().isoformat()
    record["all_passed"] = True
    with CAPTURE.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    columns = ["case_id", "requirement_ids", "artifact_path", "artifact_type", "input_id", "request_id",
               "expected", "actual", "conclusion", "code_commit", "branch", "source_dirty", "captured_at",
               "operator", "environment", "interface_version", "rule_version", "related_ci", "sha256", "privacy_review"]
    with MANIFEST.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for index, item in enumerate(record["cases"], 1):
            covered = "B01;B02;B03;B04;B05;B06;B07;B08" if CASES[index - 1][1] == 0 else "B01;B02;B07;B08;B09"
            writer.writerow({"case_id": item["case_id"], "requirement_ids": covered,
                "artifact_path": item["artifact_path"], "artifact_type": "txt", "input_id": f"coursework_{index}",
                "request_id": item["observed"]["request_id"], "expected": CASES[index - 1][2] or "SUCCESS",
                "actual": item["observed"]["result"], "conclusion": "PASS", "code_commit": record["code_commit"],
                "branch": record["branch"], "source_dirty": "false", "captured_at": item["observed"]["timestamp"],
                "operator": record["operator"], "environment": json.dumps(record["environment"], ensure_ascii=True),
                "interface_version": "1.0", "rule_version": "input_rules_v1", "related_ci": "",
                "sha256": item["sha256"], "privacy_review": "Fixed public coursework input; CLI export unmodified"})
        writer.writerow({"case_id": "S1-CAPTURE", "requirement_ids": "B01;B08;B09;B10",
            "artifact_path": CAPTURE.relative_to(ROOT).as_posix(), "artifact_type": "json",
            "expected": "CLI cases, interactive smoke and unit tests pass", "actual": f"5 cases + interactive + {unit['test_count']} tests PASS",
            "conclusion": "PASS", "code_commit": record["code_commit"], "branch": record["branch"],
            "source_dirty": "false", "captured_at": record["captured_at"], "operator": record["operator"],
            "environment": json.dumps(record["environment"], ensure_ascii=True), "interface_version": "1.0",
            "rule_version": "input_rules_v1", "sha256": digest(CAPTURE), "privacy_review": "Public coursework inputs and local runtime metadata only"})


def verify():
    record = json.loads(CAPTURE.read_text(encoding="utf-8"))
    with MANIFEST.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    require(len(rows) == 6, "Expected five demos and one capture record")
    expected_paths = {f"evidence/stage_1/demo_{index}.txt" for index in range(1, 6)} | {"evidence/stage_1/capture.json"}
    require({row["artifact_path"] for row in rows} == expected_paths, "Wrong artifact paths")
    for row in rows:
        require(digest(ROOT / row["artifact_path"]) == row["sha256"], "Artifact hash mismatch: " + row["artifact_path"])
        require(row["code_commit"] == record["code_commit"] and row["conclusion"] == "PASS", "Metadata mismatch")
    require(record["all_passed"] and record["unit_tests"]["exit_code"] == 0, "Capture did not pass")
    require(len(record["cases"]) == 5, "Missing capture cases")
    for index, case in enumerate(CASES, 1):
        observed = inspect_demo(STAGE / f"demo_{index}.txt", case)
        item = record["cases"][index - 1]
        require(observed == item["observed"] and item["actual"]["exit_code"] == case[1], "Capture/report mismatch")
        row = next(row for row in rows if row["case_id"] == f"S1-{index:02d}")
        require(row["request_id"] == observed["request_id"] and row["actual"] == observed["result"], "Manifest/report mismatch")
    require(sources() == record["source_sha256"], "Current application/tests differ from captured version")
    tool_hash = record.get("verification_tool_sha256", record["capture_tool_sha256"])
    require(digest(Path(__file__)) == tool_hash, "Capture/verification tool changed")
    print(f"PASS: 5 exact inputs, 6 artifact hashes, real partial traces, reference matrix, {record['unit_tests']['test_count']} recorded tests, {len(record['source_sha256'])} source hashes")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", action="store_true", help="Capture once; refuses existing evidence. Default: verify only.")
    args = parser.parse_args()
    try:
        if args.capture:
            capture()
        verify()
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
