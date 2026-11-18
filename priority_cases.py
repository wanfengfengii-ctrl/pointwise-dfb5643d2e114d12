"""Finite public inputs and hand-derived outcomes; no priority implementation."""
import copy
import json
import sys
import tempfile
import unittest
from fractions import Fraction as F
from pathlib import Path

import coverage as api
from coverage.intersections import point_on_segment, parameter_on_segment


def box(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


UNIT = box(0, 0, 1, 1)
TRIANGLE = [(0, 0), (1, 0), (0, 1)]
CASES = (
    dict(name="reversal", regions=[("A", UNIT, []), ("B", list(reversed(UNIT)), [])],
         fields={"A": [1, 0, 0], "B": [-1, 0, 1]}, area=F(1),
         components=[F(3, 4)], total=F(3, 4),
         winner_areas={("A",): F(1, 2), ("B",): F(1, 2)},
         samples=[((F(1, 4), 0), F(3, 4), ("B",)),
                  ((F(1, 2), 0), F(1, 2), ("A", "B")),
                  ((F(3, 4), 0), F(3, 4), ("A",))]),
    dict(name="identical", regions=[("A", UNIT, []), ("B", UNIT, []), ("C", UNIT, [])],
         fields={"A": [1, 0, 0], "B": [-1, 0, 1], "C": [1, 0, 0]},
         area=F(1), components=[F(3, 4)], total=F(3, 4),
         winner_areas={("A", "C"): F(1, 2), ("B",): F(1, 2)},
         samples=[((F(1, 4), 0), F(3, 4), ("B",)),
                  ((F(1, 2), 0), F(1, 2), ("A", "B", "C")),
                  ((F(3, 4), 0), F(3, 4), ("A", "C"))]),
    dict(name="partial_hole",
         regions=[("A", box(0, 0, 2, 2), [box(F(1, 2), F(1, 2), F(3, 2), F(3, 2))]),
                  ("B", box(1, 0, 2, 2), []), ("C", box(1, 0, 2, 2), [])],
         fields={"A": [0, 0, 0], "B": [0, 0, 10], "C": [0, 0, 10]},
         area=F(7, 2), components=[F(20)], total=F(20),
         winner_areas={("A",): F(3, 2), ("B", "C"): F(2)},
         samples=[((0, 0), F(0), ("A",)), ((1, 0), F(10), ("B", "C")),
                  ((F(1, 2), 1), F(0), ("A",))]),
    dict(name="point_contact",
         regions=[("A", UNIT, []), ("B", box(1, 1, 2, 2), [])],
         fields={"A": [0, 0, 0], "B": [0, 0, 10]},
         area=F(2), components=[F(0), F(10)], total=F(10),
         winner_areas={("A",): F(1), ("B",): F(1)},
         samples=[((1, 1), F(10), ("B",)), ((1, F(3, 4)), F(0), ("A",))]),
    dict(name="negative_edge",
         regions=[("A", UNIT, []), ("B", box(1, 0, 2, 1), [])],
         fields={"A": [0, 0, -3], "B": [0, 0, -1]},
         area=F(2), components=[F(-4)], total=F(-4),
         winner_areas={("A",): F(1), ("B",): F(1)},
         samples=[((F(1, 2), 0), F(-3), ("A",)),
                  ((1, 0), F(-1), ("B",)), ((F(3, 2), 0), F(-1), ("B",))]),
    dict(name="three_way",
         regions=[("A", TRIANGLE, []), ("B", TRIANGLE, []), ("C", TRIANGLE, [])],
         fields={"A": [1, 0, 0], "B": [0, 1, 0], "C": [-1, -1, 1]},
         area=F(1, 2), components=[F(11, 36)], total=F(11, 36),
         winner_areas={("A",): F(1, 6), ("B",): F(1, 6), ("C",): F(1, 6)},
         samples=[((F(1, 2), 0), F(1, 2), ("A", "C")),
                  ((0, F(1, 2)), F(1, 2), ("B", "C")),
                  ((F(1, 2), F(1, 2)), F(1, 2), ("A", "B"))]),
)


def prepare(case):
    members = [(name, api.put_region(name, outer, holes))
               for name, outer, holes in case["regions"]]
    api.seal_batch("day", members)


def priority_api():
    return api.build_priority_report, api.sample_priority


def requests_at(report, point):
    point = tuple(F(v) for v in point)
    for component in report["components"]:
        for boundary in component["boundaries"]:
            for index, segment in enumerate(boundary["segments"]):
                a, b = tuple(segment["start"]), tuple(segment["end"])
                if point_on_segment(point, a, b):
                    yield boundary["boundary_id"], index, parameter_on_segment(point, a, b)


def area_of_rings(rings):
    def unsigned(ring):
        return abs(sum((p[0] * q[1] - p[1] * q[0]
                        for p, q in zip(ring, ring[1:] + ring[:1])), F(0))) / 2
    return unsigned(rings[0]) - sum((unsigned(h) for h in rings[1:]), F(0))


def fixture_check():
    for case in CASES:
        with api.open_archive(":memory:"):
            prepare(case)
            report = api.build_report("v1", "day")
            if report["measurements"]["total_area"] != case["area"]:
                raise AssertionError((case["name"], "V1 area"))
            if len(report["components"]) != len(case["components"]):
                raise AssertionError((case["name"], "V1 component count"))
            for point, _, _ in case["samples"]:
                if not list(requests_at(report, point)):
                    raise AssertionError((case["name"], "sample is not on saved boundary", point))
    print("PRIORITY_FIXTURES_V1 " + json.dumps(
        [{"case": c["name"], "area": str(c["area"]),
          "priority_integral_expected": str(c["total"])} for c in CASES]))


class TestPriority(unittest.TestCase):
    def check_case(self, case, report):
        self.assertEqual(report["format"], 2)
        priority = report["priority"]
        self.assertEqual(priority["total_integral"], case["total"])
        self.assertIs(type(priority["total_integral"]), F)
        self.assertEqual(sorted(i["integral"] for i in priority["integrals"]),
                         sorted(case["components"]))
        self.assertEqual([i["component_id"] for i in priority["integrals"]],
                         [c["component_id"] for c in report["components"]])
        expected_fields = [
            dict(region_id=m["region_id"], revision=m["revision"],
                 coefficients=[F(v) for v in case["fields"][m["region_id"]]])
            for m in report["binding"]]
        self.assertEqual(priority["fields"], expected_fields)
        areas, sums, ids = {}, {}, set()
        for cell in priority["cells"]:
            self.assertNotIn(cell["cell_id"], ids)
            ids.add(cell["cell_id"])
            names = tuple(w["region_id"] for w in cell["winners"])
            self.assertEqual(names, tuple(sorted(set(names))))
            self.assertTrue(names)
            for member in cell["winners"]:
                self.assertIn(member, report["binding"])
            area = area_of_rings(cell["rings"])
            self.assertGreater(area, 0)
            areas[names] = areas.get(names, F(0)) + area
            cid = cell["component_id"]
            sums[cid] = sums.get(cid, F(0)) + cell["integral"]
            self.assertIs(type(cell["integral"]), F)
        self.assertEqual(areas, case["winner_areas"])
        self.assertEqual(sums, {i["component_id"]: i["integral"] for i in priority["integrals"]})
        _, sample = priority_api()
        for point, value, names in case["samples"]:
            requests = list(requests_at(report, point))
            self.assertTrue(requests)
            for boundary, index, t in requests:
                result = sample(report["report_id"], boundary, index, t)
                self.assertEqual(result, dict(
                    point=[F(v) for v in point], value=value,
                    winners=[dict(region_id=name, revision=1) for name in names]))
                self.assertEqual(api.sample_boundary(report["report_id"], boundary, index, t)["point"],
                                 result["point"])

    def test_analytic_cases(self):
        build, _ = priority_api()
        for case in CASES:
            with self.subTest(case=case["name"]), api.open_archive(":memory:"):
                prepare(case)
                normal = api.build_report("plain", "day")
                report = build("priority", "day", copy.deepcopy(case["fields"]))
                for key in ("binding", "inputs", "components", "measurements"):
                    self.assertEqual(report[key], normal[key])
                self.check_case(case, report)
                self.assertEqual(api.read_report("priority"), report)
                self.assertEqual(api.open_package(api.export_report("priority")), report)

    def test_binding_failure_and_isolation(self):
        build, sample = priority_api()
        case = CASES[1]
        with api.open_archive(":memory:") as archive:
            prepare(case)
            plain_report = api.build_report("plain", "day")
            old = api.export_report("plain")
            fields = copy.deepcopy(case["fields"])
            report = build("priority", "day", fields)
            saved = api.export_report("priority")
            fields["A"][0] = 999
            report["priority"]["cells"].clear()
            self.assertEqual(api.export_report("priority"), saved)
            replay = {k: tuple(F(v) for v in values)
                      for k, values in reversed(list(case["fields"].items()))}
            self.assertEqual(build("priority", "day", replay), api.open_package(saved))
            changed = copy.deepcopy(case["fields"])
            changed["A"][0] = 2
            with self.assertRaises(ValueError):
                build("priority", "day", changed)
            api.seal_batch("other", [("A", 1), ("B", 1), ("C", 1)])
            with self.assertRaises(ValueError):
                build("priority", "other", case["fields"])
            with self.assertRaises(ValueError):
                build("plain", "day", case["fields"])
            with self.assertRaises(ValueError):
                api.build_report("priority", "day")
            with self.assertRaises(ValueError):
                sample("plain", *next(requests_at(plain_report, (F(1, 2), 0))))
            with self.assertRaises(KeyError):
                build("absent-batch", "missing", case["fields"])
            with self.assertRaises(KeyError):
                sample("absent-report", "missing", 0, F(0))
            for bad in (None, {}, dict(case["fields"], extra=[0, 0, 0]),
                        dict(case["fields"], A=[True, 0, 0]),
                        dict(case["fields"], A=[0.5, 0, 0]),
                        dict(case["fields"], A=[0, 0])):
                with self.subTest(fields=bad), self.assertRaises(ValueError):
                    build("bad", "day", bad)
            report = api.read_report("priority")
            boundary, index, t = next(requests_at(report, (F(1, 2), 0)))
            for bad in (0, True, 0.5, F(-1), F(2)):
                with self.assertRaises(ValueError):
                    sample("priority", boundary, index, bad)
            with self.assertRaises(KeyError):
                sample("priority", boundary, -1, F(0))
            def fail(name, connection):
                if name == "report.after_payload":
                    connection.execute("INSERT INTO missing_priority_table VALUES(1)")
            archive.failure_hook = fail
            import sqlite3
            try:
                with self.assertRaises(sqlite3.OperationalError):
                    build("failed", "day", case["fields"])
            finally:
                archive.failure_hook = None
            for identity in ("bad", "failed", "absent-batch"):
                for table in ("reports", "receipts"):
                    self.assertEqual(archive.connection.execute(
                        "SELECT count(*) FROM " + table + " WHERE report_id=?", (identity,)).fetchone()[0], 0)
            self.assertEqual(api.export_report("plain"), old)
            self.assertEqual(api.export_report("priority"), saved)
            self.check_case(case, build("failed", "day", case["fields"]))

    def test_reopen_and_corrupt_packages(self):
        build, sample = priority_api()
        case = CASES[1]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "priority.sqlite"
            with api.open_archive(path):
                prepare(case)
                api.build_report("plain", "day")
                plain = api.export_report("plain")
                report = build("priority", "day", case["fields"])
                saved = api.export_report("priority")
                request = next(requests_at(report, (F(1, 2), 0)))
                reading = sample("priority", *request)
                report["priority"]["fields"][0]["coefficients"][0] = F(999)
                report["inputs"].clear()
                reading["winners"].clear()
                api.put_region("A", box(0, 0, 4, 4))
            with api.open_archive(path):
                self.assertEqual(api.export_report("plain"), plain)
                self.assertEqual(api.export_report("priority"), saved)
                self.check_case(case, api.read_report("priority"))
                self.assertEqual(sample("priority", *request)["winners"],
                                 [dict(region_id=n, revision=1) for n in ("A", "B", "C")])
        raw = json.loads(saved)
        mutations = []
        bad = copy.deepcopy(raw)
        pair = bad["report"]["priority"]["cells"][0]["integral"]["q"]
        pair[0] += pair[1]
        mutations.append(bad)
        bad = copy.deepcopy(raw)
        del bad["report"]["priority"]["fields"]
        mutations.append(bad)
        bad = copy.deepcopy(raw)
        bad["report"]["priority"]["cells"][0]["winners"] = [
            dict(region_id="absent", revision=1)]
        mutations.append(bad)
        tied_index = next(i for i, cell in enumerate(raw["report"]["priority"]["cells"])
                          if len(cell["winners"]) == 2)
        bad = copy.deepcopy(raw)
        bad["report"]["priority"]["cells"][tied_index]["winners"].pop()
        mutations.append(bad)
        bad = copy.deepcopy(raw)
        bad["report"]["priority"]["cells"][tied_index]["winners"] = [
            dict(region_id="B", revision=1)]
        mutations.append(bad)
        for bad in mutations:
            with self.subTest(package=bad), self.assertRaises(ValueError):
                api.open_package(json.dumps(bad))


def verify():
    suite = unittest.TestSuite([
        unittest.defaultTestLoader.discover("tests", pattern="test_*.py"),
        unittest.defaultTestLoader.loadTestsFromTestCase(TestPriority)])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)


