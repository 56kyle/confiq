"""ClickSource: reads explicitly-set Click parameters as raw bindings (design_d §10.3, ADR 0027)."""

from __future__ import annotations

import importlib
from collections.abc import Mapping
from collections.abc import Sequence
from typing import TYPE_CHECKING
from typing import Any
from typing import ClassVar
from typing import Protocol
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


_DEFAULT_PARAMETER_SOURCE_NAMES = frozenset({"DEFAULT", "DEFAULT_MAP"})
_CURRENT_CONTEXT_ATTRIBUTE = "get_current_context"
NO_ACTIVE_CONTEXT_MESSAGE_TEMPLATE = (
    "{framework}Source must be constructed inside an active {framework} command "
    "invocation; no active context was found."
)


class _ParameterLike(Protocol):
    """The parameter surface capture needs: a name."""

    @property
    def name(self) -> str | None: ...


class _ParameterSourceLike(Protocol):
    """The parameter-source surface capture needs: the enum member's name."""

    @property
    def name(self) -> str: ...


class _CommandLike(Protocol):
    """The command surface capture needs: its declared parameters and its callback."""

    @property
    def params(self) -> Sequence[_ParameterLike]: ...

    @property
    def callback(self) -> Callable[..., Any] | None: ...


class _CommandContextLike(Protocol):
    """The invocation-context surface capture needs, satisfied by both real and vendored Click.

    Typer >= 0.26 vendors its own Click fork, whose Context is structurally identical here but is
    not a click.Context subclass; capture is written against this shape rather than either class.
    """

    @property
    def params(self) -> Mapping[str, object]: ...

    @property
    def command(self) -> _CommandLike: ...

    def get_parameter_source(self, name: str) -> _ParameterSourceLike | None: ...


class ClickSource(BaseSource):
    """Reads explicitly-set Click parameters from the active Context as an eager snapshot (ADR 0032).

    A binding source (ADR 0027, 0049): it surfaces raw parameter names + markers via
    raw_bindings(), which the resolver maps to config paths against the schema path table, rather
    than emitting config-path data. Only parameters the user explicitly set participate, detected
    via Context.get_parameter_source(). The snapshot is captured at construction — no Context
    reference survives __init__ — so binding replays deterministically (ADR 0032).

    Requires click (confiq[click]).
    """

    _NAME: ClassVar[str] = "cli:click"
    _FRAMEWORK: ClassVar[str] = "Click"
    _EXTRA_MODULE: ClassVar[str] = "click"
    _INSTALL_EXTRA: ClassVar[str] = "click"
    _CONTEXT_STACK_MODULES: ClassVar[tuple[str, ...]] = ("click.globals",)

    def __init__(self, *, profile: str | None = None) -> None:
        """Capture the explicitly-set parameters of the active command as immutable RawBindings.

        Raises ImportError if the framework's extra is missing, and RuntimeError if constructed
        outside an active command invocation.
        """
        _ = import_optional(self._EXTRA_MODULE, extra=self._INSTALL_EXTRA)
        context = _current_command_context(self._FRAMEWORK, self._CONTEXT_STACK_MODULES)
        self._bindings: tuple[RawBinding, ...] = _capture_bindings(context)
        self.profile = profile

    @property
    def name(self) -> str:
        return self._NAME

    def raw_bindings(self) -> Sequence[RawBinding]:
        return self._bindings


def _current_command_context(framework: str, module_names: Sequence[str]) -> _CommandContextLike:
    """Return the active context from the first context-stack module offering one, else raise RuntimeError."""
    for module_name in module_names:
        context = _context_from(module_name)
        if context is not None:
            return context
    raise RuntimeError(NO_ACTIVE_CONTEXT_MESSAGE_TEMPLATE.format(framework=framework))


def _context_from(module_name: str) -> _CommandContextLike | None:
    """Return the active context on a context-stack module, or None if absent or empty."""
    try:
        globals_module = importlib.import_module(module_name)
    except ModuleNotFoundError as error:
        if not _is_missing_module_itself(error, module_name):
            raise
        return None
    get_current_context = getattr(globals_module, _CURRENT_CONTEXT_ATTRIBUTE, None)
    if get_current_context is None:
        return None
    try:
        return cast("_CommandContextLike", get_current_context())
    except RuntimeError:
        return None


def _is_missing_module_itself(error: ModuleNotFoundError, module_name: str) -> bool:
    """Report whether the module we asked for is what was missing, rather than one of its imports.

    A missing typer._click.globals reports whichever link of typer, typer._click, typer._click.globals
    broke first, so any dotted prefix of the requested name counts as the module itself being absent.
    """
    missing = error.name
    if missing is None:
        return False
    return module_name == missing or module_name.startswith(f"{missing}.")


def _capture_bindings(ctx: _CommandContextLike) -> tuple[RawBinding, ...]:
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


def _marker_for(param: _ParameterLike, name: str, callback_binds: Mapping[str, ConfigBind]) -> ConfigBind | None:
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
