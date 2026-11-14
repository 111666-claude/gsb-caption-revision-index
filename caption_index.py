"""Live caption timeline for a spectator stream."""

# A dynamically built segment tree over integer ticks.  Each active caption
# interval is stored in the canonical nodes covering ``[start, end)``.  A
# point query only has to look at the nodes on one root-to-leaf path.
_UNIVERSE_SIZE = 1 << 62
_UNIVERSE_MIN = -(1 << 61)


class _IntervalIndex:
    """Active half-open intervals indexed for efficient point queries.

    ``active_at`` yields exactly the keys whose interval contains the tick.  A
    key is only present in one canonical node on any root-to-leaf path, so it
    is yielded once per query.
    """

    def __init__(self):
        self._nodes = {}
        self._nodes_for_key = {}

    @staticmethod
    def _leaf(tick):
        if not _UNIVERSE_MIN <= tick < _UNIVERSE_MIN + _UNIVERSE_SIZE:
            raise ValueError("tick outside supported range")
        return tick - _UNIVERSE_MIN + _UNIVERSE_SIZE

    @classmethod
    def _canonical_nodes(cls, start, end):
        left = cls._leaf(start)
        right = cls._leaf(end)
        nodes = []
        while left < right:
            if left & 1:
                nodes.append(left)
                left += 1
            if right & 1:
                right -= 1
                nodes.append(right)
            left >>= 1
            right >>= 1
        return nodes

    def insert(self, key, start, end):
        if end <= start:
            return
        nodes = self._canonical_nodes(start, end)
        self._nodes_for_key[key] = nodes
        for node in nodes:
            bucket = self._nodes.get(node)
            if bucket is None:
                bucket = self._nodes[node] = set()
            bucket.add(key)

    def remove(self, key):
        nodes = self._nodes_for_key.pop(key, None)
        if not nodes:
            return
        for node in nodes:
            bucket = self._nodes.get(node)
            if bucket is None:
                continue
            bucket.discard(key)
            if not bucket:
                del self._nodes[node]

    def active_at(self, tick):
        node = self._leaf(tick)
        while node:
            bucket = self._nodes.get(node)
            if bucket:
                yield from bucket
            node >>= 1


class CaptionIndex:
    def __init__(self):
        # Latest revision for each (id, locale) pair.  Tombstones stay here so
        # that an older put arriving late cannot resurrect a deleted caption.
        self._revisions = {}
        # The latest state for each pair: a cue dict, or None for a tombstone.
        self._states = {}
        # One point-query index per locale.
        self._indices = {}
        self.Work = 0

    def apply(self, event):
        """Apply a put or delete event with id, revision, and optional cue data."""
        op = event["op"]
        if op not in ("put", "delete"):
            raise ValueError("unknown event")

        key = (event["id"], event["locale"])
        revision = event["revision"]

        # Out-of-order corrections, repeated messages and older tombstones
        # are all no-ops for this (id, locale) pair.
        previous_revision = self._revisions.get(key)
        if previous_revision is not None and revision <= previous_revision:
            return

        old_state = self._states.get(key)
        if old_state is not None:
            self._indices[old_state["locale"]].remove(key)

        if op == "put":
            cue = dict(event)
            self._states[key] = cue
            index = self._indices.get(cue["locale"])
            if index is None:
                index = self._indices[cue["locale"]] = _IntervalIndex()
            index.insert(key, cue["start"], cue["end"])
        else:
            # Keep the tombstone as the pair's current state.
            self._states[key] = None

        self._revisions[key] = revision

    def visible(self, tick, locale):
        """Return (id, text) pairs for active cues at an integer tick."""
        found = []

        # Captions in the requested locale always take precedence over English
        # fallback for the same caption ID.
        target_ids = set()
        index = self._indices.get(locale)
        if index is not None:
            for key in index.active_at(tick):
                self.Work += 1
                state = self._states[key]
                target_ids.add(state["id"])
                found.append((state["start"], state["id"], state["text"]))

        # English is a fallback only for IDs with no active requested-locale
        # caption at this tick.
        if locale != "en":
            english = self._indices.get("en")
            if english is not None:
                for key in english.active_at(tick):
                    self.Work += 1
                    state = self._states[key]
                    if state["id"] not in target_ids:
                        found.append((state["start"], state["id"], state["text"]))

        found.sort(key=lambda item: (item[0], item[1]))
        return [(ident, text) for _, ident, text in found]
