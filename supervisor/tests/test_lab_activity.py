"""Tests for lab activity logging."""

import pytest
from supervisor.models.lab_activity import LabActivityLog, ActivityEventType, EntityType
from supervisor.services.lab_activity_service import (
    log_activity,
    log_member_added,
    log_member_role_changed,
    log_member_removed,
    get_lab_activities,
    count_lab_activities,
)


class TestLabActivityService:
    """Tests for the lab activity service functions."""

    def test_log_activity_creates_entry(self, db, test_supervisor, test_user):
        """Test that log_activity creates a new activity log entry."""
        activity = log_activity(
            db=db,
            lab_id=test_supervisor.id,
            actor_user_id=test_user.id,
            event_type=ActivityEventType.MEMBER_ADDED.value,
            entity_type=EntityType.MEMBER.value,
            entity_id=test_user.id,
            summary_text="Test activity entry",
        )
        db.commit()

        assert activity.id is not None
        assert activity.lab_id == test_supervisor.id
        assert activity.actor_user_id == test_user.id
        assert activity.event_type == ActivityEventType.MEMBER_ADDED.value
        assert activity.summary_text == "Test activity entry"

    def test_log_activity_with_reason_and_json(self, db, test_supervisor, test_user):
        """Test that log_activity stores reason and JSON fields."""
        before_state = {"role": "RESEARCHER"}
        after_state = {"role": "STEWARD"}

        activity = log_activity(
            db=db,
            lab_id=test_supervisor.id,
            actor_user_id=test_user.id,
            event_type=ActivityEventType.MEMBER_ROLE_CHANGED.value,
            entity_type=EntityType.MEMBER.value,
            entity_id=test_user.id,
            summary_text="Changed role",
            reason_text="Promoted due to contributions",
            before_json=before_state,
            after_json=after_state,
        )
        db.commit()

        assert activity.reason_text == "Promoted due to contributions"
        assert activity.before_json == before_state
        assert activity.after_json == after_state

    def test_log_member_added_convenience(self, db, test_supervisor, test_user, test_user2):
        """Test the log_member_added convenience function."""
        activity = log_member_added(
            db=db,
            lab_id=test_supervisor.id,
            actor_user_id=test_user.id,
            member_user_id=test_user2.id,
            member_name="Test User 2",
            role="RESEARCHER",
        )
        db.commit()

        assert activity.event_type == ActivityEventType.MEMBER_ADDED.value
        assert activity.entity_type == EntityType.MEMBER.value
        assert activity.entity_id == test_user2.id
        assert "Added Test User 2 as RESEARCHER" in activity.summary_text

    def test_log_member_role_changed_convenience(self, db, test_supervisor, test_user, test_user2):
        """Test the log_member_role_changed convenience function."""
        activity = log_member_role_changed(
            db=db,
            lab_id=test_supervisor.id,
            actor_user_id=test_user.id,
            member_user_id=test_user2.id,
            member_name="Test User 2",
            old_role="RESEARCHER",
            new_role="STEWARD",
            reason_text="Promoted for excellent work",
        )
        db.commit()

        assert activity.event_type == ActivityEventType.MEMBER_ROLE_CHANGED.value
        assert activity.reason_text == "Promoted for excellent work"
        assert activity.before_json == {"role": "RESEARCHER"}
        assert activity.after_json == {"role": "STEWARD"}

    def test_log_member_removed_convenience(self, db, test_supervisor, test_user, test_user2):
        """Test the log_member_removed convenience function."""
        activity = log_member_removed(
            db=db,
            lab_id=test_supervisor.id,
            actor_user_id=test_user.id,
            member_user_id=test_user2.id,
            member_name="Test User 2",
            old_role="RESEARCHER",
        )
        db.commit()

        assert activity.event_type == ActivityEventType.MEMBER_REMOVED.value
        assert "Removed Test User 2 (was RESEARCHER)" in activity.summary_text

    def test_get_lab_activities_returns_ordered(self, db, test_supervisor, test_user):
        """Test that get_lab_activities returns results in reverse chronological order."""
        # Create multiple activities
        for i in range(3):
            log_activity(
                db=db,
                lab_id=test_supervisor.id,
                actor_user_id=test_user.id,
                event_type=ActivityEventType.MEMBER_ADDED.value,
                entity_type=EntityType.MEMBER.value,
                entity_id=i + 1,
                summary_text=f"Activity {i}",
            )
        db.commit()

        activities = get_lab_activities(db, test_supervisor.id)

        assert len(activities) == 3
        # Should be in reverse order (most recent first)
        assert activities[0].summary_text == "Activity 2"
        assert activities[1].summary_text == "Activity 1"
        assert activities[2].summary_text == "Activity 0"

    def test_get_lab_activities_filters_by_event_type(self, db, test_supervisor, test_user):
        """Test filtering activities by event type."""
        log_activity(
            db=db,
            lab_id=test_supervisor.id,
            actor_user_id=test_user.id,
            event_type=ActivityEventType.MEMBER_ADDED.value,
            entity_type=EntityType.MEMBER.value,
            entity_id=1,
            summary_text="Member added",
        )
        log_activity(
            db=db,
            lab_id=test_supervisor.id,
            actor_user_id=test_user.id,
            event_type=ActivityEventType.MEMBER_REMOVED.value,
            entity_type=EntityType.MEMBER.value,
            entity_id=1,
            summary_text="Member removed",
        )
        db.commit()

        activities = get_lab_activities(
            db, test_supervisor.id,
            event_types=[ActivityEventType.MEMBER_ADDED.value]
        )

        assert len(activities) == 1
        assert activities[0].event_type == ActivityEventType.MEMBER_ADDED.value

    def test_get_lab_activities_search(self, db, test_supervisor, test_user):
        """Test searching activities by text."""
        log_activity(
            db=db,
            lab_id=test_supervisor.id,
            actor_user_id=test_user.id,
            event_type=ActivityEventType.MEMBER_ADDED.value,
            entity_type=EntityType.MEMBER.value,
            entity_id=1,
            summary_text="Added alice to the lab",
        )
        log_activity(
            db=db,
            lab_id=test_supervisor.id,
            actor_user_id=test_user.id,
            event_type=ActivityEventType.MEMBER_ADDED.value,
            entity_type=EntityType.MEMBER.value,
            entity_id=2,
            summary_text="Added bob to the lab",
        )
        db.commit()

        activities = get_lab_activities(db, test_supervisor.id, search_text="alice")

        assert len(activities) == 1
        assert "alice" in activities[0].summary_text

    def test_count_lab_activities(self, db, test_supervisor, test_user):
        """Test counting activities."""
        for i in range(5):
            log_activity(
                db=db,
                lab_id=test_supervisor.id,
                actor_user_id=test_user.id,
                event_type=ActivityEventType.MEMBER_ADDED.value,
                entity_type=EntityType.MEMBER.value,
                entity_id=i + 1,
                summary_text=f"Activity {i}",
            )
        db.commit()

        count = count_lab_activities(db, test_supervisor.id)
        assert count == 5

    def test_activities_scoped_to_lab(self, db, test_supervisor, test_user):
        """Test that activities are properly scoped to their lab."""
        # Create a second supervisor
        from supervisor.models.supervisor import Supervisor
        other_supervisor = Supervisor(
            name="Other Lab",
            description="Another lab",
        )
        db.add(other_supervisor)
        db.commit()

        # Add activity to first supervisor
        log_activity(
            db=db,
            lab_id=test_supervisor.id,
            actor_user_id=test_user.id,
            event_type=ActivityEventType.MEMBER_ADDED.value,
            entity_type=EntityType.MEMBER.value,
            entity_id=1,
            summary_text="Activity in first lab",
        )
        # Add activity to second supervisor
        log_activity(
            db=db,
            lab_id=other_supervisor.id,
            actor_user_id=test_user.id,
            event_type=ActivityEventType.MEMBER_ADDED.value,
            entity_type=EntityType.MEMBER.value,
            entity_id=1,
            summary_text="Activity in second lab",
        )
        db.commit()

        # Query first lab
        activities = get_lab_activities(db, test_supervisor.id)
        assert len(activities) == 1
        assert activities[0].summary_text == "Activity in first lab"


