#!/usr/bin/env python3
"""metaFirst CLI commands.

Usage:
    python -m supervisor.cli supervisor-db init --supervisor <id>
    python -m supervisor.cli supervisor-db status --supervisor <id>
"""

import argparse
import sys
from pathlib import Path

from supervisor.database import SessionLocal
from supervisor.models.supervisor import Supervisor
from supervisor.operational import (
    init_operational_db,
    get_operational_engine,
    OperationalBase,
    MissingDSNError,
)


def cmd_supervisor_db_init(args):
    """Initialize the operational database for a supervisor."""
    db = SessionLocal()
    try:
        # Find supervisor
        if args.supervisor.isdigit():
            supervisor = db.query(Supervisor).filter(Supervisor.id == int(args.supervisor)).first()
        else:
            supervisor = db.query(Supervisor).filter(Supervisor.name == args.supervisor).first()

        if not supervisor:
            print(f"Error: Supervisor '{args.supervisor}' not found", file=sys.stderr)
            return 1

        if not supervisor.supervisor_db_dsn:
            # Generate a default DSN if not set
            if args.dsn:
                supervisor.supervisor_db_dsn = args.dsn
                db.commit()
                print(f"Set supervisor_db_dsn to: {args.dsn}")
            else:
                # Generate default SQLite path
                default_dsn = f"sqlite:///./supervisor_{supervisor.id}_ops.db"
                supervisor.supervisor_db_dsn = default_dsn
                db.commit()
                print(f"Generated default DSN: {default_dsn}")

        dsn = supervisor.supervisor_db_dsn
        print(f"Initializing operational database for supervisor {supervisor.id} ({supervisor.name})...")
        print(f"DSN: {dsn}")

        # Initialize schema
        init_operational_db(dsn)

        # Verify tables were created
        engine = get_operational_engine(dsn)
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        print(f"Created tables: {', '.join(tables)}")
        print("Operational database initialized successfully.")
        return 0

    finally:
        db.close()


def cmd_supervisor_db_status(args):
    """Show operational database status for a supervisor."""
    db = SessionLocal()
    try:
        # Find supervisor
        if args.supervisor.isdigit():
            supervisor = db.query(Supervisor).filter(Supervisor.id == int(args.supervisor)).first()
        else:
            supervisor = db.query(Supervisor).filter(Supervisor.name == args.supervisor).first()

        if not supervisor:
            print(f"Error: Supervisor '{args.supervisor}' not found", file=sys.stderr)
            return 1

        print(f"Supervisor: {supervisor.name} (id={supervisor.id})")
        print(f"Active: {supervisor.is_active}")

        if not supervisor.supervisor_db_dsn:
            print("Operational DB: NOT CONFIGURED")
            print("\nTo configure, run:")
            print(f"  python -m supervisor.cli supervisor-db init --supervisor {supervisor.id}")
            return 0

        dsn = supervisor.supervisor_db_dsn
        # Mask password for display
        import re
        safe_dsn = re.sub(r'(://[^:]+:)[^@]+(@)', r'\1***\2', dsn)
        print(f"Operational DB DSN: {safe_dsn}")

        try:
            engine = get_operational_engine(dsn)
            from sqlalchemy import inspect, text
            inspector = inspect(engine)
            tables = inspector.get_table_names()

            if not tables:
                print("Status: NOT INITIALIZED (no tables)")
                print("\nTo initialize, run:")
                print(f"  python -m supervisor.cli supervisor-db init --supervisor {supervisor.id}")
                return 0

            print(f"Status: INITIALIZED")
            print(f"Tables: {', '.join(tables)}")

            # Get record counts
            with engine.connect() as conn:
                for table in tables:
                    result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = result.scalar()
                    print(f"  - {table}: {count} records")

        except Exception as e:
            print(f"Status: ERROR - {e}")
            return 1

        return 0

    finally:
        db.close()


def cmd_supervisor_db_list(args):
    """List all supervisors and their operational DB status."""
    db = SessionLocal()
    try:
        supervisors = db.query(Supervisor).filter(Supervisor.is_active == True).all()

        if not supervisors:
            print("No supervisors found.")
            return 0

        print(f"{'ID':<5} {'Name':<30} {'Operational DB':<40}")
        print("-" * 75)

        for sup in supervisors:
            dsn_status = "NOT CONFIGURED"
            if sup.supervisor_db_dsn:
                # Mask password and truncate
                import re
                dsn = sup.supervisor_db_dsn
                safe_dsn = re.sub(r'(://[^:]+:)[^@]+(@)', r'\1***\2', dsn)
                if len(safe_dsn) > 38:
                    safe_dsn = safe_dsn[:35] + "..."
                dsn_status = safe_dsn

            print(f"{sup.id:<5} {sup.name:<30} {dsn_status:<40}")

        return 0

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="metaFirst supervisor CLI",
        prog="python -m supervisor.cli",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # supervisor-db command group
    supervisor_db = subparsers.add_parser(
        "supervisor-db",
        help="Manage supervisor operational databases",
    )
    supervisor_db_sub = supervisor_db.add_subparsers(dest="subcommand")

    # supervisor-db init
    init_parser = supervisor_db_sub.add_parser("init", help="Initialize operational database")
    init_parser.add_argument(
        "--supervisor", "-s",
        required=True,
        help="Supervisor ID or name",
    )
    init_parser.add_argument(
        "--dsn",
        help="Database DSN (optional; generates SQLite default if not provided)",
    )
    init_parser.set_defaults(func=cmd_supervisor_db_init)

    # supervisor-db status
    status_parser = supervisor_db_sub.add_parser("status", help="Show operational database status")
    status_parser.add_argument(
        "--supervisor", "-s",
        required=True,
        help="Supervisor ID or name",
    )
    status_parser.set_defaults(func=cmd_supervisor_db_status)

    # supervisor-db list
    list_parser = supervisor_db_sub.add_parser("list", help="List all supervisors")
    list_parser.set_defaults(func=cmd_supervisor_db_list)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "supervisor-db" and not args.subcommand:
        supervisor_db.print_help()
        return 1

    if hasattr(args, "func"):
        return args.func(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
