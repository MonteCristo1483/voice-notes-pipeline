"""Rendering is deterministic and should never produce empty sections."""

from voice_notes.render import (
    normalize_tags,
    render_personal_long,
    render_personal_short,
    render_work,
)


def test_work_note_omits_empty_sections_and_puts_tags_last():
    note = render_work(
        {
            "essence": "Обсудили запуск.",
            "topics": [{"title": "Запуск", "points": ["Релиз в пятницу."]}],
            "decisions": [],
            "tasks": [],
            "questions": [],
            "facts": [],
            "materials": [],
            "tags": ["Проект 1", "релиз"],
        }
    )

    assert "## Суть" in note
    assert "### Запуск" in note
    assert "## Решения и обоснования" not in note
    assert "## Задачи" not in note
    assert note.endswith("#проект_1 #релиз")


def test_tasks_include_owner_and_due_once():
    note = render_work(
        {
            "essence": "Планёрка.",
            "tasks": [
                {"task": "Закрыть оплату", "owner": "Миша", "due": "пятница"},
                {"task": "Миша закрывает оплату", "owner": "Миша", "due": ""},
                {"task": "Написать отчёт", "owner": "я", "due": "нет срока"},
            ],
            "tags": ["планёрка"],
        }
    )

    assert "- [ ] Закрыть оплату — Миша, срок: пятница" in note
    assert "- [ ] Миша закрывает оплату" in note
    assert "Написать отчёт" in note
    assert "нет срока" not in note


def test_decisions_strip_redundant_reason_prefix():
    note = render_work(
        {
            "essence": "Созвон.",
            "decisions": [{"decision": "Перенести релиз", "reason": "потому что не готово"}],
            "tags": ["релиз"],
        }
    )

    assert "- Перенести релиз — не готово" in note


def test_personal_short_renders_three_blocks():
    note = render_personal_short(
        {
            "essence": "Сделать сервис консультаций.",
            "facts": ["1000 ₽ за 1,5 часа"],
            "actions": ["Собрать лендинг"],
            "tags": ["нейросети"],
        }
    )

    assert note.startswith("**Суть.** Сделать сервис консультаций.")
    assert "**Факты.**\n- 1000 ₽ за 1,5 часа" in note
    assert "**Что сделать.**\n- Собрать лендинг" in note
    assert note.endswith("#нейросети")


def test_personal_long_drops_bare_numbers_and_cjk():
    note = render_personal_long(
        {
            "essence": "Идея проекта.",
            "main": ["Главная мысль"],
            "actions": [],
            "facts": ["120", "7 тысяч рублей за операцию", "44 元"],
            "tags": [],
        }
    )

    assert "120" not in note
    assert "7 тысяч рублей за операцию" in note
    assert "元" not in note


def test_tags_are_normalized_and_deduplicated():
    assert normalize_tags(["#Проект 1", "проект_1", "AI", "  "]) == ["#проект_1", "#ai"]
