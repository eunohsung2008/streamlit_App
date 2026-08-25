import tempfile
import unittest
from pathlib import Path

from data_store import LocalStore


class LocalStoreTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = LocalStore(Path(self.temp_dir.name) / "test.db")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_notice_lifecycle(self):
        self.store.add_notice("시험 일정", "금요일입니다.", "담임 선생님", True)
        notices = self.store.list_notices()
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0]["title"], "시험 일정")
        self.assertEqual(notices[0]["pinned"], 1)

        self.store.delete_notice(notices[0]["id"])
        self.assertEqual(self.store.list_notices(), [])

    def test_suggestion_lookup_and_reply(self):
        lookup_hash = "a" * 64
        self.store.add_suggestion("학급 생활", "건의", "내용", lookup_hash)
        suggestion = self.store.get_suggestion_by_hash(lookup_hash)
        self.assertIsNotNone(suggestion)
        self.assertEqual(suggestion["status"], "접수")

        self.store.update_suggestion(suggestion["id"], "답변 완료", "반영할게요.")
        updated = self.store.get_suggestion_by_hash(lookup_hash)
        self.assertEqual(updated["status"], "답변 완료")
        self.assertEqual(updated["reply"], "반영할게요.")

        self.store.delete_suggestion(suggestion["id"])
        self.assertIsNone(self.store.get_suggestion_by_hash(lookup_hash))

    def test_study_post_lifecycle(self):
        image_url, image_path = self.store.save_image(b"image-bytes", "image/webp", "problems")
        self.assertTrue(image_url.startswith("data:image/webp;base64,"))
        self.assertEqual(image_path, "")

        self.store.add_study_post(
            {
                "subject": "수학",
                "title": "좋은 문제",
                "difficulty": "도전",
                "problem": "문제 내용",
                "solution": "풀이 내용",
                "author_alias": "익명",
                "problem_image_url": image_url,
                "problem_image_path": image_path,
            }
        )
        posts = self.store.list_study_posts()
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]["subject"], "수학")

        self.store.delete_study_post(posts[0]["id"])
        self.assertEqual(self.store.list_study_posts(), [])


if __name__ == "__main__":
    unittest.main()

