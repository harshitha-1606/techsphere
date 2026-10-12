"""End-to-end workflow tests (run: python -m unittest discover -s tests -v)."""
import io
import os
import sys
import tempfile
import unittest
import zipfile

_tmp = tempfile.mkdtemp(prefix="ts_test_")
os.environ.update(DATA_DIR=_tmp, DEMO_MODE="true", SECRET_KEY="test-secret")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openpyxl  # noqa: E402
from pypdf import PdfReader  # noqa: E402

from backend import app as appmod  # noqa: E402
from backend import db  # noqa: E402

app = appmod.app


def make_xlsx(rows, header=None, title_rows=1, merge_dept=None):
    wb = openpyxl.Workbook()
    ws = wb.active
    for i in range(title_rows):
        ws.append([f"TECH SPHERE participants list {i}"])
    ws.append(header or ["S.No", "Student Name", "Department", "Roll No.", "Email ID", "Mobile Number", "Team / Batch", "Theme / Topic"])
    for r in rows:
        ws.append(r)
    if merge_dept:
        ws.merge_cells(merge_dept)
    b = io.BytesIO()
    wb.save(b)
    return b.getvalue()


ROWS = [
    [1, "B. Harshitha", "2nd Year AIDS Department", "22AD001", "  Harshitha@Example.com ", 9876500001.0, "Team 1", "IoT"],
    [2, "  K.  Ravi   Kumar ", "3rd Year CSE", "22CS002", "ravi@example.com", "9876500002", "Team 2", "AI"],
    [3, "Duplicate Email", "3rd Year CSE", "22CS003", "RAVI@example.com", "9", "Team 2", "AI"],
    [4, "", "3rd Year CSE", "22CS004", "noname@example.com", "9", "T", "x"],
    [5, "Bad Email", "3rd Year CSE", "22CS005", "not-an-email", "9", "T", "x"],
    [6, "No Dept", "", "22CS006", "nodept@example.com", "9", "T", "x"],
    [None] * 8,
    [7, "L" * 130, "3rd Year CSE", "22CS007", "long@example.com", "9", "T", "x"],
    [8, "Venkata Subrahmanyeswara Rao Chinthalapudi Naga Sai", "Computer Science and Engineering (Data Science) 4th Year", "22CS008", "longish@example.com", "9", "T", "x"],
    [9, "Merged Dept One", "2nd Year ECE", "22EC009", "m1@example.com", "9", "T", "x"],
    [10, "Merged Dept Two", None, "22EC010", "m2@example.com", "9", "T", "x"],
]
VALID = ["harshitha@example.com", "ravi@example.com", "longish@example.com", "m1@example.com", "m2@example.com"]


def login_coord(c, pw="coordinator@123"):
    return c.post("/api/coordinator/login", json={"username": "techshere", "password": pw})


class Workflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = app.test_client()

    def upload(self, content, name="p.xlsx"):
        return self.c.post("/api/coordinator/upload", data={"file": (io.BytesIO(content), name)},
                           content_type="multipart/form-data")

    def test_01_auth_and_guards(self):
        self.assertEqual(self.c.get("/api/coordinator/participants").status_code, 401)
        self.assertEqual(self.c.get("/api/participant/me").status_code, 401)
        self.assertEqual(login_coord(self.c, "wrong").status_code, 401)
        self.assertEqual(login_coord(self.c).status_code, 200)
        self.assertEqual(self.c.get("/api/coordinator/me").status_code, 200)

    def test_02_upload_validation(self):
        login_coord(self.c)
        r = self.upload(make_xlsx(ROWS, title_rows=2, merge_dept="C13:C14"))
        self.assertEqual(r.status_code, 200, r.get_json())
        j = r.get_json()
        self.assertEqual(j["valid"], 5, [(x["row"], x["errors"]) for x in j["rows"]])
        self.assertEqual(j["invalid"], 5)
        self.assertEqual(j["blank_rows_skipped"], 1)
        errs = {x["row"]: x["errors"] for x in j["rows"] if x["errors"]}
        self.assertTrue(any("Duplicate email" in e for e in sum(errs.values(), [])))
        self.assertTrue(any("Invalid email" in e for e in sum(errs.values(), [])))
        self.assertTrue(any("Missing Student Name" in e for e in sum(errs.values(), [])))
        self.assertTrue(any("Missing Department" in e for e in sum(errs.values(), [])))
        self.assertTrue(any("longer than" in e for e in sum(errs.values(), [])))
        good = {x["data"]["email"]: x["data"] for x in j["rows"] if x["valid"]}
        self.assertEqual(good["harshitha@example.com"]["mobile"], "9876500001")
        self.assertEqual(good["ravi@example.com"]["name"], "K. Ravi Kumar")
        self.assertEqual(good["m2@example.com"]["department"], "2nd Year ECE")  # merged cell filled
        self.assertEqual(self.c.get("/api/coordinator/participants").get_json(), [])  # nothing imported yet

    def test_03_bad_files(self):
        login_coord(self.c)
        self.assertEqual(self.upload(b"", "p.xlsx").status_code, 400)
        self.assertEqual(self.upload(b"hello", "p.txt").status_code, 422)
        self.assertEqual(self.upload(b"not really excel", "p.xlsx").status_code, 422)
        r = self.upload(make_xlsx([[1, "x"]], header=["A", "B"]))
        self.assertEqual(r.status_code, 422)
        self.assertIn("Required column", r.get_json()["error"])
        r = self.upload(make_xlsx([], header=["Student Name", "Department", "Email ID"]))
        self.assertEqual(r.status_code, 422)  # header only / empty dataset

    def test_04_full_flow(self):
        login_coord(self.c)
        tok = self.upload(make_xlsx(ROWS, title_rows=2, merge_dept="C13:C14")).get_json()["token"]
        imp = self.c.post("/api/coordinator/import", json={"token": tok}).get_json()
        self.assertEqual((imp["inserted"], imp["invalid_skipped"]), (5, 5))
        self.assertEqual(self.c.post("/api/coordinator/import", json={"token": tok}).status_code, 404)  # no double import
        people = self.c.get("/api/coordinator/participants").get_json()
        self.assertEqual(sorted(p["email"] for p in people), sorted(VALID))
        self.assertTrue(all(p["status"] == "pending" for p in people))

        # generate (force one failure first, then retry)
        orig = appmod.certs.render_pdf
        def flaky(path, name, dept, cid):
            if name.startswith("Merged Dept One"):
                raise RuntimeError("simulated failure")
            return orig(path, name, dept, cid)
        appmod.certs.render_pdf = flaky
        self.run_generation()
        appmod.certs.render_pdf = orig
        s = self.c.get("/api/coordinator/summary").get_json()
        self.assertEqual((s["generated"], s["failed"]), (4, 1))
        self.assertEqual(self.c.get("/api/coordinator/generate/status").get_json()["failed"], 1)
        self.run_generation(only_failed=True)
        s = self.c.get("/api/coordinator/summary").get_json()
        self.assertEqual((s["generated"], s["failed"], s["total_participants"]), (5, 0, 5))

        # idempotent: repeating changes nothing
        before = {p["email"]: p["certificate_id"] for p in self.c.get("/api/coordinator/participants").get_json()}
        stamps = {f: os.path.getmtime(os.path.join(_tmp, "certificates", f)) for f in os.listdir(os.path.join(_tmp, "certificates"))}
        self.run_generation()
        self.assertEqual(self.c.get("/api/coordinator/generate/status").get_json()["skipped"], 5)
        after = {p["email"]: p["certificate_id"] for p in self.c.get("/api/coordinator/participants").get_json()}
        self.assertEqual(before, after)
        self.assertEqual(stamps, {f: os.path.getmtime(os.path.join(_tmp, "certificates", f)) for f in stamps})

        # PDF content: each certificate carries its own name/department, exact filenames
        people = {p["email"]: p for p in self.c.get("/api/coordinator/participants").get_json()}
        h = people["harshitha@example.com"]
        pdf = self.c.get(f"/api/coordinator/certificates/{h['certificate_id']}/pdf")
        self.assertEqual(pdf.status_code, 200)
        self.assertIn("TechSphere_B_Harshitha.pdf", pdf.headers["Content-Disposition"])
        self.assertTrue(pdf.data.startswith(b"%PDF"))
        meta = PdfReader(io.BytesIO(pdf.data)).metadata
        self.assertIn("B. Harshitha", meta.title)
        self.assertIn(h["certificate_id"], meta.subject)

        # ZIP
        z = self.c.get("/api/coordinator/certificates.zip")
        self.assertEqual(z.status_code, 200)
        names = zipfile.ZipFile(io.BytesIO(z.data)).namelist()
        self.assertEqual(len(names), 5)
        self.assertIn("TechSphere_B_Harshitha.pdf", names)
        self.assertEqual(len(set(p["certificate_id"] for p in people.values())), 5)

    def test_05_participant_isolation(self):
        p = app.test_client()
        self.assertEqual(p.get("/api/participant/certificate.pdf").status_code, 401)
        self.assertEqual(p.get("/api/coordinator/participants").status_code, 401)
        bad = p.post("/api/participant/login", json={"username": "harshitha@example.com", "password": "ravi@example.com"})
        self.assertEqual(bad.status_code, 401)
        self.assertEqual(p.post("/api/participant/login", json={"username": "ghost@example.com", "password": "ghost@example.com"}).status_code, 401)
        ok = p.post("/api/participant/login", json={"username": " HARSHITHA@example.com ", "password": "harshitha@EXAMPLE.com"})
        self.assertEqual(ok.status_code, 200)
        me = p.get("/api/participant/me").get_json()
        self.assertEqual((me["name"], me["department"], me["ready"]), ("B. Harshitha", "2nd Year AIDS Department", True))
        pdf = p.get("/api/participant/certificate.pdf")
        self.assertEqual(pdf.status_code, 200)
        self.assertIn("B. Harshitha", PdfReader(io.BytesIO(pdf.data)).metadata.title)
        self.assertEqual(p.get("/api/participant/certificate/preview.jpg").status_code, 200)
        # a participant session must not reach coordinator APIs or other people's files
        for url in ("/api/coordinator/participants", "/api/coordinator/certificates.zip", "/api/coordinator/summary"):
            self.assertEqual(p.get(url).status_code, 401, url)
        other = self.c.get("/api/coordinator/participants").get_json()
        oid = next(x["certificate_id"] for x in other if x["email"] == "ravi@example.com")
        self.assertEqual(p.get(f"/api/coordinator/certificates/{oid}/pdf").status_code, 401)
        self.assertEqual(p.post("/api/participant/logout").status_code, 200)
        self.assertEqual(p.get("/api/participant/me").status_code, 401)

    def test_06_not_ready_message_state(self):
        c = app.test_client()
        login_coord(c)
        tok = c.post("/api/coordinator/upload", data={"file": (io.BytesIO(make_xlsx(
            [[1, "Late Student", "1st Year IT", "r", "late@example.com", "1", "T", "x"]])), "p.xlsx")},
            content_type="multipart/form-data").get_json()["token"]
        c.post("/api/coordinator/import", json={"token": tok})
        p = app.test_client()
        p.post("/api/participant/login", json={"username": "late@example.com", "password": "late@example.com"})
        self.assertFalse(p.get("/api/participant/me").get_json()["ready"])
        self.assertEqual(p.get("/api/participant/certificate.pdf").status_code, 404)

    def test_07_changed_data_regenerates_same_id(self):
        c = app.test_client()
        login_coord(c)
        cid = next(x for x in c.get("/api/coordinator/participants").get_json() if x["email"] == "ravi@example.com")["certificate_id"]
        rows = [[1, "K. Ravi Kumar Reddy", "3rd Year CSE", "22CS002", "ravi@example.com", "1", "T", "x"]]
        tok = c.post("/api/coordinator/upload", data={"file": (io.BytesIO(make_xlsx(rows)), "p.xlsx")},
                     content_type="multipart/form-data").get_json()["token"]
        self.assertEqual(c.post("/api/coordinator/import", json={"token": tok}).get_json()["updated"], 1)
        mid = next(x for x in c.get("/api/coordinator/participants").get_json() if x["email"] == "ravi@example.com")
        self.assertEqual(mid["status"], "pending")  # stale -> not served until regenerated
        self.assertEqual(c.get(f"/api/coordinator/certificates/{cid}/pdf").status_code, 404)
        self.run_generation(c)
        after = next(x for x in c.get("/api/coordinator/participants").get_json() if x["email"] == "ravi@example.com")
        self.assertEqual((after["status"], after["certificate_id"]), ("generated", cid))

    def test_08_rate_limit_and_persistence(self):
        c = app.test_client()
        codes = [c.post("/api/participant/login", json={"username": "x@y.com", "password": "nope"}).status_code for _ in range(7)]
        self.assertEqual(codes[-1], 429)
        # "restart": brand-new DB connection still sees records and files on disk
        with db.connect() as conn:
            n = conn.execute("SELECT COUNT(*) FROM certificates WHERE status='generated'").fetchone()[0]
        self.assertGreaterEqual(n, 5)
        self.assertTrue(any(f.endswith(".pdf") for f in os.listdir(os.path.join(_tmp, "certificates"))))

    def run_generation(self, client=None, only_failed=False):
        import time
        c = client or self.c
        self.assertEqual(c.post("/api/coordinator/generate", json={"only_failed": only_failed}).status_code, 200)
        for _ in range(200):
            if c.get("/api/coordinator/generate/status").get_json()["state"] == "done":
                return
            time.sleep(0.1)
        self.fail("generation did not finish")


if __name__ == "__main__":
    unittest.main()
