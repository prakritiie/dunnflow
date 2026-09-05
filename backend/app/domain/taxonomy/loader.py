from __future__ import annotations
import functools, hashlib, pathlib
import yaml
from app.core.config import settings
from app.domain.models.core import FailureClass


def _sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]


@functools.lru_cache(maxsize=1)
def load_taxonomy() -> tuple[dict[str, FailureClass], dict[str, str], str, str]:
    """Returns (classes_by_code, families, declared_version, config_sha)."""
    path = pathlib.Path(settings.CONFIG_DIR) / "taxonomy.yaml"
    raw = yaml.safe_load(path.read_text())
    classes = {c["code"]: FailureClass(**c) for c in raw["classes"]}
    return classes, raw["families"], raw["version"], _sha(path)


def taxonomy() -> dict[str, FailureClass]:
    return load_taxonomy()[0]


def taxonomy_version() -> str:
    _, _, ver, sha = load_taxonomy()
    return f"{ver}+{sha}"


def get_class(code: str) -> FailureClass:
    return taxonomy()[code]


def is_known(code: str) -> bool:
    return code in taxonomy()
