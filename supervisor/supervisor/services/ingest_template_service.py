"""RDMP-derived sample template service.

Provides functions for generating CSV templates derived from RDMP fields
and parsing uploaded CSV files for multi-sample ingestion.

## Column Mapping (append-only)

The following columns are always present:
- sample_name (required)

The following standard columns are optionally included:
- visibility (PRIVATE, INSTITUTION, PUBLIC)

RDMP-derived columns are included based on the fields defined in rdmp_json.fields[].
Only fields with known types (string, number, date, categorical) are mapped.

## Append-only contract

Adding new *optional* RDMP fields is a safe, non-breaking change: CSV files
exported from an earlier RDMP version will still import successfully because
missing optional columns default to empty/omitted.

Adding a new *required* RDMP field is intentionally a breaking change for
previously exported templates — the import will reject CSVs that lack the
required column header. This is by design: required fields represent data
the project considers incomplete without.

Extra columns in the CSV that don't match any current RDMP field are
silently ignored. The template_hash in audit logs records the column
structure at export/import time for traceability, but is never used as
an acceptance gate.
"""

import csv
import hashlib
import io
from typing import Any, Optional
from dataclasses import dataclass
from sqlalchemy.orm import Session

from supervisor.models.rdmp import RDMPVersion, RDMPStatus
from supervisor.models.sample import Sample, SampleFieldValue, MetadataVisibility

# Maximum rows allowed in a single CSV import
MAX_IMPORT_ROWS = 1000


@dataclass
class TemplateColumn:
    """Definition of a template column."""
    key: str
    label: str
    required: bool
    source: str  # 'system' or 'rdmp'
    field_type: Optional[str] = None  # For RDMP fields
    allowed_values: Optional[list[str]] = None  # For categorical fields


@dataclass
class TemplateMetadata:
    """Metadata about a generated template."""
    rdmp_id: int
    rdmp_version: int
    rdmp_status: str  # ACTIVE or DRAFT
    columns: list[TemplateColumn]
    template_hash: str  # Hash of column structure for audit trail


@dataclass
class RowValidationError:
    """Error in a CSV row."""
    row_number: int
    column: str
    message: str


@dataclass
class CSVPreviewResult:
    """Result of CSV preview/validation."""
    total_rows: int
    valid_rows: int
    errors: list[RowValidationError]
    parsed_rows: list[dict[str, Any]]  # Only valid rows
    template_hash: str


def derive_template_columns(rdmp: RDMPVersion) -> list[TemplateColumn]:
    """Derive template columns from RDMP.

    Column mapping is explicit and append-only:
    - sample_name (required, system)
    - visibility (optional, system)
    - RDMP fields from rdmp_json.fields[]

    When extending this function with new system columns, mark them
    ``required=False`` to preserve backward compatibility with CSVs
    exported from earlier RDMP versions.
    """
    columns = []

    # System columns (always present)
    columns.append(TemplateColumn(
        key="sample_name",
        label="Sample Name",
        required=True,
        source="system",
    ))

    # Optional system column for visibility
    columns.append(TemplateColumn(
        key="visibility",
        label="Visibility",
        required=False,
        source="system",
        allowed_values=["PRIVATE", "INSTITUTION", "PUBLIC"],
    ))

    # RDMP-derived columns
    rdmp_fields = rdmp.rdmp_json.get("fields", [])
    for field in rdmp_fields:
        field_key = field.get("key")
        if not field_key:
            continue

        columns.append(TemplateColumn(
            key=field_key,
            label=field.get("label", field_key),
            required=field.get("required", False),
            source="rdmp",
            field_type=field.get("type"),
            allowed_values=field.get("allowed_values"),
        ))

    return columns


def compute_template_hash(columns: list[TemplateColumn]) -> str:
    """Compute a hash of the template column structure.

    Used for audit trail to detect if template changed between export and import.
    """
    column_keys = [c.key for c in columns]
    content = ",".join(sorted(column_keys))
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def get_rdmp_for_template(db: Session, project_id: int) -> tuple[Optional[RDMPVersion], str]:
    """Get RDMP for template generation.

    Priority:
    1. ACTIVE RDMP (preferred)
    2. DRAFT RDMP (allowed, logged)

    Returns (rdmp, status) where status is 'ACTIVE', 'DRAFT', or 'NONE'.
    """
    # Try to get ACTIVE RDMP first
    active_rdmp = (
        db.query(RDMPVersion)
        .filter(
            RDMPVersion.project_id == project_id,
            RDMPVersion.status == RDMPStatus.ACTIVE,
        )
        .first()
    )

    if active_rdmp:
        return (active_rdmp, "ACTIVE")

    # Fall back to latest DRAFT
    draft_rdmp = (
        db.query(RDMPVersion)
        .filter(
            RDMPVersion.project_id == project_id,
            RDMPVersion.status == RDMPStatus.DRAFT,
        )
        .order_by(RDMPVersion.version_int.desc())
        .first()
    )

    if draft_rdmp:
        return (draft_rdmp, "DRAFT")

    return (None, "NONE")


def generate_template_csv(columns: list[TemplateColumn]) -> str:
    """Generate CSV content with header row only.

    Returns CSV string with column keys as headers.
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header row
    headers = [c.key for c in columns]
    writer.writerow(headers)

    return output.getvalue()


def generate_template_metadata(rdmp: RDMPVersion) -> TemplateMetadata:
    """Generate complete template metadata for a project's RDMP."""
    columns = derive_template_columns(rdmp)
    template_hash = compute_template_hash(columns)

    return TemplateMetadata(
        rdmp_id=rdmp.id,
        rdmp_version=rdmp.version_int,
        rdmp_status=rdmp.status.value,
        columns=columns,
        template_hash=template_hash,
    )


