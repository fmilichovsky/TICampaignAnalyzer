# Terra Invicta Narrative Save Analyzer

`tinarrative` reconstructs a readable campaign history from Terra Invicta save
snapshots. It keeps observed state changes separate from inferred events and
narrative presentation.

## Development

```powershell
python -m pip install -e .
tinarrative --help
```

## Testing

```powershell
python -m pip install -e ".[test]"
python -m pytest
```

See [the testing guide](docs/testing.md) for test and fixture conventions.

## Package layout

- `io`: discover and load save files.
- `parsing`: decode version-specific save data and normalize it.
- `model`: stable snapshots, changes, events, and provenance types.
- `diff`: derive literal state transitions.
- `analyzers`: emit domain-specific atomic events.
- `reconstruction`: combine evidence into conservative inferred events.
- `narrative`: group atomic events into narrative developments.
- `rendering`: turn structured narrative output into user-facing formats.
