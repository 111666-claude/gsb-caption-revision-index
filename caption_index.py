"""Live caption timeline for a spectator stream."""


class CaptionIndex:
    def __init__(self):
        self._cues = []
        self.Work = 0

    def apply(self, event):
        """Apply a put or delete event with id, revision, and optional cue data."""
        if event["op"] == "put":
            self._cues.append(dict(event))
        elif event["op"] == "delete":
            self._cues = [cue for cue in self._cues if cue["id"] != event["id"]]
        else:
            raise ValueError("unknown event")

    def visible(self, tick, locale):
        """Return (id, text) pairs for active cues at an integer tick."""
        found = []
        for cue in self._cues:
            self.Work += 1
            if cue["start"] <= tick <= cue["end"] and cue["locale"] in (locale, "en"):
                found.append((cue["start"], cue["id"], cue["text"]))
        found.sort()
        return [(ident, text) for _, ident, text in found]
