"""Demo data seeding script for RDM system.

Creates:
- 5 users (alice, bob, carol, david, eve)
- 4 RDMP templates (qPCR, RNA-seq, microscopy, clinical)
- 3 projects with RDMPs and storage roots (LOCAL_DATA)
- Sample data with field values
- Demonstrates: multi-project stewards, missing fields, role permissions
"""

import json
import sys
from pathlib import Path

# Add supervisor to path
sys.path.insert(0, str(Path(__file__).parent.parent / "supervisor"))

from sqlalchemy.orm import Session
from supervisor.database import SessionLocal, engine, Base
from supervisor.models.user import User
from supervisor.models.supervisor import Supervisor
from supervisor.models.project import Project
from supervisor.models.membership import Membership
from supervisor.models.supervisor_membership import SupervisorMembership, SupervisorRole
from supervisor.models.rdmp import RDMPTemplate, RDMPTemplateVersion, RDMPVersion
from supervisor.models.sample import Sample, SampleFieldValue
from supervisor.models.storage import StorageRoot
from supervisor.utils.security import hash_password


def load_rdmp_template(filename: str) -> dict:
    """Load RDMP template from JSON file."""
    path = Path(__file__).parent / "rdmp_templates" / filename
    with open(path) as f:
        return json.load(f)


