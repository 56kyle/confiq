"""ClickSource: reads explicitly-set Click parameters as raw bindings (design_d §10.3, ADR 0027)."""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Sequence
from typing import TYPE_CHECKING
from typing import Any
from typing import ClassVar
from typing import cast
from typing import get_args
from typing import get_origin
from typing import get_type_hints

from typing_extensions import Annotated

from confiq._cli import ConfigBind
from confiq._imports import import_optional
from confiq.source._base_source import BaseSource
from confiq.source._source import RawBinding


if TYPE_CHECKING:
    from collections.abc import Callable

    from click import Context
    from click import Parameter


_DEFAULT_PARAMETER_SOURCE_NAMES = frozenset({"DEFAULT", "DEFAULT_MAP"})


class ClickSource(BaseSource):
    """Reads explicitly-set Click parameters from the active Context as an eager snapshot (ADR 0032).

    A binding source (ADR 0027, 0049): it surfaces raw parameter names + markers via
    raw_bindings(), which the resolver maps to config paths against the schema path table, rather
    than emitting config-path data. Only parameters the user explicitly set participate, detected
    via Context.get_parameter_source(). The snapshot is captured at construction — no Context
    reference survives __init__ — so binding replays deterministically (ADR 0032).

    Requires click (confiq[cli]).
    """

    _NAME: ClassVar[str] = "cli:click"
    _FRAMEWORK: ClassVar[str] = "Click"
    _EXTRA_MODULE: ClassVar[str] = "click"

    def __init__(self, *, profile: str | None = None) -> None:
        """Capture the explicitly-set parameters of the active command as immutable RawBindings.

        Raises ImportError if the [cli] extra is missing, and RuntimeError if constructed outside
        an active command invocation.
        """
        _ = import_optional(self._EXTRA_MODULE, extra="cli")
        self._bindings: tuple[RawBinding, ...] = _capture_bindings(_current_click_context(self._FRAMEWORK))
        self.profile = profile

    @property
    def name(self) -> str:
        return self._NAME

    def raw_bindings(self) -> Sequence[RawBinding]:
        return self._bindings


def _current_click_context(framework: str) -> Context:
    """Return the active Click context, or raise RuntimeError naming the framework (ADR 0032)."""
    click = import_optional("click", extra="cli")
    try:
        return cast("Context", click.get_current_context())  # pyright: ignore[reportAny]  # optional-dep module attr is Any
    except RuntimeError as error:
        raise RuntimeError(
            f"{framework}Source must be constructed inside an active {framework} command "
            f"invocation; no active context was found.",
        ) from error


def _capture_bindings(ctx: Context) -> tuple[RawBinding, ...]:
    """Snapshot every explicitly-set parameter of the command as a RawBinding (ADR 0027, 0032)."""
    callback_binds = _callback_binds(ctx.command.callback)
    bindings: list[RawBinding] = []
    for param in ctx.command.params:
        name = param.name
        if name is None:
            continue
        parameter_source = ctx.get_parameter_source(name)
        if parameter_source is None or parameter_source.name in _DEFAULT_PARAMETER_SOURCE_NAMES:
            continue
        value: object = ctx.params.get(name)
        bindings.append(RawBinding(name, value, _marker_for(param, name, callback_binds)))
    return tuple(bindings)


def _marker_for(param: Parameter, name: str, callback_binds: Mapping[str, ConfigBind]) -> ConfigBind | None:
    """Resolve a parameter's marker: a generated option's confiq_path wins over a callback ConfigBind (ADR 0032)."""
    confiq_path = getattr(param, "confiq_path", None)
    if isinstance(confiq_path, str):
        return ConfigBind(confiq_path)
    return callback_binds.get(name)


def _callback_binds(callback: Callable[..., Any] | None) -> dict[str, ConfigBind]:
    """Extract each parameter's ConfigBind from the command callback's annotations (ADR 0027).

    Degrades to no binds (convention for all) when there is no callback or its annotations cannot
    be resolved, so an unresolved forward reference never blocks a plain CLI.
    """
    if callback is None:
        return {}
    try:
        hints: dict[str, object] = get_type_hints(callback, include_extras=True)
    except Exception:  # noqa: BLE001  # unresolved annotation degrades to convention, never blocks
        return {}
    binds: dict[str, ConfigBind] = {}
    for name, hint in hints.items():
        bind = _config_bind_in(hint)
        if bind is not None:
            binds[name] = bind
    return binds


def _config_bind_in(hint: object) -> ConfigBind | None:
    """Return the ConfigBind in an Annotated hint's extras, or None."""
    if get_origin(hint) is Annotated:
        extras = cast("tuple[object, ...]", get_args(hint)[1:])
        for extra in extras:
            if isinstance(extra, ConfigBind):
                return extra
    return None
