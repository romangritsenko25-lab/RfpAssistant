"""Drop-down lists that openpyxl drops: data validations stored in the ``x14`` sheet extension.

Excel keeps a list whose source is another sheet in ``<extLst>`` of the sheet XML, not in the
``dataValidations`` element that openpyxl reads. The file is only read here (zip + XML), nothing in it
is executed. A document type declaration is refused, which closes entity-expansion tricks.
"""

import zipfile
from io import BytesIO
from pathlib import Path
from typing import NamedTuple
from xml.etree import ElementTree

MAX_XML_BYTES = 50_000_000
_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
_X14 = "http://schemas.microsoft.com/office/spreadsheetml/2009/9/main"
_XM = "http://schemas.microsoft.com/office/excel/2006/main"


class X14List(NamedTuple):
    """One list validation: the cells it covers (as written in the file) and its source formula."""

    sqref: str
    formula: str


def read_x14_lists(path: Path) -> dict[str, list[X14List]]:
    """Sheet name -> list validations found in the sheets' x14 extension. Unreadable parts are skipped."""
    try:
        with zipfile.ZipFile(path) as archive:
            targets = _sheet_parts(archive)
            lists: dict[str, list[X14List]] = {}
            for name, part in targets.items():
                data = _read_part(archive, part)
                if data is None or _X14.encode() not in data or b"dataValidation" not in data:
                    continue
                found = _lists_in_sheet(data)
                if found:
                    lists[name] = found
            return lists
    except (zipfile.BadZipFile, ElementTree.ParseError, KeyError):
        return {}


def _read_part(archive: zipfile.ZipFile, part: str) -> bytes | None:
    try:
        info = archive.getinfo(part)
    except KeyError:
        return None
    if info.file_size > MAX_XML_BYTES:
        return None
    data = archive.read(info)
    return None if b"<!DOCTYPE" in data or b"<!ENTITY" in data else data


def _sheet_parts(archive: zipfile.ZipFile) -> dict[str, str]:
    """Sheet name -> path of its XML part inside the archive."""
    workbook, rels = (_read_part(archive, p) for p in ("xl/workbook.xml", "xl/_rels/workbook.xml.rels"))
    if workbook is None or rels is None:
        return {}
    by_id = {
        rel.get("Id"): rel.get("Target", "")
        for rel in ElementTree.fromstring(rels).iter(f"{{{_PKG_REL}}}Relationship")
    }
    parts: dict[str, str] = {}
    for sheet in ElementTree.fromstring(workbook).iter(f"{{{_MAIN}}}sheet"):
        target = by_id.get(sheet.get(f"{{{_REL}}}id"))
        if target and sheet.get("name"):
            parts[sheet.get("name")] = target.lstrip("/") if target.startswith("/") else f"xl/{target}"
    return parts


def _lists_in_sheet(data: bytes) -> list[X14List]:
    found: list[X14List] = []
    for _, element in ElementTree.iterparse(BytesIO(data), events=("end",)):
        if element.tag != f"{{{_X14}}}dataValidation":
            continue
        formula = element.findtext(f"{{{_X14}}}formula1/{{{_XM}}}f")
        sqref = element.findtext(f"{{{_XM}}}sqref")
        if element.get("type") == "list" and formula and sqref:
            found.append(X14List(sqref.strip(), formula.strip()))
        element.clear()
    return found
