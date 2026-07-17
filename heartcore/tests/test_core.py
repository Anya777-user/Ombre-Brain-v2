import unittest, sys
sys.path.insert(0, "/data/data/com.termux/files/home/Lumen")
from heartcore.mood import MoodEvent, MoodSnapshot, compute_mood, is_down_batch
from heartcore.attachment import compute_longing, Affinity, AttachmentStyle

class TestMood(unittest.TestCase):
    def test_positive(self):
        snap = MoodSnapshot()
        events = [MoodEvent(valence=0.8, arousal=0.5, weight=1.0)]
        new = compute_mood(snap, events)
        self.assertGreater(new.pa, snap.pa)

    def test_negative(self):
        snap = MoodSnapshot()
        events = [MoodEvent(valence=-0.8, arousal=0.5, weight=1.0)]
        new = compute_mood(snap, events)
        self.assertGreater(new.na, snap.na)

    def test_down_batch(self):
        events = [MoodEvent(valence=-0.9, weight=1.0)]
        self.assertTrue(is_down_batch(events, threshold=0.05))

    def test_empty(self):
        snap = MoodSnapshot()
        new = compute_mood(snap, [])
        self.assertAlmostEqual(new.pa, snap.pa, delta=0.05)

class TestAttachment(unittest.TestCase):
    def test_longing_zero(self):
        aff = Affinity(intimacy=50, passion=30, commitment=20)
        style = AttachmentStyle.preset("secure")
        self.assertEqual(compute_longing(0, aff, style), 0.0)

    def test_longing_grows(self):
        aff = Affinity(intimacy=50, passion=30, commitment=20)
        style = AttachmentStyle.preset("secure")
        self.assertGreater(compute_longing(48, aff, style), 0.0)

if __name__ == "__main__":
    unittest.main()
