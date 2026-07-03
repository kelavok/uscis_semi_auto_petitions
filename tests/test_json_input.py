import unittest

from app.json_input import parse_llm_json_object


class JsonInputTests(unittest.TestCase):
    def test_valid_json_is_unchanged(self) -> None:
        result = parse_llm_json_object('{"message": "valid", "items": ["a", "b"]}')
        self.assertFalse(result.repaired)
        self.assertEqual(result.data["message"], "valid")

    def test_repairs_fences_nested_quotes_newlines_and_trailing_comma(self) -> None:
        malformed = '''Here is the JSON:
```json
{
  "exact_rfe_quote": "The officer wrote "web portals," "domains," and "blogs" carry no weight.",
  "strategy": "Line one
Line two",
}
```'''
        result = parse_llm_json_object(malformed)
        self.assertTrue(result.repaired)
        self.assertEqual(
            result.data["exact_rfe_quote"],
            'The officer wrote "web portals," "domains," and "blogs" carry no weight.',
        )
        self.assertEqual(result.data["strategy"], "Line one\nLine two")
        self.assertTrue(any("double quote" in note for note in result.repair_notes))
        self.assertTrue(any("trailing comma" in note for note in result.repair_notes))

    def test_preserves_valid_arrays_of_strings_during_repair(self) -> None:
        malformed = '''```json
{"items": ["one", "two"], "quote": "He said "hello" today."}
```'''
        result = parse_llm_json_object(malformed)
        self.assertEqual(result.data["items"], ["one", "two"])
        self.assertEqual(result.data["quote"], 'He said "hello" today.')


if __name__ == "__main__":
    unittest.main()
