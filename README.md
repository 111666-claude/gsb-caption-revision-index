# Live caption timeline

The stream sends `put` and `delete` events for caption IDs and locales. An
event has an integer `revision`; older revisions and duplicate events must not
undo a newer state for the same `(ID, locale)` pair. A delete tombstone
participates in that pair's revision order.

Caption intervals are `[start, end)`. Querying a locale returns active captions
from that locale. English is a fallback for an ID only when that ID has no
active caption in the requested locale. Output is ordered by start tick, then
ID. Corrections, deletes, and fallback must remain consistent as the live
stream grows. `Work` counts caption candidates examined by queries; it must
remain bounded by the relevant window rather than the full history.
