import unittest

from caption_index import CaptionIndex


def put(ident, revision, locale, start, end, text, **extra):
    event = {"op": "put", "id": ident, "revision": revision, "locale": locale,
             "start": start, "end": end, "text": text}
    event.update(extra)
    return event


def delete(ident, revision, locale):
    return {"op": "delete", "id": ident, "revision": revision, "locale": locale}


def tick_index(events):
    index = CaptionIndex()
    for event in (events.values() if isinstance(events, dict) else events):
        index.apply(event)
    return index


class RevisionOrderingTests(unittest.TestCase):
    def test_newer_revision_wins_when_it_arrives_first(self):
        index = tick_index({
            "1": put("a", 2, "en", 10, 20, "new"),
            "2": put("a", 1, "en", 10, 20, "old"),
            "3": put("a", 2, "en", 10, 20, "duplicate"),
            "4": put("a", 1, "en", 10, 20, "still old"),
        })
        self.assertEqual(index.visible(12, "en"), [("a", "new")])

    def test_out_of_order_delete_cannot_erase_newer_caption(self):
        index = tick_index({
            "1": put("a", 5, "en", 10, 20, "kept"),
            "2": delete("a", 3, "en"),
        })
        self.assertEqual(index.visible(12, "en"), [("a", "kept")])

    def test_late_older_put_cannot_resurrect_deleted_caption(self):
        index = tick_index({
            "1": delete("a", 5, "en"),
            "2": put("a", 4, "en", 10, 20, "ghost"),
        })
        self.assertEqual(index.visible(12, "en"), [])

    def test_newer_put_after_delete_wins(self):
        index = tick_index({
            "1": put("a", 1, "en", 10, 20, "first"),
            "2": delete("a", 2, "en"),
            "3": put("a", 3, "en", 10, 20, "second"),
        })
        self.assertEqual(index.visible(12, "en"), [("a", "second")])

    def test_revisions_are_per_locale_pair(self):
        index = tick_index({
            "1": put("a", 9, "en", 10, 20, "english"),
            "2": put("a", 1, "fr", 10, 20, "francais"),
        })
        self.assertEqual(index.visible(12, "fr"), [("a", "francais")])
        self.assertEqual(index.visible(12, "en"), [("a", "english")])

    def test_tombstone_then_reused_ids_are_independent(self):
        index = tick_index({
            "1": put("a", 1, "en", 10, 20, "gone"),
            "2": delete("a", 2, "en"),
            "3": put("b", 2, "en", 10, 20, "other"),
        })
        self.assertEqual(index.visible(12, "en"), [("b", "other")])

    def test_duplicate_identical_events_are_idempotent(self):
        event = put("a", 1, "en", 10, 20, "one")
        index = tick_index([event, event, event])
        self.assertEqual(index.visible(12, "en"), [("a", "one")])


class IntervalTests(unittest.TestCase):
    def test_interval_is_half_open(self):
        index = tick_index({
            "1": put("a", 1, "en", 10, 20, "A"),
            "2": put("b", 1, "en", 20, 30, "B"),
        })
        self.assertEqual(index.visible(19, "en"), [("a", "A")])
        self.assertEqual(index.visible(20, "en"), [("b", "B")])
        self.assertEqual(index.visible(30, "en"), [])

    def test_correction_moves_the_window(self):
        index = tick_index({
            "1": put("a", 1, "en", 10, 20, "first"),
            "2": put("a", 2, "en", 15, 25, "second"),
        })
        self.assertEqual(index.visible(12, "en"), [])
        self.assertEqual(index.visible(16, "en"), [("a", "second")])
        self.assertEqual(index.visible(22, "en"), [("a", "second")])

    def test_empty_and_inverted_intervals_are_invisible(self):
        index = tick_index({
            "1": put("a", 1, "en", 10, 10, "empty"),
            "2": put("b", 1, "en", 10, 5, "inverted"),
        })
        self.assertEqual(index.visible(10, "en"), [])

    def test_output_ordered_by_start_then_id(self):
        index = tick_index({
            "1": put("c", 1, "en", 10, 100, "C"),
            "2": put("b", 1, "en", 10, 100, "B"),
            "3": put("a", 1, "en", 5, 100, "A"),
            "4": put("d", 1, "fr", 5, 100, "D"),
        })
        self.assertEqual(index.visible(20, "fr"),
                         [("a", "A"), ("d", "D"), ("b", "B"), ("c", "C")])


class FallbackTests(unittest.TestCase):
    def test_english_fallback_only_when_target_language_is_absent(self):
        index = tick_index({
            "1": put("a", 1, "en", 10, 20, "hello"),
            "2": put("b", 1, "en", 10, 20, "only english"),
        })
        self.assertEqual(index.visible(12, "fr"), [("a", "hello"), ("b", "only english")])

    def test_active_target_language_suppresses_english_fallback(self):
        index = tick_index({
            "1": put("a", 1, "en", 10, 20, "english"),
            "2": put("a", 2, "fr", 10, 20, "francais"),
        })
        self.assertEqual(index.visible(12, "fr"), [("a", "francais")])

    def test_fallback_reappears_when_target_version_is_deleted(self):
        index = tick_index({
            "1": put("a", 1, "en", 10, 20, "english"),
            "2": put("a", 1, "fr", 10, 20, "francais"),
            "3": delete("a", 2, "fr"),
        })
        self.assertEqual(index.visible(12, "fr"), [("a", "english")])

    def test_fallback_reappears_when_target_interval_covers_other_ticks(self):
        index = tick_index({
            "1": put("a", 1, "en", 10, 20, "english"),
            "2": put("a", 1, "fr", 30, 40, "francais"),
        })
        self.assertEqual(index.visible(12, "fr"), [("a", "english")])
        self.assertEqual(index.visible(35, "fr"), [("a", "francais")])

    def test_english_query_does_not_fall_back(self):
        index = tick_index({"1": put("a", 1, "fr", 10, 20, "francais")})
        self.assertEqual(index.visible(12, "en"), [])


class WorkBoundTests(unittest.TestCase):
    def test_recent_queries_do_not_scan_history(self):
        index = CaptionIndex()
        for n in range(3000):
            start = n * 10
            index.apply(put(f"old{n}", 1, "en", start, start + 10, f"old text {n}"))
        # A few currently active captions among a large history.
        base = 3000 * 10
        for n in range(5):
            index.apply(put(f"live{n}", 1, "en", base - 10, base + 1000, f"live {n}"))

        total_work = 0
        for q in range(200):
            result = index.visible(base + q, "fr")
            total_work += index.Work
            self.assertEqual(len(result), 5)
        self.assertLessEqual(index.Work, 6000)

    def test_window_work_scales_with_active_not_history(self):
        index = CaptionIndex()
        for n in range(3000):
            start = n * 10
            index.apply(put(f"old{n}", 1, "en", start, start + 10, f"old text {n}"))
        index.apply(put("live", 1, "en", 30000, 40000, "live"))
        self.assertEqual(index.visible(35000, "en"), [("live", "live")])
        self.assertLessEqual(index.Work, 100)


if __name__ == "__main__":
    unittest.main()
