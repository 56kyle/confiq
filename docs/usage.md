# Usage

`confiq` is a library, not a command-line tool: configuration is computed by calling
`load(schema, sources)` from your own application. See `design_d.md` for the full
specification and `reference.md` for the API surface.

```python
from confiq import EnvSource, FileSource, load

settings = load(Settings, sources=[
    FileSource("config.toml"),
    EnvSource(prefix="APP"),   # highest precedence
])
```
