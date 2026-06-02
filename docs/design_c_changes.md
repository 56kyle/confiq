# Planned Changes to Design C


- Change FileSource to use fsspec
- Passthrough much of the fsspec optional dependencies where relevant
- Refactor CliSource into 3 separate sources for argparse, click, and typer (can compose parts of the three however)
- Ensure none of the manual arg parsing makes it past
- Ensure the behavior of explicitly binding portions of the CLI to the config, then updating the config on CLI execution
- Figure out how to resolve CLI defaults vs config defaults, for example, if a CLI function defines x as 2 by default, does that override a config level default just by the cli function being called? How about an env var?
- Look into possibly extracting loaders to instead be sources, then composing the source logic as needed (for example, maybe file source just loads text or bytes, then that is parsed elsewhere?)
- If not doing loaders turned to sources, maybe make a proper transformation layer kind of similar to an ETL pipeline
- Look further into plugins and where they truly make sense
- Especially interrogate whether the way we handle adapter selection makes any sense at all
- Overall check larger structure sense
- Check for any design patterns that may help better architect everything
- Look to improve the module split up into more relevant groupings
- Break up functions where possible. The entire resolution chain is far too compacted
- Make explicit the behaviors underpinning resolution on all fronts.
