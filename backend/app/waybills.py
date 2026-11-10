"""Накладные Kaspi: много файлов → один PDF для термопринтера (по одной наклейке на страницу).

Kaspi отдаёт накладную как лист A4, на котором наклейка занимает четверть листа (обычно левую верхнюю;
если на листе несколько наклеек — они в других четвертях). Мы находим на каждом листе четверти с текстом,
вырезаем их и кладём по одной на страницу нужного размера (по умолчанию 75×120 мм), подряд.

В накладных есть имена и адреса покупателей, поэтому ничего не сохраняем на диск: всё в памяти.
"""

import hashlib
import io
import re
import zipfile
from dataclasses import dataclass, field

from pypdf import PageObject, PdfReader, PdfWriter, Transformation
from pypdf.generic import ArrayObject

MM = 72 / 25.4
A4 = (210, 297)
# Раскладки: страница (мм) и сетка (колонки × строки) наклеек на ней; "join" — просто склеить файлы как есть.
LAYOUTS = {
    "a4x1": (A4, (1, 1)),
    "a4x4": (A4, (2, 2)),
    "a4x8": (A4, (2, 4)),
    "a4x9": (A4, (3, 3)),
    "75x120": ((75, 120), (1, 1)),
    "100x150": ((100, 150), (1, 1)),
    "join": None,
}
SIZES = LAYOUTS  # старое имя
MAX_FILES = 200
MAX_BYTES = 30 * 1024 * 1024
CELL_MARGIN = 3 * MM  # поля вокруг наклейки на листе A4


class WaybillError(ValueError):
    pass


def is_zip(data: bytes) -> bool:
    return data.startswith(b"PK\x03\x04") or data.startswith(b"PK\x05\x06")


def unpack(files: list[bytes]) -> list[bytes]:
    """Раскрыть ZIP-архивы: PDF из архива встают на его место (по имени файла), остальное остаётся как есть."""
    return [data for _, data in unpack_named([("", f) for f in files])]


def unpack_named(files: list[tuple[str, bytes]]) -> list[tuple[str, bytes]]:
    """Как unpack, но с именами файлов: (имя, содержимое). Имя нужно, чтобы узнать номер заказа.

    Всё в памяти. Размер распакованного проверяем заранее и при чтении, чтобы «zip-бомба» не забила память.
    """
    result: list[tuple[str, bytes]] = []
    total = 0
    for n, (name, data) in enumerate(files, start=1):
        if not is_zip(data):
            result.append((name, data))
            total += len(data)
            continue
        try:
            archive = zipfile.ZipFile(io.BytesIO(data))
            entries = sorted(
                (
                    info
                    for info in archive.infolist()
                    if not info.is_dir()
                    and info.filename.lower().endswith(".pdf")
                    and not info.filename.startswith("__MACOSX/")
                    and not info.filename.rsplit("/", 1)[-1].startswith("._")
                ),
                key=lambda info: info.filename,
            )
            if not entries:
                raise WaybillError(f"В архиве №{n} нет PDF-накладных")
            for info in entries:
                if len(result) >= MAX_FILES or total + info.file_size > MAX_BYTES:
                    raise WaybillError(f"Слишком много за раз: до {MAX_FILES} файлов и до 30 МБ")
                with archive.open(info) as entry:
                    pdf = entry.read(MAX_BYTES - total + 1)
                total += len(pdf)
                if total > MAX_BYTES:
                    raise WaybillError(f"Слишком много за раз: до {MAX_FILES} файлов и до 30 МБ")
                result.append((info.filename.rsplit("/", 1)[-1], pdf))
        except WaybillError:
            raise
        except Exception:
            raise WaybillError(f"Архив №{n} не открывается (повреждён или с паролем)") from None
    return result


def _text_points(page: PageObject) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []

    def visitor(text, cm, tm, font_dict, font_size):
        if text and text.strip():
            # Положение текста на листе: матрица текста, умноженная на текущую матрицу страницы.
            x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
            y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
            points.append((x, y))

    try:
        page.extract_text(visitor_text=visitor)
    except Exception:
        pass
    return points


def label_regions(page: PageObject) -> list[tuple[float, float, float, float]]:
    """Прямоугольники (x0, y0, x1, y1) с наклейками на странице, по порядку чтения."""
    box = page.mediabox
    left, bottom, width, height = float(box.left), float(box.bottom), float(box.width), float(box.height)
    is_a4_like = width > 400 and height > 600
    if not is_a4_like:
        return [(left, bottom, left + width, bottom + height)]  # уже размер наклейки
    half_w, half_h = width / 2, height / 2
    quadrants = [  # левая верхняя, правая верхняя, левая нижняя, правая нижняя
        (left, bottom + half_h, left + half_w, bottom + height),
        (left + half_w, bottom + half_h, left + width, bottom + height),
        (left, bottom, left + half_w, bottom + half_h),
        (left + half_w, bottom, left + width, bottom + half_h),
    ]
    points = _text_points(page)
    if not points:
        return [quadrants[0]]  # текст не распознан — берём обычное место наклейки
    found = [q for q in quadrants if any(q[0] <= x <= q[2] and q[1] <= y <= q[3] for x, y in points)]
    return found or [quadrants[0]]


def _place(target: PageObject, page: PageObject, region, x: float, y: float, w: float, h: float) -> None:
    """Вписать наклейку в прямоугольник (x, y, w, h) на целевой странице, по центру, сохраняя пропорции."""
    x0, y0, x1, y1 = region
    scale = min(w / (x1 - x0), h / (y1 - y0))
    dx = x + (w - (x1 - x0) * scale) / 2
    dy = y + (h - (y1 - y0) * scale) / 2
    target.merge_transformed_page(page, Transformation().translate(-x0, -y0).scale(scale, scale).translate(dx, dy))


