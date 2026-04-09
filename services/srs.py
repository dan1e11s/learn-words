from __future__ import annotations

from datetime import datetime, timedelta


SRS_INTERVALS = [1, 3, 7, 14, 30, 60, 120]


def progress_gain(question_type: str, times_tested: int) -> int:
    base = 5 if question_type == "input" else 3
    penalty = min(4, times_tested // 10)
    return max(1, base - penalty)


def next_interval_days(current_interval_days: int) -> int:
    if current_interval_days in SRS_INTERVALS:
        idx = SRS_INTERVALS.index(current_interval_days)
        if idx + 1 < len(SRS_INTERVALS):
            return SRS_INTERVALS[idx + 1]
        return SRS_INTERVALS[-1]
    return 1


def compute_next_review(
    was_already_mastered: bool,
    current_interval_days: int,
    is_correct: bool,
) -> tuple[int | None, datetime | None]:
    now = datetime.utcnow()
    if not is_correct:
        return None, None

    if was_already_mastered:
        new_interval = next_interval_days(current_interval_days)
    else:
        new_interval = SRS_INTERVALS[0]

    return new_interval, now + timedelta(days=new_interval)