class TestLabActivityAPI:
    """Tests for the lab activity API endpoints."""

    def test_list_activity_requires_auth(self, client, test_supervisor):
        """Test that activity endpoint requires authentication."""
        response = client.get(f"/api/supervisors/{test_supervisor.id}/activity")
        assert response.status_code == 401

    def test_list_activity_requires_membership(
        self, client, db, test_supervisor, test_user2, auth_headers_user2
    ):
        """Test that activity endpoint requires lab membership."""
        response = client.get(
            f"/api/supervisors/{test_supervisor.id}/activity",
            headers=auth_headers_user2,
        )
        assert response.status_code == 403

    def test_list_activity_returns_entries(
        self, client, db, test_supervisor, test_user, auth_headers
    ):
        """Test that activity endpoint returns entries."""
        # Create some activity
        log_activity(
            db=db,
            lab_id=test_supervisor.id,
            actor_user_id=test_user.id,
            event_type=ActivityEventType.MEMBER_ADDED.value,
            entity_type=EntityType.MEMBER.value,
            entity_id=test_user.id,
            summary_text="Test activity",
        )
        db.commit()

        response = client.get(
            f"/api/supervisors/{test_supervisor.id}/activity",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert len(data["items"]) == 1
        assert data["items"][0]["summary_text"] == "Test activity"

    def test_list_event_types(self, client, db, test_supervisor, auth_headers):
        """Test that event-types endpoint returns options."""
        response = client.get(
            f"/api/supervisors/{test_supervisor.id}/activity/event-types",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        assert all("value" in item and "label" in item for item in data)


class TestMemberActivityLogging:
    """Tests for activity logging when managing members."""

    def test_add_member_logs_activity(
        self, client, db, test_supervisor, test_user, test_user2, auth_headers
    ):
        """Test that adding a member creates an activity log."""
        response = client.post(
            f"/api/supervisors/{test_supervisor.id}/members",
            headers=auth_headers,
            json={"username": "testuser2", "role": "RESEARCHER"},
        )
        assert response.status_code == 201

        # Check activity was logged
        activities = get_lab_activities(db, test_supervisor.id)
        member_added = [a for a in activities if a.event_type == ActivityEventType.MEMBER_ADDED.value]
        assert len(member_added) == 1
        assert "testuser2" in member_added[0].summary_text.lower() or "Test User 2" in member_added[0].summary_text

    def test_update_member_role_logs_activity(
        self, client, db, test_supervisor, test_user, test_user2, auth_headers
    ):
        """Test that updating a member role creates an activity log with reason."""
        # First add the member
        from supervisor.models.supervisor_membership import SupervisorMembership, SupervisorRole
        membership = SupervisorMembership(
            supervisor_id=test_supervisor.id,
            user_id=test_user2.id,
            role=SupervisorRole.RESEARCHER,
        )
        db.add(membership)
        db.commit()

        # Update the role with reason
        response = client.patch(
            f"/api/supervisors/{test_supervisor.id}/members/{test_user2.id}",
            headers=auth_headers,
            json={"role": "STEWARD", "reason": "Promoted for excellent work"},
        )
        assert response.status_code == 200

        # Check activity was logged
        activities = get_lab_activities(db, test_supervisor.id)
        role_changed = [a for a in activities if a.event_type == ActivityEventType.MEMBER_ROLE_CHANGED.value]
        assert len(role_changed) == 1
        assert role_changed[0].reason_text == "Promoted for excellent work"

    def test_update_member_role_requires_reason(
        self, client, db, test_supervisor, test_user, test_user2, auth_headers
    ):
        """Test that updating a member role requires a reason."""
        # First add the member
        from supervisor.models.supervisor_membership import SupervisorMembership, SupervisorRole
        membership = SupervisorMembership(
            supervisor_id=test_supervisor.id,
            user_id=test_user2.id,
            role=SupervisorRole.RESEARCHER,
        )
        db.add(membership)
        db.commit()

        # Try to update without reason (should fail validation)
        response = client.patch(
            f"/api/supervisors/{test_supervisor.id}/members/{test_user2.id}",
            headers=auth_headers,
            json={"role": "STEWARD"},  # Missing reason
        )
        assert response.status_code == 422  # Validation error

    def test_remove_member_logs_activity(
        self, client, db, test_supervisor, test_user, test_user2, auth_headers
    ):
        """Test that removing a member creates an activity log."""
        # First add the member
        from supervisor.models.supervisor_membership import SupervisorMembership, SupervisorRole
        membership = SupervisorMembership(
            supervisor_id=test_supervisor.id,
            user_id=test_user2.id,
            role=SupervisorRole.RESEARCHER,
        )
        db.add(membership)
        db.commit()

        # Remove the member
        response = client.delete(
            f"/api/supervisors/{test_supervisor.id}/members/{test_user2.id}",
            headers=auth_headers,
        )
        assert response.status_code == 204

        # Check activity was logged
        activities = get_lab_activities(db, test_supervisor.id)
        member_removed = [a for a in activities if a.event_type == ActivityEventType.MEMBER_REMOVED.value]
        assert len(member_removed) == 1
