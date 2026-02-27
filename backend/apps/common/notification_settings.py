"""알림 설정 비트마스크 유틸."""

from collections.abc import Mapping

NOTIFICATION_KEY_SCHEDULE_D7 = "schedule_d7"
NOTIFICATION_KEY_SCHEDULE_D3 = "schedule_d3"
NOTIFICATION_KEY_NEW_ANNOUNCE = "new_announce"
NOTIFICATION_KEY_ANSWER_COMPLETE = "answer_complete"

NOTIFICATION_BIT_SCHEDULE_D7 = 1 << 0
NOTIFICATION_BIT_SCHEDULE_D3 = 1 << 1
NOTIFICATION_BIT_NEW_ANNOUNCE = 1 << 2
NOTIFICATION_BIT_ANSWER_COMPLETE = 1 << 3

NOTIFICATION_SETTING_BITS: dict[str, int] = {
    NOTIFICATION_KEY_SCHEDULE_D7: NOTIFICATION_BIT_SCHEDULE_D7,
    NOTIFICATION_KEY_SCHEDULE_D3: NOTIFICATION_BIT_SCHEDULE_D3,
    NOTIFICATION_KEY_NEW_ANNOUNCE: NOTIFICATION_BIT_NEW_ANNOUNCE,
    NOTIFICATION_KEY_ANSWER_COMPLETE: NOTIFICATION_BIT_ANSWER_COMPLETE,
}

NOTIFICATION_FULL_MASK = (
    NOTIFICATION_BIT_SCHEDULE_D7
    | NOTIFICATION_BIT_SCHEDULE_D3
    | NOTIFICATION_BIT_NEW_ANNOUNCE
    | NOTIFICATION_BIT_ANSWER_COMPLETE
)

DEFAULT_NOTIFICATION_SETTINGS: dict[str, bool] = {
    key: True for key in NOTIFICATION_SETTING_BITS
}
DEFAULT_NOTIFICATION_MASK = NOTIFICATION_FULL_MASK


def _coerce_mask(value: object | None) -> int:
    if isinstance(value, int):
        if value < 0:
            return DEFAULT_NOTIFICATION_MASK
        return value & NOTIFICATION_FULL_MASK

    if isinstance(value, str):
        raw = value.strip()
        if raw.isdigit():
            return int(raw) & NOTIFICATION_FULL_MASK

    return DEFAULT_NOTIFICATION_MASK


def decode_notification_settings(value: object | None) -> dict[str, bool]:
    """저장값(bitmask 또는 레거시 dict)을 bool 딕셔너리로 복원합니다."""
    if isinstance(value, Mapping):
        normalized = dict(DEFAULT_NOTIFICATION_SETTINGS)
        for key, default_value in DEFAULT_NOTIFICATION_SETTINGS.items():
            raw = value.get(key, default_value)
            normalized[key] = raw if isinstance(raw, bool) else default_value
        return normalized

    mask = _coerce_mask(value)
    return {
        key: bool(mask & bit)
        for key, bit in NOTIFICATION_SETTING_BITS.items()
    }


def encode_notification_settings(value: Mapping[str, object] | None) -> int:
    """bool 딕셔너리를 bitmask 정수로 인코딩합니다."""
    if not isinstance(value, Mapping):
        return DEFAULT_NOTIFICATION_MASK

    mask = 0
    for key, bit in NOTIFICATION_SETTING_BITS.items():
        default_value = DEFAULT_NOTIFICATION_SETTINGS[key]
        raw = value.get(key, default_value)
        is_enabled = raw if isinstance(raw, bool) else default_value
        if is_enabled:
            mask |= bit
    return mask


def is_notification_enabled(value: object | None, key: str) -> bool:
    if key not in DEFAULT_NOTIFICATION_SETTINGS:
        return True

    return decode_notification_settings(value)[key]

