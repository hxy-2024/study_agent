import json
from pathlib import Path

from app.domain.local_settings.schemas import LocalAISettings, LocalAISettingsResponse, LocalAISettingsUpdate


def load_local_ai_settings(*, path: str | Path) -> LocalAISettings:
    settings_path = Path(path)
    if not settings_path.exists():
        return LocalAISettings()
    payload = json.loads(settings_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return LocalAISettings()
    return LocalAISettings.model_validate(payload)


def save_local_ai_settings(
    update: LocalAISettingsUpdate,
    *,
    path: str | Path,
) -> LocalAISettingsResponse:
    settings_path = Path(path)
    current = load_local_ai_settings(path=settings_path)
    update_payload = update.model_dump(exclude_unset=True)
    next_settings = current.model_copy(update={key: value for key, value in update_payload.items() if value is not None})
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(next_settings.model_dump(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return next_settings.to_response()
