"""Минимальный Excel (.xlsx) без сторонних библиотек: записать одну таблицу и прочитать первый лист.

Хватает для выгрузки и загрузки закупочных цен. Формулы не вычисляются — берётся сохранённое значение.
"""

import csv
import io
import re
import zipfile
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 20_000


class TableError(ValueError):
    pass


def _col(n: int) -> str:
    name = ""
    while n:
        n, r = divmod(n - 1, 26)
        name = chr(65 + r) + name
    return name


def write_xlsx(rows: list[list], sheet: str = "Лист1", widths: list[int] | None = None) -> bytes:
    """Таблица → .xlsx. Первая строка — заголовок (жирным не делаем, зато закреплена)."""
    cells = []
    for r, row in enumerate(rows, start=1):
        out = []
        for c, value in enumerate(row, start=1):
            ref = f"{_col(c)}{r}"
            if value is None or value == "":
                continue
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                out.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                out.append(f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escape(str(value))}</t></is></c>')
        cells.append(f'<row r="{r}">{"".join(out)}</row>')
    cols = "".join(f'<col min="{i}" max="{i}" width="{w}" customWidth="1"/>' for i, w in enumerate(widths or [], start=1))
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
        + (f"<cols>{cols}</cols>" if cols else "")
        + f'<sheetData>{"".join(cells)}</sheetData></worksheet>'
    )
    files = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            "</Types>"
        ),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>"
        ),
        "xl/workbook.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<sheets><sheet name="{escape(sheet[:31])}" sheetId="1" r:id="rId1"/></sheets></workbook>'
        ),
        "xl/_rels/workbook.xml.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            "</Relationships>"
        ),
        "xl/worksheets/sheet1.xml": sheet_xml,
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, text in files.items():
            z.writestr(name, text)
    return buf.getvalue()


def _cell_index(ref: str) -> int:
    letters = re.match(r"[A-Z]+", ref or "A")
    n = 0
    for ch in letters.group(0) if letters else "A":
        n = n * 26 + ord(ch) - 64
    return n - 1


def _read_xlsx(data: bytes) -> list[list[str]]:
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        names = z.namelist()
        if sum(i.file_size for i in z.infolist()) > MAX_BYTES * 10:
            raise TableError("Файл слишком большой")
        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            shared = ["".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")) for si in root.findall("m:si", NS)]
        sheet = "xl/worksheets/sheet1.xml" if "xl/worksheets/sheet1.xml" in names else next(
            (n for n in sorted(names) if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")), None)
        if not sheet:
            raise TableError("В файле нет листов")
        root = ET.fromstring(z.read(sheet))
    except TableError:
        raise
    except Exception:
        raise TableError("Файл Excel не открывается") from None
    rows: list[list[str]] = []
    for row in root.iter(f"{{{NS['m']}}}row"):
        values: dict[int, str] = {}
        for c in row.findall("m:c", NS):
            kind = c.get("t")
            if kind == "inlineStr":
                text = "".join(t.text or "" for t in c.iter(f"{{{NS['m']}}}t"))
            else:
                v = c.find("m:v", NS)
                text = v.text if v is not None and v.text else ""
                if kind == "s" and text.isdigit() and int(text) < len(shared):
                    text = shared[int(text)]
            values[_cell_index(c.get("r", ""))] = text.strip()
        if values:
            rows.append([values.get(i, "") for i in range(max(values) + 1)])
        if len(rows) > MAX_ROWS:
            raise TableError(f"Слишком много строк: до {MAX_ROWS}")
    return rows


def _read_csv(data: bytes) -> list[list[str]]:
    for encoding in ("utf-8-sig", "cp1251"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise TableError("Не понятна кодировка файла")
    dialect = csv.Sniffer().sniff(text[:2000], delimiters=";,\t") if text.strip() else csv.excel
    rows = [[c.strip() for c in r] for r in csv.reader(io.StringIO(text), dialect)]
    if len(rows) > MAX_ROWS:
        raise TableError(f"Слишком много строк: до {MAX_ROWS}")
    return [r for r in rows if any(r)]


def read_table(data: bytes, filename: str = "") -> list[list[str]]:
    """Первый лист .xlsx или CSV (разделитель ; , или Tab) → строки со значениями-строками."""
    if len(data) > MAX_BYTES:
        raise TableError("Файл больше 5 МБ")
    if data.startswith(b"PK"):
        return _read_xlsx(data)
    if filename.lower().endswith((".xls",)) or data.startswith(b"\xd0\xcf\x11\xe0"):
        raise TableError("Старый формат .xls не поддерживается — сохраните файл как .xlsx или CSV")
    return _read_csv(data)