def seed_database():
    """Seed the database with demo data."""
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    try:
        print("\n=== Creating Users ===")
        users_data = [
            {"username": "alice", "display_name": "Alice Smith", "password": "demo123"},
            {"username": "bob", "display_name": "Bob Johnson", "password": "demo123"},
            {"username": "carol", "display_name": "Carol Williams", "password": "demo123"},
            {"username": "david", "display_name": "David Brown", "password": "demo123"},
            {"username": "eve", "display_name": "Eve Davis", "password": "demo123"},
        ]

        users = []
        for data in users_data:
            user = User(
                username=data["username"],
                hashed_password=hash_password(data["password"]),
                display_name=data["display_name"],
            )
            db.add(user)
            users.append(user)
            print(f"  Created user: {data['username']} ({data['display_name']})")

        db.flush()

        print("\n=== Creating RDMP Templates ===")
        template_files = [
            ("qpcr.json", "qPCR Standard"),
            ("rnaseq.json", "RNA-seq Standard"),
            ("microscopy.json", "Microscopy Standard"),
            ("clinical_samples.json", "Clinical Samples"),
        ]

        templates = []
        for filename, name in template_files:
            rdmp_json = load_rdmp_template(filename)

            template = RDMPTemplate(
                name=rdmp_json["name"],
                description=rdmp_json["description"],
            )
            db.add(template)
            db.flush()

            version = RDMPTemplateVersion(
                template_id=template.id,
                version_int=1,
                created_by=users[0].id,  # Alice creates all templates
                template_json=rdmp_json,
            )
            db.add(version)
            templates.append((template, rdmp_json))
            print(f"  Created template: {name}")

        db.flush()

        print("\n=== Creating Supervisor ===")
        # Create a default supervisor for all demo projects
        # Operational DB uses SQLite in the supervisor directory
        supervisor_db_path = Path(__file__).parent.parent / "supervisor" / "demo_lab_ops.db"
        supervisor_db_dsn = f"sqlite:///{supervisor_db_path}"
        supervisor = Supervisor(
            name="Demo Lab",
            description="Default supervisor for demo projects",
            supervisor_db_dsn=supervisor_db_dsn,
        )
        db.add(supervisor)
        db.flush()
        print(f"  Created supervisor: {supervisor.name}")

        print("\n=== Creating Supervisor Memberships ===")
        # Alice: PI (primary steward authority)
        db.add(SupervisorMembership(
            supervisor_id=supervisor.id,
            user_id=users[0].id,  # Alice
            role=SupervisorRole.PI,
            created_by=users[0].id,
        ))
        print("  Alice → PI")

        # Eve: STEWARD (operational responsibility)
        db.add(SupervisorMembership(
            supervisor_id=supervisor.id,
            user_id=users[4].id,  # Eve
            role=SupervisorRole.STEWARD,
            created_by=users[0].id,
        ))
        print("  Eve → STEWARD")

        # Carol: STEWARD (also a steward, cross-project responsibilities)
        db.add(SupervisorMembership(
            supervisor_id=supervisor.id,
            user_id=users[2].id,  # Carol
            role=SupervisorRole.STEWARD,
            created_by=users[0].id,
        ))
        print("  Carol → STEWARD")

        # Bob: RESEARCHER
        db.add(SupervisorMembership(
            supervisor_id=supervisor.id,
            user_id=users[1].id,  # Bob
            role=SupervisorRole.RESEARCHER,
            created_by=users[0].id,
        ))
        print("  Bob → RESEARCHER")

        # David: RESEARCHER
        db.add(SupervisorMembership(
            supervisor_id=supervisor.id,
            user_id=users[3].id,  # David
            role=SupervisorRole.RESEARCHER,
            created_by=users[0].id,
        ))
        print("  David → RESEARCHER")

        db.flush()

        # Set Alice as primary steward
        supervisor.primary_steward_user_id = users[0].id
        print(f"  Primary steward set to: Alice")

        print("\n=== Creating Projects ===")

        # Project 1: Gene Expression Study (qPCR) - Alice PI, Bob and Carol researchers
        print("\n  Project 1: Gene Expression Study 2024 (qPCR)")
        project1 = Project(
            name="Gene Expression Study 2024",
            description="qPCR analysis of gene expression in cancer cell lines",
            created_by=users[0].id,  # Alice
            supervisor_id=supervisor.id,
        )
        db.add(project1)
        db.flush()

        # RDMP for project 1 (qPCR template)
        rdmp1 = RDMPVersion(
            project_id=project1.id,
            version_int=1,
            created_by=users[0].id,
            rdmp_json=templates[0][1],  # qPCR template
            provenance_json={
                "template_id": templates[0][0].id,
                "template_name": "qPCR Standard",
                "template_version": 1
            },
        )
        db.add(rdmp1)

        # Memberships
        db.add(Membership(project_id=project1.id, user_id=users[0].id, role_name="PI", created_by=users[0].id))
        db.add(Membership(project_id=project1.id, user_id=users[1].id, role_name="researcher", created_by=users[0].id))
        db.add(Membership(project_id=project1.id, user_id=users[2].id, role_name="researcher", created_by=users[0].id))
        print("    Members: Alice (PI), Bob (researcher), Carol (researcher)")

        # Storage root for project 1
        storage_root1 = StorageRoot(
            project_id=project1.id,
            name="LOCAL_DATA",
            description="Local folders on user machines",
        )
        db.add(storage_root1)
        print("    Storage root: LOCAL_DATA")

        # Project 2: Transcriptomics Analysis (RNA-seq) - Carol PI, David researcher, Eve steward
        print("\n  Project 2: Transcriptomics Analysis (RNA-seq)")
        project2 = Project(
            name="Transcriptomics Analysis",
            description="RNA-seq of cancer cell lines under different treatments",
            created_by=users[2].id,  # Carol
            supervisor_id=supervisor.id,
        )
        db.add(project2)
        db.flush()

        # RDMP for project 2 (RNA-seq template)
        rdmp2 = RDMPVersion(
            project_id=project2.id,
            version_int=1,
            created_by=users[2].id,
            rdmp_json=templates[1][1],  # RNA-seq template
            provenance_json={
                "template_id": templates[1][0].id,
                "template_name": "RNA-seq Standard",
                "template_version": 1
            },
        )
        db.add(rdmp2)

        # Memberships
        db.add(Membership(project_id=project2.id, user_id=users[2].id, role_name="PI", created_by=users[2].id))
        db.add(Membership(project_id=project2.id, user_id=users[3].id, role_name="researcher", created_by=users[2].id))
        db.add(Membership(project_id=project2.id, user_id=users[4].id, role_name="steward", created_by=users[2].id))
        print("    Members: Carol (PI), David (researcher), Eve (steward)")

        # Storage root for project 2
        storage_root2 = StorageRoot(
            project_id=project2.id,
            name="LOCAL_DATA",
            description="Local folders on user machines",
        )
        db.add(storage_root2)
        print("    Storage root: LOCAL_DATA")

        # Project 3: Cellular Imaging Core (Microscopy) - Eve steward, Alice researcher
        print("\n  Project 3: Cellular Imaging Core (Microscopy)")
        project3 = Project(
            name="Cellular Imaging Core",
            description="Microscopy facility data management",
            created_by=users[4].id,  # Eve
            supervisor_id=supervisor.id,
        )
        db.add(project3)
        db.flush()

        # RDMP for project 3 (Microscopy template)
        rdmp3 = RDMPVersion(
            project_id=project3.id,
            version_int=1,
            created_by=users[4].id,
            rdmp_json=templates[2][1],  # Microscopy template
            provenance_json={
                "template_id": templates[2][0].id,
                "template_name": "Microscopy Standard",
                "template_version": 1
            },
        )
        db.add(rdmp3)

        # Memberships
        db.add(Membership(project_id=project3.id, user_id=users[4].id, role_name="steward", created_by=users[4].id))
        db.add(Membership(project_id=project3.id, user_id=users[0].id, role_name="researcher", created_by=users[4].id))
        print("    Members: Eve (steward), Alice (researcher)")

        # Storage root for project 3
        storage_root3 = StorageRoot(
            project_id=project3.id,
            name="LOCAL_DATA",
            description="Local folders on user machines",
        )
        db.add(storage_root3)
        print("    Storage root: LOCAL_DATA")

        db.flush()

        print("\n=== Creating Sample Data ===")

        # Project 1 samples (qPCR) - Bob creates samples
        print("\n  Project 1 samples (qPCR):")

        # Sample 1: Complete sample
        sample1 = Sample(
            project_id=project1.id,
            sample_identifier="QPCR-001",
            created_by=users[1].id,  # Bob
        )
        db.add(sample1)
        db.flush()

        # Add complete field values
        fields1 = [
            ("gene_name", "GAPDH"),
            ("primer_batch", "BATCH-2024-01"),
            ("cell_line", "HeLa"),
            ("replicate_number", 1),
            ("experiment_date", "2024-01-15"),
            ("notes", "Control sample"),
        ]

        for field_key, value in fields1:
            db.add(SampleFieldValue(
                sample_id=sample1.id,
                field_key=field_key,
                value_json=json.dumps(value),
                value_text=str(value),
                updated_by=users[1].id,
            ))

        print(f"    ✓ {sample1.sample_identifier} (complete)")

        # Sample 2: Incomplete sample (missing cell_line - required field)
        sample2 = Sample(
            project_id=project1.id,
            sample_identifier="QPCR-002",
            created_by=users[1].id,  # Bob
        )
        db.add(sample2)
        db.flush()

        # Add partial field values (missing cell_line)
        fields2 = [
            ("gene_name", "TP53"),
            ("primer_batch", "BATCH-2024-01"),
            ("replicate_number", 1),
            ("experiment_date", "2024-01-16"),
        ]

        for field_key, value in fields2:
            db.add(SampleFieldValue(
                sample_id=sample2.id,
                field_key=field_key,
                value_json=json.dumps(value),
                value_text=str(value),
                updated_by=users[1].id,
            ))

        print(f"    ⚠ {sample2.sample_identifier} (INCOMPLETE - missing cell_line)")

        # Project 2 samples (RNA-seq) - David creates samples
        print("\n  Project 2 samples (RNA-seq):")

        sample3 = Sample(
            project_id=project2.id,
            sample_identifier="RNA-001",
            created_by=users[3].id,  # David
        )
        db.add(sample3)
        db.flush()

        fields3 = [
            ("library_prep_kit", "TruSeq Stranded mRNA"),
            ("sequencing_platform", "Illumina NovaSeq"),
            ("read_length", 150),
            ("tissue_type", "Liver"),
            ("treatment_condition", "Untreated"),
            ("rna_quality_rin", 8.5),
        ]

        for field_key, value in fields3:
            db.add(SampleFieldValue(
                sample_id=sample3.id,
                field_key=field_key,
                value_json=json.dumps(value),
                value_text=str(value),
                updated_by=users[3].id,
            ))

        print(f"    ✓ {sample3.sample_identifier} (complete)")

        # Project 3 samples (Microscopy) - Eve creates samples
        print("\n  Project 3 samples (Microscopy):")

        sample4 = Sample(
            project_id=project3.id,
            sample_identifier="IMG-001",
            created_by=users[4].id,  # Eve
        )
        db.add(sample4)
        db.flush()

        fields4 = [
            ("microscope_type", "Confocal"),
            ("objective", "63x/1.4 NA Oil"),
            ("fluorophore", "GFP"),
            ("exposure_time_ms", 100),
            ("sample_type", "Fixed cells"),
        ]

        for field_key, value in fields4:
            db.add(SampleFieldValue(
                sample_id=sample4.id,
                field_key=field_key,
                value_json=json.dumps(value),
                value_text=str(value),
                updated_by=users[4].id,
            ))

        print(f"    ✓ {sample4.sample_identifier} (complete)")

        db.commit()

        # Initialize operational database for the supervisor
        print("\n=== Initializing Operational Database ===")
        from supervisor.operational import init_operational_db
        init_operational_db(supervisor_db_dsn)
        print(f"  Initialized: {supervisor_db_dsn}")

        print("\n" + "=" * 50)
        print("✓ Demo data seeded successfully!")
        print("=" * 50)

        print("\n=== Summary ===")
        print(f"Users: {len(users_data)}")
        print(f"  - alice, bob, carol, david, eve (all with password: demo123)")
        print(f"\nSupervisors: 1")
        print(f"  - Demo Lab (owns all demo projects)")
        print(f"  - Operational DB: {supervisor_db_dsn}")
        print(f"  - Primary steward: Alice (PI)")
        print(f"  - Memberships:")
        print(f"      Alice (PI), Carol (STEWARD), Eve (STEWARD), Bob (RESEARCHER), David (RESEARCHER)")
        print(f"\nRDMP Templates: {len(template_files)}")
        print(f"  - qPCR Standard")
        print(f"  - RNA-seq Standard")
        print(f"  - Microscopy Standard")
        print(f"  - Clinical Samples")
        print(f"\nProjects: 3 (each with storage root: LOCAL_DATA, owned by Demo Lab supervisor)")
        print(f"  - Gene Expression Study 2024 (qPCR)")
        print(f"  - Transcriptomics Analysis (RNA-seq)")
        print(f"  - Cellular Imaging Core (Microscopy)")
        print(f"\nSamples: 4 total")
        print(f"  - 2 in qPCR project (1 incomplete)")
        print(f"  - 1 in RNA-seq project")
        print(f"  - 1 in Microscopy project")
        print(f"\nMulti-project stewards:")
        print(f"  - Carol: Member of projects 1 and 2")
        print(f"  - Eve: Member of projects 2 and 3")
        print(f"  - Alice: Member of projects 1 and 3")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Error seeding data: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 50)
    print("RDM Demo Data Seeding")
    print("=" * 50)
    seed_database()
