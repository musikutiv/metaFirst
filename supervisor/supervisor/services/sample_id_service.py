"""Sample ID extraction service for detecting sample identifiers from filenames."""

import re
import os
from typing import Optional
from dataclasses import dataclass


@dataclass
class SampleIdDetectionResult:
    """Result of sample ID detection from a filename."""
    detected_sample_id: Optional[str]
    rule_type: Optional[str]
    regex: Optional[str]
    example_filename: str
    match_success: bool
    explanation: str


def extract_sample_id_from_filename(
    filename: str,
    rule_type: Optional[str],
    regex_pattern: Optional[str],
) -> SampleIdDetectionResult:
    """Extract sample ID from filename using the configured rule.

    Args:
        filename: The filename (or path) to extract from
        rule_type: The rule type (currently only "filename_regex" supported)
        regex_pattern: The regex pattern to use. Should have named group (?P<sample_id>...)
                      or we fall back to group 1.

    Returns:
        SampleIdDetectionResult with detection details
    """
    # Get just the filename if a path was provided
    basename = os.path.basename(filename)

    # No rule configured
    if not rule_type or not regex_pattern:
        return SampleIdDetectionResult(
            detected_sample_id=None,
            rule_type=rule_type,
            regex=regex_pattern,
            example_filename=basename,
            match_success=False,
            explanation="No sample ID extraction rule configured for this project",
        )

    # Only filename_regex is supported for now
    if rule_type != "filename_regex":
        return SampleIdDetectionResult(
            detected_sample_id=None,
            rule_type=rule_type,
            regex=regex_pattern,
            example_filename=basename,
            match_success=False,
            explanation=f"Unsupported rule type: {rule_type}",
        )

    try:
        match = re.search(regex_pattern, basename)
        if not match:
            return SampleIdDetectionResult(
                detected_sample_id=None,
                rule_type=rule_type,
                regex=regex_pattern,
                example_filename=basename,
                match_success=False,
                explanation=f"Regex did not match filename '{basename}'",
            )

        # Try named group first, then fall back to group 1
        sample_id = None
        try:
            sample_id = match.group("sample_id")
        except IndexError:
            pass

        if sample_id is None and match.lastindex and match.lastindex >= 1:
            sample_id = match.group(1)

        if sample_id:
            return SampleIdDetectionResult(
                detected_sample_id=sample_id,
                rule_type=rule_type,
                regex=regex_pattern,
                example_filename=basename,
                match_success=True,
                explanation=f"Extracted '{sample_id}' from '{basename}' using regex",
            )
        else:
            return SampleIdDetectionResult(
                detected_sample_id=None,
                rule_type=rule_type,
                regex=regex_pattern,
                example_filename=basename,
                match_success=False,
                explanation="Regex matched but no capture group found (use named group ?P<sample_id> or group 1)",
            )

    except re.error as e:
        return SampleIdDetectionResult(
            detected_sample_id=None,
            rule_type=rule_type,
            regex=regex_pattern,
            example_filename=basename,
            match_success=False,
            explanation=f"Invalid regex pattern: {str(e)}",
        )


def detect_sample_ids_for_batch(
    filenames: list[str],
    rule_type: Optional[str],
    regex_pattern: Optional[str],
) -> dict:
    """Detect sample IDs for a batch of files.

    Returns detection info using the first file as example.

    Args:
        filenames: List of filenames/paths
        rule_type: The rule type
        regex_pattern: The regex pattern

    Returns:
        Dict with detection explanation and per-file results
    """
    if not filenames:
        return {
            "detection_explanation": {
                "rule_type": rule_type,
                "regex": regex_pattern,
                "example_filename": None,
                "example_result": None,
                "configured": bool(rule_type and regex_pattern),
            },
            "detections": [],
        }

    # Use first file as example
    example_file = filenames[0]
    example_result = extract_sample_id_from_filename(example_file, rule_type, regex_pattern)

    # Detect for all files
    detections = []
    for filename in filenames:
        result = extract_sample_id_from_filename(filename, rule_type, regex_pattern)
        detections.append({
            "filename": os.path.basename(filename),
            "detected_sample_id": result.detected_sample_id,
            "match_success": result.match_success,
        })

    return {
        "detection_explanation": {
            "rule_type": rule_type,
            "regex": regex_pattern,
            "example_filename": example_result.example_filename,
            "example_result": example_result.detected_sample_id,
            "configured": bool(rule_type and regex_pattern),
            "explanation": example_result.explanation,
        },
        "detections": detections,
    }
