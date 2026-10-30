"""
Authentication endpoints for the High School Management System API
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

from ..database import generate_session_token, teachers_collection, verify_password

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)


@router.post("/login")
def login(username: str, password: str) -> Dict[str, Any]:
    """Login a teacher account."""
    teacher = teachers_collection.find_one({"_id": username})

    if not teacher or not verify_password(teacher.get("password", ""), password):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password",
        )

    session_token = generate_session_token()
    teachers_collection.update_one(
        {"_id": username},
        {"$set": {"session_token": session_token}},
    )

    return {
        "username": teacher["username"],
        "display_name": teacher["display_name"],
        "role": teacher["role"],
        "session_token": session_token,
    }


@router.get("/check-session")
def check_session(username: str, session_token: Optional[str] = None) -> Dict[str, Any]:
    """Validate an active teacher session."""
    teacher = teachers_collection.find_one({"_id": username})

    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    if not session_token or teacher.get("session_token") != session_token:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    return {
        "username": teacher["username"],
        "display_name": teacher["display_name"],
        "role": teacher["role"],
        "session_token": teacher["session_token"],
    }
