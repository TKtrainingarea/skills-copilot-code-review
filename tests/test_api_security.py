from pathlib import Path
from types import SimpleNamespace
import sys

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import src.backend.database as database
import src.backend.routers.activities as activities_router
import src.backend.routers.auth as auth_router


class FakeCollection:
    def __init__(self, docs):
        self.docs = docs

    def find_one(self, query):
        if not query:
            return None
        if "_id" in query:
            return self.docs.get(query["_id"])
        return None

    def update_one(self, query, update):
        document = self.docs[query["_id"]]
        if "$set" in update:
            document.update(update["$set"])
        if "$push" in update:
            participants = document.setdefault("participants", [])
            participants.append(update["$push"]["participants"])
        if "$pull" in update:
            participants = document.setdefault("participants", [])
            email = update["$pull"]["participants"]
            document["participants"] = [value for value in participants if value != email]
        return SimpleNamespace(modified_count=1)

    def count_documents(self, query=None):
        return len(self.docs)


@pytest.fixture
def fake_data(monkeypatch):
    teacher_collection = FakeCollection(
        {
            "mchen": {
                "_id": "mchen",
                "username": "mchen",
                "display_name": "Mr. Chen",
                "password": database.hash_password("chess456"),
                "role": "teacher",
                "session_token": None,
            }
        }
    )
    activity_collection = FakeCollection(
        {
            "Chess Club": {
                "_id": "Chess Club",
                "description": "Learn strategies and compete in chess tournaments",
                "schedule": "Mondays and Fridays, 3:15 PM - 4:45 PM",
                "schedule_details": {
                    "days": ["Monday", "Friday"],
                    "start_time": "15:15",
                    "end_time": "16:45",
                },
                "max_participants": 2,
                "participants": ["existing@example.com"],
            }
        }
    )

    monkeypatch.setattr(database, "teachers_collection", teacher_collection)
    monkeypatch.setattr(database, "activities_collection", activity_collection)
    monkeypatch.setattr(auth_router, "teachers_collection", teacher_collection)
    monkeypatch.setattr(activities_router, "teachers_collection", teacher_collection)
    monkeypatch.setattr(activities_router, "activities_collection", activity_collection)

    return teacher_collection, activity_collection


def test_login_returns_session_token_and_records_teacher_session(fake_data):
    teachers, _ = fake_data

    result = auth_router.login("mchen", "chess456")

    assert result["username"] == "mchen"
    assert result["session_token"]
    assert teachers.docs["mchen"]["session_token"] == result["session_token"]


def test_signup_requires_valid_session_token(fake_data):
    teachers, _ = fake_data
    teachers.docs["mchen"]["session_token"] = "valid-session"

    with pytest.raises(HTTPException, match="Authentication required|Invalid.*session"):
        activities_router.signup_for_activity(
            "Chess Club",
            "new-student@example.com",
            teacher_username="mchen",
            teacher_session_token="wrong-session",
        )


def test_signup_rejects_full_activity(fake_data):
    teachers, activities = fake_data
    teachers.docs["mchen"]["session_token"] = "valid-session"
    activities.docs["Chess Club"]["participants"] = [
        "existing@example.com",
        "another@example.com",
    ]

    with pytest.raises(HTTPException, match="full|Full"):
        activities_router.signup_for_activity(
            "Chess Club",
            "new-student@example.com",
            teacher_username="mchen",
            teacher_session_token="valid-session",
        )
