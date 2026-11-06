"""Накладные Kaspi: много файлов → один PDF для термопринтера (по одной наклейке на страницу).

Kaspi отдаёт накладную как лист A4, на котором наклейка занимает четверть листа (обычно левую верхнюю;
если на листе несколько наклеек — они в других четвертях). Мы находим на каждом листе четверти с текстом,
вырезаем их и кладём по одной на страницу нужного размера (по умолчанию 75×120 мм), подряд.

В накладных есть имена и адреса покупателей, поэтому ничего не сохраняем на диск: всё в памяти.
"""

import io

from pypdf import PageObject, PdfReader, PdfWriter, Transformation

MM = 72 / 25.4
SIZES = {"75x120": (75, 120), "100x150": (100, 150), "58x40": (58, 40)}
MAX_FILES = 200
MAX_BYTES = 30 * 1024 * 1024


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


def merge(files: list[bytes], size: str = "75x120") -> tuple[bytes, int]:
    """Собрать накладные в один PDF. Возвращает (PDF, сколько наклеек)."""
    if size not in SIZES:
        raise WaybillError("Неизвестный размер наклейки")
    if not files:
        raise WaybillError("Добавьте хотя бы одну накладную")
    if len(files) > MAX_FILES or sum(len(f) for f in files) > MAX_BYTES:
        raise WaybillError(f"Слишком много за раз: до {MAX_FILES} файлов и до 30 МБ")
    target_w, target_h = SIZES[size][0] * MM, SIZES[size][1] * MM
    writer = PdfWriter()
    count = 0
    for n, data in enumerate(files, start=1):
        if not data.startswith(b"%PDF"):
            raise WaybillError(f"Файл №{n} — не PDF")
        try:
            reader = PdfReader(io.BytesIO(data))
        except Exception:
            raise WaybillError(f"Файл №{n} не открывается как PDF") from None
        for page in reader.pages:
            for x0, y0, x1, y1 in label_regions(page):
                w, h = x1 - x0, y1 - y0
                scale = min(target_w / w, target_h / h)
                dx = (target_w - w * scale) / 2
                dy = (target_h - h * scale) / 2
                label = writer.add_blank_page(width=target_w, height=target_h)
                # Сдвигаем нужную четверть в начало координат, масштабируем, центрируем на наклейке.
                transform = Transformation().translate(-x0, -y0).scale(scale, scale).translate(dx, dy)
                label.merge_transformed_page(page, transform)
                label.mediabox.lower_left = (0, 0)
                label.mediabox.upper_right = (target_w, target_h)
                count += 1
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue(), count
