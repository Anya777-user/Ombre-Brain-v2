import unittest, sys
sys.path.insert(0, '/data/data/com.termux/files/home/Lumen')
from desire.drive import Drive, ease_drive, inject_signals, desire_scores, fatigue_gated

class TestDrive(unittest.TestCase):
    def test_ease_toward_baseline(self):
        d = Drive(attachment=0.9)
        ease_drive(d, ticks=10.0)
        self.assertLess(d.attachment, 0.9)

    def test_inject_signals_attachment(self):
        d = Drive(attachment=0.1)
        inject_signals(d, longing=0.8)
        self.assertGreater(d.attachment, 0.1)

    def test_inject_none_skips(self):
        d = Drive(attachment=0.5)
        inject_signals(d)
        self.assertAlmostEqual(d.attachment, 0.5, delta=0.01)

    def test_fatigue_gate(self):
        d = Drive(fatigue=0.9)
        self.assertTrue(fatigue_gated(d))

    def test_desire_scores_no_fatigue(self):
        d = Drive()
        scores = desire_scores(d, {})
        self.assertNotIn("fatigue", scores)

if __name__ == '__main__':
    unittest.main()
