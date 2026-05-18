class AlasConfigValidationError(ValueError):
    def __init__(self, code, detail=""):
        self.code = code
        self.detail = detail
        message = f"{code}: {detail}" if detail else code
        super().__init__(message)


REQUIRED_SECTION_PATHS = {
    "Alas": ("Emulator", "Error", "Optimization", "Storage"),
    "General": ("Storage",),
    "Restart": ("Scheduler", "Storage"),
    "Main": ("Scheduler", "Campaign", "Fleet", "Storage"),
    "Reward": ("Scheduler", "Reward", "Storage"),
}

REQUIRED_EMULATOR_KEYS = (
    "Serial",
    "PackageName",
    "ScreenshotMethod",
    "ControlMethod",
)
REQUIRED_SCHEDULER_KEYS = ("Enable", "NextRun", "Command")
MIN_SECTION_COUNT = 20
MIN_SCHEDULER_COUNT = 5


def _fail(code, detail=""):
    raise AlasConfigValidationError(code, detail)


def _require_dict(value, code, detail):
    if not isinstance(value, dict):
        _fail(code, detail)
    return value


def validate_alas_config(config_data):
    root = _require_dict(config_data, "root_not_object", "root")

    if len(root) < MIN_SECTION_COUNT:
        _fail("too_few_sections", str(len(root)))

    missing_sections = [
        section for section in REQUIRED_SECTION_PATHS if section not in root
    ]
    if missing_sections:
        _fail("missing_section", ", ".join(missing_sections))

    for section, required_children in REQUIRED_SECTION_PATHS.items():
        section_data = _require_dict(root.get(section), "invalid_section", section)
        missing_children = [
            child for child in required_children if child not in section_data
        ]
        if missing_children:
            _fail(
                "missing_group",
                f"{section}.{', '.join(missing_children)}",
            )
        for child in required_children:
            _require_dict(section_data.get(child), "invalid_group", f"{section}.{child}")

    emulator = root["Alas"]["Emulator"]
    missing_emulator_keys = [
        key for key in REQUIRED_EMULATOR_KEYS if key not in emulator
    ]
    if missing_emulator_keys:
        _fail("missing_emulator_key", ", ".join(missing_emulator_keys))

    storage_errors = []
    for section in REQUIRED_SECTION_PATHS:
        storage = root[section].get("Storage")
        if not isinstance(storage, dict) or not isinstance(storage.get("Storage"), dict):
            storage_errors.append(section)
    if storage_errors:
        _fail("invalid_storage", ", ".join(storage_errors))

    scheduler_count = 0
    scheduler_errors = []
    for section, section_data in root.items():
        if not isinstance(section_data, dict) or "Scheduler" not in section_data:
            continue
        scheduler = section_data.get("Scheduler")
        if not isinstance(scheduler, dict):
            scheduler_errors.append(section)
            continue
        scheduler_count += 1
        missing_scheduler_keys = [
            key for key in REQUIRED_SCHEDULER_KEYS if key not in scheduler
        ]
        if missing_scheduler_keys:
            scheduler_errors.append(
                f"{section}.{', '.join(missing_scheduler_keys)}"
            )
            continue
        if not isinstance(scheduler.get("Enable"), bool):
            scheduler_errors.append(f"{section}.Enable")
        if not isinstance(scheduler.get("NextRun"), str):
            scheduler_errors.append(f"{section}.NextRun")
        if not isinstance(scheduler.get("Command"), str) or not scheduler.get("Command"):
            scheduler_errors.append(f"{section}.Command")

    if scheduler_count < MIN_SCHEDULER_COUNT:
        _fail("too_few_schedulers", str(scheduler_count))
    if scheduler_errors:
        _fail("invalid_scheduler", ", ".join(scheduler_errors[:5]))

    return True
