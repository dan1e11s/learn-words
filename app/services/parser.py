from __future__ import annotations


def parse_words_batch(raw_text: str) -> tuple[list[tuple[str, str]], list[str]]:
    parsed: list[tuple[str, str]] = []
    errors: list[str] = []

    for idx, raw_line in enumerate(raw_text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        if " - " not in line:
            errors.append(f"Строка {idx}: нет разделителя ' - '")
            continue
        korean, russian = line.split(" - ", maxsplit=1)
        korean = korean.strip()
        russian = russian.strip()
        if not korean or not russian:
            errors.append(f"Строка {idx}: пустое слово или перевод")
            continue
        translations = [item.strip() for item in russian.split(",")]
        if any(not item for item in translations):
            errors.append(f"Строка {idx}: пустой перевод в списке через запятую")
            continue

        normalized_russian = ", ".join(dict.fromkeys(translations))
        parsed.append((korean, normalized_russian))

    return parsed, errors
