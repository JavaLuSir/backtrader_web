from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import backtrader as bt


def list_strategies(strategies_dir: Path) -> list[dict]:
    strategies_dir = strategies_dir.resolve()
    if not strategies_dir.exists():
        return []

    items: list[dict] = []
    for path in sorted(strategies_dir.glob("*.py")):
        if path.name.startswith("_") or path.name == "__init__.py":
            continue
        items.append({"id": path.name, "name": path.stem})
    return items


def _safe_strategy_path(strategies_dir: Path, strategy_id: str) -> Path:
    base = strategies_dir.resolve()
    path = (base / strategy_id).resolve()

    if path.suffix.lower() != ".py":
        raise ValueError("strategy_id must be a .py file under strategies/")
    if base not in path.parents:
        raise ValueError("invalid strategy path")
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(strategy_id)
    return path


def _load_module_from_file(path: Path) -> ModuleType:
    module_name = f"btweb_strategy_{path.stem}_{abs(hash(str(path)))}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if not spec or not spec.loader:
        raise RuntimeError(f"failed to load strategy module: {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_strategy_class(strategies_dir: Path, strategy_id: str) -> type[bt.Strategy]:
    path = _safe_strategy_path(strategies_dir, strategy_id)
    module = _load_module_from_file(path)

    cls = getattr(module, "STRATEGY_CLASS", None)
    if cls is None and hasattr(module, "get_strategy"):
        cls = module.get_strategy()

    if cls is None:
        candidates: list[type[bt.Strategy]] = []
        for obj in vars(module).values():
            if (
                isinstance(obj, type)
                and issubclass(obj, bt.Strategy)
                and obj is not bt.Strategy
                and getattr(obj, "__module__", None) == module.__name__
            ):
                candidates.append(obj)
        if not candidates:
            raise ValueError(
                f"{strategy_id} 内未找到 bt.Strategy 子类；请定义 STRATEGY_CLASS=你的策略类"
            )
        cls = sorted(candidates, key=lambda c: c.__name__)[0]

    if not isinstance(cls, type) or not issubclass(cls, bt.Strategy):
        raise ValueError(f"{strategy_id} 的 STRATEGY_CLASS 不是 bt.Strategy 子类")

    return cls

