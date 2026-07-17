"""Slice 2 document-toolkit tests — pure, no DB or network."""

from __future__ import annotations

import io
import zipfile

import pytest
from mactech_workers.documents import (
    build_sections,
    classify_document,
    detect_format,
    extract_text,
)
from mactech_workers.documents.archive import ArchiveError, expand_archive, is_zip
from mactech_workers.documents.store import FilesystemDocumentStore, storage_key_for

# ---- format detection + extraction ----


def test_detect_and_extract_txt():
    blob = b"This solicitation requires an FRCS cybersecurity specialist."
    assert detect_format("scope.txt", blob) == "txt"
    doc = extract_text("scope.txt", blob)
    assert doc.ok and "FRCS" in doc.text


def test_detect_and_extract_html_strips_tags():
    blob = b"<html><body><h1>Section L</h1><script>x=1</script><p>Instructions to offerors</p></body></html>"
    assert detect_format("l.html", blob) == "html"
    doc = extract_text("l.html", blob)
    assert "Instructions to offerors" in doc.text
    assert "x=1" not in doc.text  # script stripped


def test_detect_and_extract_csv():
    blob = b"item,qty\nUFGS 25 05 11,1\n"
    doc = extract_text("bid.csv", blob)
    assert doc.ok and "UFGS 25 05 11" in doc.text


def test_detect_and_extract_xlsx():
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Requirement", "Section"])
    ws.append(["Cybersecurity submittal", "25 05 11"])
    buf = io.BytesIO()
    wb.save(buf)
    doc = extract_text("matrix.xlsx", buf.getvalue())
    assert doc.ok and "Cybersecurity submittal" in doc.text


def test_zip_is_not_treated_as_text():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.txt", "hi")
    doc = extract_text("pkg.zip", buf.getvalue())
    assert not doc.ok and doc.format == "zip"


# ---- safe archive expansion ----


def test_expand_archive_flattens_members():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("PWS.txt", "performance work statement")
        zf.writestr("nested/SpecSection2505 11.txt", "cybersecurity for FRCS")
    files = expand_archive(buf.getvalue(), source_name="package.zip")
    names = {f.filename for f in files}
    assert "PWS.txt" in names
    # Path components stripped (traversal defense).
    assert "SpecSection2505 11.txt" in names


def test_expand_archive_rejects_traversal_and_executables():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../evil.txt", "nope")
        zf.writestr("payload.exe", b"MZ")
        zf.writestr("ok.txt", "fine")
    files = expand_archive(buf.getvalue(), source_name="a.zip")
    names = {f.filename for f in files}
    assert "ok.txt" in names
    assert "evil.txt" in names  # basename kept, path defused
    assert "payload.exe" not in names  # executable dropped


def test_expand_archive_rejects_too_many_members():
    from mactech_workers.documents import archive as arch

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for i in range(arch.MAX_MEMBERS + 1):
            zf.writestr(f"f{i}.txt", "x")
    with pytest.raises(ArchiveError):
        expand_archive(buf.getvalue(), source_name="many.zip")


def test_expand_archive_rejects_depth():
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as zf:
        zf.writestr("deep.txt", "x")
    mid = io.BytesIO()
    with zipfile.ZipFile(mid, "w") as zf:
        zf.writestr("inner.zip", inner.getvalue())
    outer = io.BytesIO()
    with zipfile.ZipFile(outer, "w") as zf:
        zf.writestr("mid.zip", mid.getvalue())
    # outer -> mid -> inner is depth 3; limit is 2.
    with pytest.raises(ArchiveError):
        expand_archive(outer.getvalue(), source_name="outer.zip")


def test_is_zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("a", "b")
    assert is_zip(buf.getvalue())
    assert not is_zip(b"%PDF-1.7")


# ---- classification ----


@pytest.mark.parametrize(
    "filename,text,expected",
    [
        ("PWS.pdf", "", "performance_work_statement"),
        ("Statement of Work.docx", "", "statement_of_work"),
        ("Section L.pdf", "", "section_l"),
        ("Section M - Evaluation.pdf", "", "section_m"),
        ("Wage Determination.pdf", "", "wage_determination"),
        ("Amendment 0002.pdf", "", "amendment"),
        (
            "random.pdf",
            "SECTION 25 05 11 CYBERSECURITY FOR FACILITY-RELATED CONTROL SYSTEMS",
            "ufgs_specification",
        ),
        ("misc.pdf", "nothing notable here", "other"),
    ],
)
def test_classify_document(filename, text, expected):
    assert classify_document(filename, text) == expected


# ---- sections / provenance ----


def test_build_sections_page_offsets_align():
    pages = ["SECTION 25 05 11\nCybersecurity for FRCS", "PART 2 - PRODUCTS\nBACnet controllers"]
    sections = build_sections(pages)
    assert len(sections) == 2
    assert sections[0].page_number == 1
    assert sections[0].section_heading and "25 05 11" in sections[0].section_heading
    # Offsets index into the JOIN-concatenated body.
    from mactech_workers.documents.sections import combined_text

    body = combined_text(pages)
    for s in sections:
        assert body[s.char_start : s.char_end] == pages[s.ordinal]


# ---- object store ----


def test_filesystem_store_roundtrip(tmp_path):
    store = FilesystemDocumentStore(root=tmp_path)
    key = storage_key_for("opp-1", "abc123", "spec.pdf")
    store.put(key, b"%PDF-1.7 body")
    assert store.exists(key)
    assert store.get(key) == b"%PDF-1.7 body"


def test_storage_key_is_content_addressed():
    k1 = storage_key_for("opp-1", "hashA", "a.pdf")
    k2 = storage_key_for("opp-1", "hashA", "a.pdf")
    assert k1 == k2 and k1.endswith(".pdf")


def test_store_rejects_traversal_key(tmp_path):
    store = FilesystemDocumentStore(root=tmp_path)
    with pytest.raises(ValueError):
        store.put("../../etc/passwd", b"x")
