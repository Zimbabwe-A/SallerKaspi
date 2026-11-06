"""Накладные Kaspi: много файлов → один PDF для термопринтера (по одной наклейке на страницу).

Kaspi отдаёт накладную как лист A4, на котором наклейка занимает четверть листа (обычно левую верхнюю;
если на листе несколько наклеек — они в других четвертях). Мы находим на каждом листе четверти с текстом,
вырезаем их и кладём по одной на страницу нужного размера (по умолчанию 75×120 мм), подряд.

В накладных есть имена и адреса покупателей, поэтому ничего не сохраняем на диск: всё в памяти.
"""

import io

from pypdf import PageObject, PdfReader, PdfWriter, Transformation

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


def _labels(files: list[bytes]):
    """Все наклейки по порядку: (страница-источник, прямоугольник наклейки на ней)."""
    for n, data in enumerate(files, start=1):
        if not data.startswith(b"%PDF"):
            raise WaybillError(f"Файл №{n} — не PDF")
        try:
            reader = PdfReader(io.BytesIO(data))
        except Exception:
            raise WaybillError(f"Файл №{n} не открывается как PDF") from None
        for page in reader.pages:
            for region in label_regions(page):
                yield page, region


def _place(target: PageObject, page: PageObject, region, x: float, y: float, w: float, h: float) -> None:
    """Вписать наклейку в прямоугольник (x, y, w, h) на целевой странице, по центру, сохраняя пропорции."""
    x0, y0, x1, y1 = region
    scale = min(w / (x1 - x0), h / (y1 - y0))
    dx = x + (w - (x1 - x0) * scale) / 2
    dy = y + (h - (y1 - y0) * scale) / 2
    target.merge_transformed_page(page, Transformation().translate(-x0, -y0).scale(scale, scale).translate(dx, dy))


def merge(files: list[bytes], layout: str = "75x120") -> tuple[bytes, int]:
    """Собрать накладные в один PDF по выбранной раскладке. Возвращает (PDF, сколько наклеек)."""
    if layout not in LAYOUTS:
        raise WaybillError("Неизвестный вариант печати")
    if not files:
        raise WaybillError("Добавьте хотя бы одну накладную")
    if len(files) > MAX_FILES or sum(len(f) for f in files) > MAX_BYTES:
        raise WaybillError(f"Слишком много за раз: до {MAX_FILES} файлов и до 30 МБ")
    writer = PdfWriter()

    if LAYOUTS[layout] is None:  # просто объединить файлы, страницы как есть
        count = 0
        for n, data in enumerate(files, start=1):
            if not data.startswith(b"%PDF"):
                raise WaybillError(f"Файл №{n} — не PDF")
            try:
                for page in PdfReader(io.BytesIO(data)).pages:
                    writer.add_page(page)
                    count += 1
            except WaybillError:
                raise
            except Exception:
                raise WaybillError(f"Файл №{n} не открывается как PDF") from None
        out = io.BytesIO(); writer.write(out)
        return out.getvalue(), count

    (page_w_mm, page_h_mm), (cols, rows) = LAYOUTS[layout]
    page_w, page_h = page_w_mm * MM, page_h_mm * MM
    per_page = cols * rows
    margin = CELL_MARGIN if per_page > 1 or page_w_mm == 210 else 0
    cell_w = (page_w - margin * (cols + 1)) / cols
    cell_h = (page_h - margin * (rows + 1)) / rows

    count, target = 0, None
    for page, region in _labels(files):
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
    return out.getvalue(), count
