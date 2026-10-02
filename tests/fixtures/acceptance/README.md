# Validator trace fixtures

`trace-cases.json` is a compact, synthetic validator fixture derived from the six genuine
Playwright workflow captures at candidate `f4b2a4a6e3364f24a2e0e8201757bef5c9ee1306`.
It retains observed context options, every before/after action, the initial full DOM snapshot,
and initial HTTP document/resource, omitting subsequent snapshots, screencast images and source
files. It is a minimally replayable structure for validator unit tests, not release evidence or
proof of a product acceptance run. Test construction adjusts the context wall-clock time into
the synthetic command interval, explicitly; the captured action semantics remain unchanged.
All captured records use synthetic inputs. New release bundles must come from fresh actual
browser runs with complete snapshots/resources, never these fixtures.
