"""Regression contract for the vision failure guidance in the public skill."""
from pathlib import Path
import unittest


SKILL = Path(__file__).resolve().parents[1] / "SKILL.md"
README = Path(__file__).resolve().parents[1] / "README.md"
TROUBLESHOOTING = Path(__file__).resolve().parents[1] / "references" / "troubleshooting.md"


class VisionFallbackContractTests(unittest.TestCase):
    def test_skill_requires_transcript_first_single_probe_fallback(self) -> None:
        content = SKILL.read_text(encoding="utf-8")
        for requirement in (
            "Vision is optional evidence, not a prerequisite",
            "provider **and an explicit image-capable model**",
            "exactly one representative hook or CTA frame, sequentially",
            "Never fan out frame analysis before this probe succeeds",
            "make **zero** more vision calls in that run",
            "label visual-only claims\n     `unresolved` rather than guessing",
        ):
            self.assertIn(requirement, content)

    def test_public_docs_explain_the_same_failure_guard(self) -> None:
        combined = README.read_text(encoding="utf-8") + TROUBLESHOOTING.read_text(encoding="utf-8")
        self.assertIn("Do not fan out vision calls before it succeeds", combined)
        self.assertIn("stop vision after the first failed probe", combined)
        self.assertIn("text/coding endpoint inherited for vision", combined)


if __name__ == "__main__":
    unittest.main()
