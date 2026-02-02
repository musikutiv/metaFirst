"""CLI commands for remediation task management."""

import argparse
import sys
from typing import Optional

from sqlalchemy.orm import Session

from supervisor.database import SessionLocal
from supervisor.models.supervisor import Supervisor
from supervisor.models.project import Project
from supervisor.services.remediation_service import (
    detect_issues_for_project,
    create_task,
    task_exists,
)


def run_remediation(
    db: Session,
    supervisor_id: Optional[int] = None,
    dry_run: bool = True,
) -> dict:
    """Run remediation detection for projects.

    Args:
        db: Database session
        supervisor_id: Optional supervisor ID to filter by
        dry_run: If True, only report issues without creating tasks

    Returns:
        Dict with results: {detected: int, created: int, skipped: int}
    """
    results = {"detected": 0, "created": 0, "skipped": 0}

    # Get supervisors to check
    query = db.query(Supervisor).filter(Supervisor.is_active == True)
    if supervisor_id:
        query = query.filter(Supervisor.id == supervisor_id)

    supervisors = query.all()

    for supervisor in supervisors:
        # Get projects for this supervisor
        projects = db.query(Project).filter(Project.supervisor_id == supervisor.id).all()

        for project in projects:
            issues = detect_issues_for_project(db, project.id)

            for issue in issues:
                results["detected"] += 1

                if dry_run:
                    print(f"[DRY-RUN] Would create task for project {project.id}: {issue['description']}")
                else:
                    # Check if task already exists
                    if task_exists(db, project.id, issue["issue_type"], issue.get("sample_id")):
                        results["skipped"] += 1
                        print(f"[SKIPPED] Task already exists for project {project.id}: {issue['issue_type']}")
                    else:
                        task = create_task(
                            db,
                            supervisor_id=supervisor.id,
                            project_id=project.id,
                            issue_type=issue["issue_type"],
                            description=issue["description"],
                            sample_id=issue.get("sample_id"),
                            metadata=issue.get("metadata"),
                        )
                        results["created"] += 1
                        print(f"[CREATED] Task {task.id} for project {project.id}: {issue['description']}")

    return results


def main():
    """Main entry point for remediation CLI."""
    parser = argparse.ArgumentParser(
        description="Run remediation detection for RDMP policy enforcement"
    )
    parser.add_argument(
        "command",
        choices=["run"],
        help="Command to execute"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report issues without creating tasks"
    )
    parser.add_argument(
        "--supervisor",
        type=int,
        help="Supervisor ID to check (optional, defaults to all)"
    )

    args = parser.parse_args()

    if args.command == "run":
        db = SessionLocal()
        try:
            results = run_remediation(
                db,
                supervisor_id=args.supervisor,
                dry_run=args.dry_run,
            )

            print(f"\nSummary:")
            print(f"  Issues detected: {results['detected']}")
            if not args.dry_run:
                print(f"  Tasks created: {results['created']}")
                print(f"  Tasks skipped (already exist): {results['skipped']}")
        finally:
            db.close()


if __name__ == "__main__":
    main()
