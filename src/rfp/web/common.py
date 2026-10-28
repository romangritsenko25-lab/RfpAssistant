"""Shared pieces of the HTML layer: templates, filters, the login redirect and flash notices."""

import re
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlencode

from fastapi import Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from rfp.api.deps import Conn
from rfp.auth import User, current_user
from rfp.models import Location

WEB_DIR = Path(__file__).parent
STATIC_DIR = WEB_DIR / "static"

templates = Jinja2Templates(directory=WEB_DIR / "templates")

# Flash messages travel as a short code in the query string, never as free text.
NOTICES = {
    "doc_uploaded": "Документ «{name}» загружен и проиндексирован.",
    "doc_unchanged": "Документ «{name}» не изменился, переиндексация не нужна.",
    "doc_deleted": "Документ «{name}» удалён из базы знаний.",
    "doc_missing": "Документ «{name}» не найден.",
    "reindexed": "Синхронизация завершена: {name}.",
}

ITEM_STATUS = {
    "pending": ("Ожидает", "outline"),
    "answered": ("Ответ готов", "success"),
    "approved": ("Одобрен", "success"),
    "edited": ("Изменён", "success"),
    "needs_review": ("На проверку", "warning"),
    "no_data": ("Нет данных", ""),
}
JOB_STATUS = {
    "queued": ("В очереди", "outline"),
    "running": ("Выполняется", "info"),
    "done": ("Готово", "success"),
    "failed": ("Ошибка", "error"),
}


_RU_MESSAGES: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pattern, re.DOTALL), template)
    for pattern, template in (
        (
            r"(\d+) model citation\(s\) rejected: not found in the fragments\.",
            "Отклонено цитат модели: {0} (не найдены во фрагментах).",
        ),
        (r"Unsupported file type '(.*)'; use (.*)\.", "Неподдерживаемый тип файла «{0}»; допустимы: {1}."),
        (r"The file is empty\.", "Файл пустой."),
        (r"The file is larger than (\d+) MB\.", "Файл больше {0} МБ."),
        (r"No questions were found in the file\.", "В файле не найдено вопросов."),
        (r"Cannot read questions from '(.*)': (.*)", "Не удалось прочитать вопросы из «{0}»: {1}"),
        (r"'(.*)' is not a column letter\.", "«{0}» — не буква колонки."),
        (r"Sheet '(.*)' not found; available: (.*)\.", "Лист «{0}» не найден; есть: {1}."),
        (
            r"Cannot find the question column: .*Specify the columns manually\.",
            "Не удалось найти колонку с вопросами: в первых 10 строках нет заголовка вроде "
            "«Вопрос», «Question» или «Сұрақ». Укажите колонки вручную.",
        ),
        (
            r"The answer column must differ from the question column\.",
            "Колонка ответов должна отличаться от колонки вопросов.",
        ),
        (
            r"The number column must differ from the answer column\.",
            "Колонка номеров должна отличаться от колонки ответов.",
        ),
        (
            r"The header row must be a non-negative number\.",
            "Строка заголовка должна быть неотрицательным числом.",
        ),
        (r"Cannot write the answers into the file: (.*)", "Не удалось записать ответы в файл: {0}"),
        (
            r"Export check failed: (.*)",
            "Самопроверка выгрузки не прошла, файл не отдан. Причина: {0}",
        ),
        (
            r"File names starting with 'REF-' are reserved for reviewed answers\.",
            "Имена файлов, начинающиеся с «REF-», зарезервированы для проверенных ответов.",
        ),
        (r"Cannot index '(.*)': (.*)", "Не удалось проиндексировать «{0}»: {1}"),
        (
            r"Nothing to change: give text, status or note\.",
            "Нечего менять: укажите текст, статус или примечание.",
        ),
        (r"The answer text must not be empty\.", "Текст ответа не должен быть пустым."),
        (r"The question has not been processed yet\.", "Вопрос ещё не обработан."),
        (
            r"Only an approved or edited answer can be saved as a reference\.",
            "Эталоном можно сохранить только одобренный или изменённый ответ.",
        ),
        (r"Job (\d+) not found\.", "Опросник №{0} не найден."),
        (r"Question (.*) not found in job (\d+)\.", "Вопрос {0} не найден в опроснике №{1}."),
        (r"Document (.*) not found\.", "Документ {0} не найден."),
        (r"The job is still being processed\.", "Опросник ещё обрабатывается."),
    )
)


def ru(message: str | None) -> str:
    """Russian text for a known service message; an unknown one is returned unchanged."""
    if not message:
        return ""
    for pattern, template in _RU_MESSAGES:
        match = pattern.fullmatch(message)
        if match:
            groups = match.groups()
            if pattern.pattern.startswith("Export check failed"):
                groups = ("; ".join(_ru_problem(p) for p in groups[0].split(" | ")),)
            return template.format(*groups)
    return message