ORDER_IN_NAME = re.compile(r"(?:^|[^0-9])W_(\d{6,})", re.IGNORECASE)


def order_number(name: str) -> str | None:
    """Номер заказа из имени файла Kaspi: W_1145092664.pdf, W_1145092664-2.pdf (копия при повторной загрузке)."""
    match = ORDER_IN_NAME.search(name or "")
    return match.group(1) if match else None


def _raw(obj) -> bytes:
    obj = obj.get_object()
    if isinstance(obj, ArrayObject):
        return b"".join(_raw(o) for o in obj)
    return getattr(obj, "_data", b"") or b""


def page_fingerprint(page: PageObject) -> str:
    """Отпечаток страницы: рисунок страницы и её картинки (штрихкод). Без расшифровки текста — имена не читаем."""
    digest = hashlib.sha256()
    if "/Contents" in page:
        digest.update(_raw(page["/Contents"]))
    xobjects = (page.get("/Resources") or {}).get("/XObject") or {}
    for key in sorted(xobjects):
        form = xobjects[key].get_object()
        digest.update(getattr(form, "_data", b"") or b"")
        for inner in sorted(((form.get("/Resources") or {}).get("/XObject") or {})):
            digest.update(getattr(form["/Resources"]["/XObject"][inner].get_object(), "_data", b"") or b"")
    return digest.hexdigest()[:32]


@dataclass
class Built:
    pdf: bytes
    count: int  # сколько наклеек (или страниц для «просто объединить») в файле
    skipped: int = 0  # сколько пропущено как уже напечатанные
    keys: list[str] = field(default_factory=list)  # что запомнить как напечатанное


def merge(files: list[bytes], layout: str = "75x120") -> tuple[bytes, int]:
    """Собрать накладные в один PDF по выбранной раскладке. Возвращает (PDF, сколько наклеек)."""
    built = build([("", f) for f in files], layout)
    return built.pdf, built.count


def build(files: list[tuple[str, bytes]], layout: str = "75x120", skip: set[str] | None = None) -> Built:
    """Собрать накладные. files — (имя файла, содержимое).

    skip — ключи уже напечатанных накладных: «order:<номер заказа>» (из имени W_….pdf) или «page:<отпечаток>».
    Если skip передан, такие накладные (и повторы внутри этой же пачки) в файл не попадают.
    """
    if layout not in LAYOUTS:
        raise WaybillError("Неизвестный вариант печати")
    if not files:
        raise WaybillError("Добавьте хотя бы одну накладную")
    if sum(len(f) for _, f in files) > MAX_BYTES:
        raise WaybillError(f"Слишком много за раз: до {MAX_FILES} файлов и до 30 МБ")
    files = unpack_named(files)
    if len(files) > MAX_FILES or sum(len(f) for _, f in files) > MAX_BYTES:
        raise WaybillError(f"Слишком много за раз: до {MAX_FILES} файлов и до 30 МБ")

    dedupe = skip is not None
    seen = set(skip or ())
    keys: list[str] = []
    skipped = 0
    pages: list[PageObject] = []
    for n, (name, data) in enumerate(files, start=1):
        if not data.startswith(b"%PDF"):
            raise WaybillError(f"Файл №{n} — не PDF")
        try:
            file_pages = list(PdfReader(io.BytesIO(data)).pages)
        except Exception:
            raise WaybillError(f"Файл №{n} не открывается как PDF") from None
        order = order_number(name)
        file_keys: list[str] = []
        if order:
            file_keys.append(f"order:{order}")
        if dedupe:
            prints = [f"page:{page_fingerprint(p)}" for p in file_pages]
            # Файл заказа целиком уже был — пропускаем; иначе пропускаем отдельные повторившиеся страницы.
            if order and f"order:{order}" in seen:
                skipped += len(file_pages)
                continue
            kept = []
            for page, key in zip(file_pages, prints):
                if key in seen:
                    skipped += 1
                    continue
                seen.add(key)
                file_keys.append(key)
                kept.append(page)
            if not kept:
                continue
            file_pages = kept
            seen.update(file_keys)
        keys.extend(file_keys)
        pages.extend(file_pages)

    if dedupe and not pages:
        return Built(b"", 0, skipped, [])

    writer = PdfWriter()
    if LAYOUTS[layout] is None:  # просто объединить файлы, страницы как есть
        for page in pages:
            writer.add_page(page)
        out = io.BytesIO(); writer.write(out)
        return Built(out.getvalue(), len(pages), skipped, keys)

    (page_w_mm, page_h_mm), (cols, rows) = LAYOUTS[layout]
    page_w, page_h = page_w_mm * MM, page_h_mm * MM
    per_page = cols * rows
    margin = CELL_MARGIN if per_page > 1 or page_w_mm == 210 else 0
    cell_w = (page_w - margin * (cols + 1)) / cols
    cell_h = (page_h - margin * (rows + 1)) / rows

    count, target = 0, None
    for page in pages:
        for region in label_regions(page):
            slot = count % per_page
            if slot == 0:
                target = writer.add_blank_page(width=page_w, height=page_h)
            col, row = slot % cols, slot // cols  # слева направо, сверху вниз
            x = margin + col * (cell_w + margin)
            y = page_h - margin - (row + 1) * cell_h - row * margin
            _place(target, page, region, x, y, cell_w, cell_h)
            count += 1
    out = io.BytesIO()
    writer.write(out)
    return Built(out.getvalue(), count, skipped, keys)
