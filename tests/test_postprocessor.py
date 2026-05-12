"""Tests for postprocessor.py — filler removal and auto-punctuation."""

import pytest

from postprocessor import PostProcessor, add_terminal_punctuation, remove_fillers


# ---------------------------------------------------------------------------
# remove_fillers
# ---------------------------------------------------------------------------

class TestRemoveFillers:
    def test_no_fillers_unchanged(self):
        assert remove_fillers("Hello world") == "Hello world"

    def test_single_filler_removed(self):
        assert remove_fillers("um hello") == "hello"

    def test_trailing_filler_removed(self):
        assert remove_fillers("hello um") == "hello"

    def test_filler_in_middle_removed(self):
        assert remove_fillers("hello um world") == "hello world"

    def test_filler_case_insensitive(self):
        assert remove_fillers("Hello Um world") == "Hello world"

    def test_multiple_fillers_removed(self):
        assert remove_fillers("um uh hello uh world") == "hello world"

    def test_bigram_filler_removed(self):
        assert remove_fillers("you know what I mean") == "what I mean"

    def test_bigram_filler_case_insensitive(self):
        assert remove_fillers("You Know what") == "what"

    def test_bigram_checked_before_single(self):
        # "you know" should be consumed as bigram, not as two separate tokens
        result = remove_fillers("you know")
        assert result == ""

    def test_filler_word_like(self):
        assert remove_fillers("it's like amazing") == "it's amazing"

    def test_filler_word_right(self):
        assert remove_fillers("that's right fine") == "that's fine"

    def test_empty_string(self):
        assert remove_fillers("") == ""

    def test_all_fillers_returns_empty(self):
        assert remove_fillers("um uh") == ""

    def test_non_filler_word_with_filler_substring_preserved(self):
        # "umbrella" starts with "um" but is not a filler word
        assert remove_fillers("umbrella") == "umbrella"

    def test_preserves_word_order(self):
        result = remove_fillers("basically the cat sat on basically the mat")
        assert result == "the cat sat on the mat"


# ---------------------------------------------------------------------------
# add_terminal_punctuation
# ---------------------------------------------------------------------------

class TestAddTerminalPunctuation:
    def test_adds_period_when_missing(self):
        assert add_terminal_punctuation("Hello world") == "Hello world."

    def test_no_change_if_period_present(self):
        assert add_terminal_punctuation("Hello world.") == "Hello world."

    def test_no_change_if_question_mark(self):
        assert add_terminal_punctuation("How are you?") == "How are you?"

    def test_no_change_if_exclamation(self):
        assert add_terminal_punctuation("Great!") == "Great!"

    def test_no_change_if_colon(self):
        assert add_terminal_punctuation("Note:") == "Note:"

    def test_no_change_if_semicolon(self):
        assert add_terminal_punctuation("Done;") == "Done;"

    def test_no_change_if_ellipsis(self):
        assert add_terminal_punctuation("Well…") == "Well…"

    def test_empty_string_unchanged(self):
        assert add_terminal_punctuation("") == ""

    def test_strips_trailing_whitespace_before_adding_period(self):
        result = add_terminal_punctuation("Hello   ")
        assert result.endswith(".")
        assert not result.endswith(" .")

    def test_whitespace_only_unchanged(self):
        result = add_terminal_punctuation("   ")
        assert result == "   "


# ---------------------------------------------------------------------------
# PostProcessor.process — full pipeline
# ---------------------------------------------------------------------------

class TestPostProcessor:
    def setup_method(self):
        self.pp = PostProcessor()

    def test_clean_text_gets_period(self):
        assert self.pp.process("Hello world") == "Hello world."

    def test_filler_removed_and_period_added(self):
        assert self.pp.process("um hello world") == "hello world."

    def test_existing_period_preserved(self):
        assert self.pp.process("Hello world.") == "Hello world."

    def test_all_fillers_produces_empty_string(self):
        # After removing all tokens, add_terminal_punctuation gets ""
        result = self.pp.process("um uh")
        assert result == ""

    def test_filler_then_punctuation(self):
        result = self.pp.process("um great work!")
        assert result == "great work!"

    def test_bigram_filler_pipeline(self):
        result = self.pp.process("you know this is good")
        assert result == "this is good."