def parse_and_validate_csv(
    csv_content: str,
    columns: list[TemplateColumn],
    existing_sample_names: set[str],
) -> CSVPreviewResult:
    """Parse and validate CSV content against template.

    Validation rules:
    - Required columns must be present in header
    - sample_name is required and must be unique (per file and vs existing)
    - visibility must be valid enum value if provided
    - Row count must not exceed MAX_IMPORT_ROWS
    - RDMP field types are validated
    """
    errors: list[RowValidationError] = []
    parsed_rows: list[dict[str, Any]] = []
    seen_sample_names: set[str] = set()

    # Parse CSV
    try:
        reader = csv.DictReader(io.StringIO(csv_content))
        headers = reader.fieldnames or []
    except Exception as e:
        return CSVPreviewResult(
            total_rows=0,
            valid_rows=0,
            errors=[RowValidationError(0, "", f"Invalid CSV format: {str(e)}")],
            parsed_rows=[],
            template_hash=compute_template_hash(columns),
        )

    # Check required columns in header
    required_columns = {c.key for c in columns if c.required}
    header_set = set(headers)
    missing_required = required_columns - header_set

    if missing_required:
        return CSVPreviewResult(
            total_rows=0,
            valid_rows=0,
            errors=[RowValidationError(
                0, "",
                f"Missing required columns: {', '.join(sorted(missing_required))}"
            )],
            parsed_rows=[],
            template_hash=compute_template_hash(columns),
        )

    # Build column lookup
    column_map = {c.key: c for c in columns}

    # Process rows
    total_rows = 0
    for row_num, row in enumerate(reader, start=2):  # Start at 2 (1 is header)
        total_rows += 1

        if total_rows > MAX_IMPORT_ROWS:
            errors.append(RowValidationError(
                row_num, "",
                f"Exceeded maximum row limit of {MAX_IMPORT_ROWS}"
            ))
            break

        row_errors: list[RowValidationError] = []
        parsed_row: dict[str, Any] = {}

        # Validate sample_name
        sample_name = row.get("sample_name", "").strip()
        if not sample_name:
            row_errors.append(RowValidationError(
                row_num, "sample_name", "Sample name is required"
            ))
        elif sample_name in seen_sample_names:
            row_errors.append(RowValidationError(
                row_num, "sample_name", f"Duplicate sample name in file: {sample_name}"
            ))
        elif sample_name in existing_sample_names:
            row_errors.append(RowValidationError(
                row_num, "sample_name", f"Sample already exists in project: {sample_name}"
            ))
        else:
            seen_sample_names.add(sample_name)
            parsed_row["sample_name"] = sample_name

        # Validate visibility if provided
        visibility = row.get("visibility", "").strip().upper()
        if visibility:
            if visibility not in ("PRIVATE", "INSTITUTION", "PUBLIC"):
                row_errors.append(RowValidationError(
                    row_num, "visibility",
                    f"Invalid visibility: {visibility}. Must be PRIVATE, INSTITUTION, or PUBLIC"
                ))
            else:
                parsed_row["visibility"] = visibility

        # Validate RDMP fields
        for key, col in column_map.items():
            if col.source != "rdmp":
                continue

            value = row.get(key, "").strip()
            if not value:
                if col.required:
                    row_errors.append(RowValidationError(
                        row_num, key, f"Required field is empty"
                    ))
                continue

            # Type validation
            if col.field_type == "number":
                try:
                    parsed_row[key] = float(value)
                except ValueError:
                    row_errors.append(RowValidationError(
                        row_num, key, f"Must be a number"
                    ))
            elif col.field_type == "categorical":
                if col.allowed_values and value not in col.allowed_values:
                    row_errors.append(RowValidationError(
                        row_num, key,
                        f"Invalid value. Must be one of: {', '.join(col.allowed_values)}"
                    ))
                else:
                    parsed_row[key] = value
            else:
                # string, date, or unknown - store as-is
                parsed_row[key] = value

        if row_errors:
            errors.extend(row_errors)
        else:
            parsed_rows.append(parsed_row)

    return CSVPreviewResult(
        total_rows=total_rows,
        valid_rows=len(parsed_rows),
        errors=errors,
        parsed_rows=parsed_rows,
        template_hash=compute_template_hash(columns),
    )


def create_samples_bulk(
    db: Session,
    project_id: int,
    raw_data_item_id: int,
    parsed_rows: list[dict[str, Any]],
    user_id: int,
) -> list[Sample]:
    """Create samples in bulk from parsed CSV rows.

    All samples will be linked to the specified raw data item.
    This is an all-or-nothing transaction - caller should handle commit.

    Returns list of created Sample objects.
    """
    created_samples = []

    for row in parsed_rows:
        sample_name = row.pop("sample_name")
        visibility_str = row.pop("visibility", None)

        # Determine visibility
        visibility = MetadataVisibility.PRIVATE
        if visibility_str:
            visibility = MetadataVisibility(visibility_str)

        # Create sample
        sample = Sample(
            project_id=project_id,
            sample_identifier=sample_name,
            visibility=visibility,
            created_by=user_id,
        )
        db.add(sample)
        db.flush()  # Get sample.id

        # Create field values for remaining keys (RDMP fields)
        for field_key, value in row.items():
            if value is not None:
                import json
                field_value = SampleFieldValue(
                    sample_id=sample.id,
                    field_key=field_key,
                    value_json=json.dumps(value),
                    value_text=str(value),
                    updated_by=user_id,
                )
                db.add(field_value)

        created_samples.append(sample)

    return created_samples