_RU_PROBLEMS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pattern), template)
    for pattern, template in (
        (r"sheets differ: expected (.*), got (.*)", "набор листов изменился: было {0}, стало {1}"),
        (r"sheet '(.*)': size is (\S+), expected (\S+)", "лист «{0}»: размер {1}, ожидался {2}"),
        (r"sheet '(.*)': the number of formulas changed", "лист «{0}»: изменилось число формул"),
        (r"sheet '(.*)': merged cells changed", "лист «{0}»: изменились объединённые ячейки"),
        (r"sheet '(.*)': drop-down lists changed", "лист «{0}»: изменились выпадающие списки"),
        (r"sheet '(.*)', cell (\S+): content changed", "лист «{0}», ячейка {1}: содержимое изменилось"),
        (r"sheet '(.*)': (.*) is not at (\S+)", "лист «{0}»: {1} не на своём месте ({2})"),
        (r"the document has (\d+) blocks, expected (\d+)", "в документе {0} блоков, ожидалось {1}"),
        (r"block (\d+): text differs from the expected one", "блок {0}: текст отличается от ожидаемого"),
        (r"table in block (\d+): the number of rows changed", "таблица в блоке {0}: изменилось число строк"),
        (
            r"table in block (\d+), row (\d+): cells changed",
            "таблица в блоке {0}, строка {1}: изменились ячейки",
        ),
        (
            r"table in block (\d+), row (\d+), column (\d+): text or answer differs from the expected one",
            "таблица в блоке {0}, строка {1}, колонка {2}: текст или ответ отличается от ожидаемого",
        ),
    )
)


def _ru_problem(message: str) -> str:
    for pattern, template in _RU_PROBLEMS:
        match = pattern.fullmatch(message)
        if match:
            return template.format(*match.groups())
    return message


def _datetime(value: datetime | None) -> str:
    return value.strftime("%d.%m.%Y %H:%M") if value else "—"


def _percent(value: float | None) -> str:
    return "—" if value is None else f"{round(value * 100)}%"


def _seconds(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f} с".replace(".", ",")


def _cost(value: float | None) -> str:
    return "—" if value is None else f"${value:.4f}"


def location_label(location: Location) -> str:
    """Where the question sits in the source file, in words."""
    parts: list[str] = []
    if location.sheet is not None:
        parts.append(f"лист «{location.sheet}»")
    if location.row is not None:
        parts.append(f"строка {location.row}")
    if location.page is not None:
        parts.append(f"стр. {location.page}")
    if location.line is not None:
        parts.append(f"строка {location.line}")
    if location.table_row is not None:
        parts.append(f"таблица, строка {location.table_row + 1}")
    elif location.block is not None:
        parts.append(f"блок {location.block + 1}")
    return ", ".join(parts) or "—"


templates.env.filters.update(
    dt=_datetime, ru=ru, pct=_percent, secs=_seconds, cost=_cost, location_label=location_label
)
templates.env.globals.update(ITEM_STATUS=ITEM_STATUS, JOB_STATUS=JOB_STATUS)


def render(
    request: Request, name: str, user: User | None = None, status_code: int = 200, **context: Any
) -> Response:
    notice_code = request.query_params.get("notice")
    notice = None
    if notice_code in NOTICES:
        notice = NOTICES[notice_code].format(name=request.query_params.get("name", "")[:200])
    context |= {"user": user, "notice": context.get("notice", notice)}
    return templates.TemplateResponse(request, name, context, status_code=status_code)


def redirect(url: str, notice: str | None = None, name: str = "") -> RedirectResponse:
    """Post/redirect/get; ``notice`` is a key of :data:`NOTICES`."""
    if notice:
        url = f"{url}?{urlencode({'notice': notice, 'name': name})}"
    return RedirectResponse(url, status_code=303)


def safe_next(target: str | None) -> str:
    """Only local paths: a login redirect must not leave the site."""
    if target and target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return target
    return "/jobs"


def web_user(request: Request, conn: Conn) -> User:
    """The logged-in user; anyone else goes to the login page (HTMX: ``HX-Redirect``), not a JSON 401."""
    try:
        return current_user(request, conn)
    except HTTPException as exc:
        if request.headers.get("HX-Request"):
            raise HTTPException(200, "Login required", headers={"HX-Redirect": "/login"}) from exc
        target = request.url.path + (f"?{request.url.query}" if request.url.query else "")
        location = "/login" if request.method != "GET" else f"/login?{urlencode({'next': target})}"
        raise HTTPException(303, "Login required", headers={"Location": location}) from exc


WebUser = Annotated[User, Depends(web_user)]
