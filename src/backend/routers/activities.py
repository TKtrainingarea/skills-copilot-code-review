"""
Endpoints for the High School Management System API
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from ..database import activities_collection, teachers_collection

router = APIRouter(
    prefix="/activities",
    tags=["activities"]
)


def require_teacher_session(
    teacher_username: Optional[str],
    teacher_session_token: Optional[str],
) -> Dict[str, Any]:
    """Validate a teacher session before allowing activity management actions."""
    if not teacher_username or not teacher_session_token:
        raise HTTPException(
            status_code=401,
            detail="Authentication required for this action",
        )

    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(
            status_code=401,
            detail="Invalid teacher credentials",
        )

    if teacher.get("role") not in {"teacher", "admin"}:
        raise HTTPException(
            status_code=403,
            detail="Teacher access required",
        )

    if teacher.get("session_token") != teacher_session_token:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session",
        )

    return teacher


@router.get("", response_model=Dict[str, Any])
@router.get("/", response_model=Dict[str, Any])
def get_activities(
    day: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get all activities with their details, with optional filtering by day and time

    - day: Filter activities occurring on this day (e.g., 'Monday', 'Tuesday')
    - start_time: Filter activities starting at or after this time (24-hour format, e.g., '14:30')
    - end_time: Filter activities ending at or before this time (24-hour format, e.g., '17:00')
    """
    # Build the query based on provided filters
    query = {}

    if day:
        query["schedule_details.days"] = {"$in": [day]}

    if start_time:
        query["schedule_details.start_time"] = {"$gte": start_time}

    if end_time:
        query["schedule_details.end_time"] = {"$lte": end_time}

    # Query the database
    activities = {}
    for activity in activities_collection.find(query):
        name = activity.pop('_id')
        activities[name] = activity

    return activities


@router.get("/days", response_model=List[str])
def get_available_days() -> List[str]:
    """Get a list of all days that have activities scheduled"""
    # Aggregate to get unique days across all activities
    pipeline = [
        {"$unwind": "$schedule_details.days"},
        {"$group": {"_id": "$schedule_details.days"}},
        {"$sort": {"_id": 1}}  # Sort days alphabetically
    ]

    days = []
    for day_doc in activities_collection.aggregate(pipeline):
        days.append(day_doc["_id"])

    return days


@router.post("/{activity_name}/signup")
def signup_for_activity(
    activity_name: str,
    email: str,
    teacher_username: Optional[str] = Query(None),
    teacher_session_token: Optional[str] = Query(None),
):
    """Sign up a student for an activity - requires teacher authentication."""
    require_teacher_session(teacher_username, teacher_session_token)

    activity = activities_collection.find_one({"_id": activity_name})
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    participants = activity.get("participants", [])
    if email in participants:
        raise HTTPException(
            status_code=400,
            detail="Already signed up for this activity",
        )

    max_participants = activity.get("max_participants")
    if max_participants is not None and len(participants) >= max_participants:
        raise HTTPException(
            status_code=400,
            detail="Activity is full",
        )

    result = activities_collection.update_one(
        {"_id": activity_name},
        {"$push": {"participants": email}},
    )

    if result.modified_count == 0:
        raise HTTPException(
            status_code=500,
            detail="Failed to update activity",
        )

    return {"message": f"Signed up {email} for {activity_name}"}


@router.post("/{activity_name}/unregister")
def unregister_from_activity(
    activity_name: str,
    email: str,
    teacher_username: Optional[str] = Query(None),
    teacher_session_token: Optional[str] = Query(None),
):
    """Remove a student from an activity - requires teacher authentication."""
    require_teacher_session(teacher_username, teacher_session_token)

    activity = activities_collection.find_one({"_id": activity_name})
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    if email not in activity.get("participants", []):
        raise HTTPException(
            status_code=400,
            detail="Not registered for this activity",
        )

    result = activities_collection.update_one(
        {"_id": activity_name},
        {"$pull": {"participants": email}},
    )

    if result.modified_count == 0:
        raise HTTPException(
            status_code=500,
            detail="Failed to update activity",
        )

    return {"message": f"Unregistered {email} from {activity_name}"}
