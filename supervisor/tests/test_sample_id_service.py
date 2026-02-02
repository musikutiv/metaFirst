"""Tests for sample ID extraction service."""

import pytest
from supervisor.services.sample_id_service import (
    extract_sample_id_from_filename,
    detect_sample_ids_for_batch,
)


class TestExtractSampleIdFromFilename:
    """Tests for extract_sample_id_from_filename."""

    def test_named_group_extraction(self):
        """Should extract sample ID using named group (?P<sample_id>...)."""
        result = extract_sample_id_from_filename(
            filename="SAMPLE-001_data.fastq.gz",
            rule_type="filename_regex",
            regex_pattern=r"(?P<sample_id>SAMPLE-\d+)",
        )

        assert result.detected_sample_id == "SAMPLE-001"
        assert result.match_success is True
        assert result.rule_type == "filename_regex"

    def test_group1_fallback(self):
        """Should fall back to group 1 if no named group."""
        result = extract_sample_id_from_filename(
            filename="SAMPLE-002_data.fastq.gz",
            rule_type="filename_regex",
            regex_pattern=r"(SAMPLE-\d+)",  # Group 1, no named group
        )

        assert result.detected_sample_id == "SAMPLE-002"
        assert result.match_success is True

    def test_no_match(self):
        """Should return None if regex doesn't match."""
        result = extract_sample_id_from_filename(
            filename="other_file.txt",
            rule_type="filename_regex",
            regex_pattern=r"(?P<sample_id>SAMPLE-\d+)",
        )

        assert result.detected_sample_id is None
        assert result.match_success is False
        assert "did not match" in result.explanation

    def test_no_rule_configured(self):
        """Should return None if no rule configured."""
        result = extract_sample_id_from_filename(
            filename="any_file.txt",
            rule_type=None,
            regex_pattern=None,
        )

        assert result.detected_sample_id is None
        assert result.match_success is False
        assert "No sample ID extraction rule configured" in result.explanation

    def test_invalid_regex(self):
        """Should handle invalid regex gracefully."""
        result = extract_sample_id_from_filename(
            filename="test.txt",
            rule_type="filename_regex",
            regex_pattern=r"[invalid(regex",  # Invalid regex
        )

        assert result.detected_sample_id is None
        assert result.match_success is False
        assert "Invalid regex" in result.explanation

    def test_unsupported_rule_type(self):
        """Should handle unsupported rule types."""
        result = extract_sample_id_from_filename(
            filename="test.txt",
            rule_type="unknown_type",
            regex_pattern=r".*",
        )

        assert result.detected_sample_id is None
        assert result.match_success is False
        assert "Unsupported rule type" in result.explanation

    def test_path_extracts_basename(self):
        """Should extract from basename when full path is provided."""
        result = extract_sample_id_from_filename(
            filename="some/nested/path/SAMPLE-003_data.txt",
            rule_type="filename_regex",
            regex_pattern=r"(?P<sample_id>SAMPLE-\d+)",
        )

        assert result.detected_sample_id == "SAMPLE-003"
        assert result.example_filename == "SAMPLE-003_data.txt"

    def test_match_but_no_capture_group(self):
        """Should warn when regex matches but has no capture group."""
        result = extract_sample_id_from_filename(
            filename="SAMPLE-001.txt",
            rule_type="filename_regex",
            regex_pattern=r"SAMPLE-\d+",  # No capture group
        )

        assert result.detected_sample_id is None
        assert result.match_success is False
        assert "no capture group" in result.explanation


class TestDetectSampleIdsForBatch:
    """Tests for detect_sample_ids_for_batch."""

    def test_batch_detection(self):
        """Should detect sample IDs for all files in batch."""
        result = detect_sample_ids_for_batch(
            filenames=[
                "SAMPLE-001_read1.fastq",
                "SAMPLE-001_read2.fastq",
                "SAMPLE-002_read1.fastq",
            ],
            rule_type="filename_regex",
            regex_pattern=r"(?P<sample_id>SAMPLE-\d+)",
        )

        assert result["detection_explanation"]["configured"] is True
        assert result["detection_explanation"]["example_result"] == "SAMPLE-001"
        assert len(result["detections"]) == 3
        assert result["detections"][0]["detected_sample_id"] == "SAMPLE-001"
        assert result["detections"][2]["detected_sample_id"] == "SAMPLE-002"

    def test_empty_batch(self):
        """Should handle empty batch."""
        result = detect_sample_ids_for_batch(
            filenames=[],
            rule_type="filename_regex",
            regex_pattern=r".*",
        )

        assert result["detection_explanation"]["example_filename"] is None
        assert len(result["detections"]) == 0
