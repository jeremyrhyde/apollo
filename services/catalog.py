"""Load and validate the YAML catalog in CONFIG_DIR.

Every file is loaded independently. A file that is missing or invalid is
reported in `Catalog.errors` (surfaced at /api/health and in Settings) and
replaced by its empty default, so one bad file never takes the server down or
hides the others.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError

from schemas.config import (
    ApolloFile,
    Exercise,
    ExercisesFile,
    SelfcareCategory,
    SelfcareFile,
    SelfcareType,
)


@dataclass(frozen=True)
class Catalog:
    apollo: ApolloFile
    exercises: ExercisesFile
    selfcare: SelfcareFile
    errors: tuple[str, ...] = ()

    def exercise(self, key: str) -> Exercise | None:
        return next((e for e in self.exercises.exercises if e.key == key), None)

    def fields_for(self, metric_type: str) -> list[str]:
        return list(self.exercises.metric_types[metric_type].fields)

    def exercises_by_group(self) -> dict[str, list[Exercise]]:
        """Exercises under each muscle group, in muscle_groups order.

        An exercise with several groups appears under each of them.
        """
        out: dict[str, list[Exercise]] = {g: [] for g in self.exercises.muscle_groups}
        for ex in self.exercises.exercises:
            for group in ex.muscle_groups:
                out[group].append(ex)
        return out

    def category(self, key: str) -> SelfcareCategory | None:
        return next((c for c in self.selfcare.categories if c.key == key), None)

    def selfcare_type(self, category_key: str, type_key: str) -> SelfcareType | None:
        cat = self.category(category_key)
        if cat is None:
            return None
        return next((t for t in cat.types if t.key == type_key), None)


_FILES: dict[str, tuple[str, type[BaseModel]]] = {
    "apollo": ("apollo.yaml", ApolloFile),
    "exercises": ("exercises.yaml", ExercisesFile),
    "selfcare": ("selfcare.yaml", SelfcareFile),
}


class _UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader that rejects a mapping (at any nesting level) with a repeated key.

    PyYAML otherwise silently keeps the last value, which would hide a typo'd
    duplicate in the YAML instead of reporting it.
    """

    def construct_mapping(self, node, deep=False):
        seen: set[object] = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                line = key_node.start_mark.line + 1
                raise yaml.constructor.ConstructorError(
                    problem=f"duplicate key {key!r} at line {line}"
                )
            seen.add(key)
        return super().construct_mapping(node, deep)


def _describe(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        parts = []
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"])
            msg = err["msg"].removeprefix("Value error, ")
            parts.append(f"{loc}: {msg}" if loc else msg)
        return "; ".join(parts)
    return str(exc).replace("\n", " ")


def load_catalog(config_dir: str | Path) -> Catalog:
    errors: list[str] = []
    parsed: dict[str, BaseModel] = {}
    for attr, (filename, model) in _FILES.items():
        path = Path(config_dir) / filename
        try:
            raw = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
            if raw is None:
                raw = {}
            if not isinstance(raw, dict):
                raise ValueError("top level must be a mapping")
            parsed[attr] = model.model_validate(raw)
        except FileNotFoundError:
            errors.append(f"{filename}: file not found")
            parsed[attr] = model()
        except (yaml.YAMLError, ValidationError, ValueError) as exc:
            errors.append(f"{filename}: {_describe(exc)}")
            parsed[attr] = model()
    return Catalog(errors=tuple(errors), **parsed)  # type: ignore[arg-type]
