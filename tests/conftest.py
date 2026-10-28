from pathlib import Path

import pytest

from tests import factories


@pytest.fixture
def rfp_docx(tmp_path: Path) -> Path:
    return factories.build_rfp_docx(tmp_path / "rfp.docx")


@pytest.fixture
def questionnaire_xlsx(tmp_path: Path) -> Path:
    return factories.build_questionnaire_xlsx(tmp_path / "questionnaire.xlsx")


@pytest.fixture
def unicode_font() -> None:
    if factories.find_unicode_font() is None:
        pytest.skip("no TrueType font with Cyrillic glyphs on this machine")