def demo():
    build, sample = priority_api()
    case = CASES[1]
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "demo.sqlite"
        with api.open_archive(path):
            prepare(case)
            report = build("priority", "day", copy.deepcopy(case["fields"]))
            TestPriority().check_case(case, report)
            request = next(requests_at(report, (F(1, 2), 0)))
            reading = sample("priority", *request)
            saved = api.export_report("priority")
            if api.open_package(saved) != report:
                raise AssertionError("offline mismatch")
            api.put_region("A", box(0, 0, 4, 4))
        with api.open_archive(path):
            if api.export_report("priority") != saved or sample("priority", *request) != reading:
                raise AssertionError("fixed delivery drift")
            actual = api.read_report("priority")["priority"]["total_integral"]
        print("POINTWISE_SCENARIO " + json.dumps({
            "case_id": "priority-identical",
            "input": {"regions": ["A:unit square", "B:unit square", "C:unit square"],
                      "fields": case["fields"]},
            "expected": {"integral": "3/4", "midpoint_value": "1/2",
                         "midpoint_winners": ["A", "B", "C"]},
            "actual": {"integral": str(actual), "midpoint_value": str(reading["value"]),
                       "midpoint_winners": [w["region_id"] for w in reading["winners"]]},
            "offline_equal": True, "reopen_equal": True,
            "oracle": "two half squares each contribute 3/8; identical A/C counted once"
        }, sort_keys=True))


if __name__ == "__main__":
    modes = {"--fixtures": fixture_check, "--verify": verify, "--demo": demo}
    if len(sys.argv) != 2 or sys.argv[1] not in modes:
        raise SystemExit("usage: python3 -B priority_cases.py --fixtures|--verify|--demo")
    modes[sys.argv[1]]()
