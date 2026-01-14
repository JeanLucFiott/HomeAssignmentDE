"""
Event Management API
A FastAPI application for managing events, attendees, venues, and ticket bookings
with multimedia support for event promotion and venue information.
"""

import os
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv
from enum import Enum
from pymongo import MongoClient
from bson.objectid import ObjectId
import io
import re
from pathlib import Path

# Load environment variables from .env file
load_dotenv()

# Initialize FastAPI application
app = FastAPI()

# Connect to MongoDB Atlas cluster using connection string from environment
client = MongoClient(os.getenv("MONGO_CONNECTION_STRING"))
db = client.event_management_db

# ==================== SANITIZATION & VALIDATION HELPERS ====================

def validate_object_id(id_string: str) -> ObjectId:
    """Validate and convert string to ObjectId, raising exception if invalid"""
    try:
        return ObjectId(id_string)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

def sanitize_string(value: str, field_name: str = "field") -> str:
    """Sanitize string input to prevent injection attacks"""
    if not isinstance(value, str):
        return value
    # Remove null bytes which could cause issues
    value = value.replace('\x00', '')
    # Limit length to prevent DOS
    if len(value) > 5000:
        raise ValueError(f"{field_name} exceeds maximum length of 5000 characters")
    return value.strip()

def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal attacks"""
    # Get just the filename, removing any path components
    filename = Path(filename).name
    # Remove dangerous characters
    filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', filename)
    # Remove directory traversal attempts
    filename = filename.replace('..', '')
    # Ensure filename is not empty
    if not filename:
        filename = "file"
    # Limit length
    if len(filename) > 255:
        filename = filename[:255]
    return filename

# ==================== DATA MODELS ====================

class MediaType(str, Enum):
    # Enum for different types of multimedia content
    poster = "poster"
    promo_video = "promo_video"
    venue_photo = "venue_photo"

class Event(BaseModel):
    # Pydantic model for event data validation
    name: str
    description: str
    date: str
    venue_id: str
    max_attendees: int

    @field_validator('name', 'description', mode='before')
    @classmethod
    def sanitize_text_fields(cls, v):
        if isinstance(v, str):
            return sanitize_string(v)
        return v

    @field_validator('date', mode='before')
    @classmethod
    def validate_date(cls, v):
        if isinstance(v, str):
            v = sanitize_string(v)
            # Basic date format validation
            try:
                datetime.fromisoformat(v)
            except ValueError:
                raise ValueError('Invalid date format')
        return v

    @field_validator('max_attendees', mode='before')
    @classmethod
    def validate_attendees(cls, v):
        if not isinstance(v, int) or v < 0:
            raise ValueError('max_attendees must be a positive integer')
        return v

class Attendee(BaseModel):
    # Pydantic model for attendee data validation
    name: str
    email: str
    phone: Optional[str] = None

    @field_validator('name', mode='before')
    @classmethod
    def sanitize_name(cls, v):
        if isinstance(v, str):
            return sanitize_string(v)
        return v

    @field_validator('email', mode='before')
    @classmethod
    def validate_email(cls, v):
        if isinstance(v, str):
            v = sanitize_string(v)
            # Basic email validation
            if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
                raise ValueError('Invalid email format')
        return v

    @field_validator('phone', mode='before')
    @classmethod
    def validate_phone(cls, v):
        if v is not None and isinstance(v, str):
            v = sanitize_string(v)
            # Basic phone validation (allows digits, +, -, spaces, parentheses)
            if not re.match(r'^[\d+\-() ]{7,}$', v):
                raise ValueError('Invalid phone format')
        return v

class Venue(BaseModel):
    # Pydantic model for venue data validation
    name: str
    address: str
    capacity: int

    @field_validator('name', 'address', mode='before')
    @classmethod
    def sanitize_venue_fields(cls, v):
        if isinstance(v, str):
            return sanitize_string(v)
        return v

    @field_validator('capacity', mode='before')
    @classmethod
    def validate_capacity(cls, v):
        if not isinstance(v, int) or v < 0:
            raise ValueError('capacity must be a positive integer')
        return v

class Booking(BaseModel):
    # Pydantic model for ticket booking data validation
    event_id: str
    attendee_id: str
    ticket_type: str
    quantity: int

    @field_validator('ticket_type', mode='before')
    @classmethod
    def sanitize_ticket_type(cls, v):
        if isinstance(v, str):
            return sanitize_string(v)
        return v

    @field_validator('quantity', mode='before')
    @classmethod
    def validate_quantity(cls, v):
        if not isinstance(v, int) or v <= 0:
            raise ValueError('quantity must be a positive integer')
        return v

class EventMultimedia(BaseModel):
    # Pydantic model for multimedia content data validation
    event_id: Optional[str] = None
    venue_id: Optional[str] = None
    filename: str
    content_type: str
    media_type: MediaType

# ==================== EVENT ENDPOINTS ====================

@app.post("/events")
def create_event(event: Event):
    # Create a new event in the database
    event_doc = event.dict()
    result = db.events.insert_one(event_doc)
    return {"message": "Event created", "id": str(result.inserted_id)}

@app.get("/events")
def get_events():
    # Retrieve all events from the database
    events = list(db.events.find())
    # Convert MongoDB ObjectId to string for JSON serialization
    for event in events:
        event["_id"] = str(event["_id"])
    return events

@app.get("/events/{event_id}")
def get_event(event_id: str):
    # Retrieve a specific event by ID
    try:
        # Query event by ObjectId
        obj_id = validate_object_id(event_id)
        event = db.events.find_one({"_id": obj_id})
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        event["_id"] = str(event["_id"])
        return event
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid event ID")

@app.put("/events/{event_id}")
def update_event(event_id: str, event: Event):
    # Update an existing event by ID
    try:
        # Update event with provided data
        obj_id = validate_object_id(event_id)
        result = db.events.update_one(
            {"_id": obj_id},
            {"$set": event.dict()}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Event not found")
        return {"message": "Event updated", "id": event_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid event ID")

@app.delete("/events/{event_id}")
def delete_event(event_id: str):
    # Delete an event by ID
    try:
        obj_id = validate_object_id(event_id)
        result = db.events.delete_one({"_id": obj_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Event not found")
        return {"message": "Event deleted", "id": event_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid event ID")

# ==================== ATTENDEE ENDPOINTS ====================

@app.post("/attendees")
def register_attendee(attendee: Attendee):
    # Register a new attendee in the system
    attendee_doc = attendee.dict()
    attendee_doc["registered_at"] = datetime.utcnow()
    result = db.attendees.insert_one(attendee_doc)
    return {"message": "Attendee registered", "id": str(result.inserted_id)}

@app.get("/attendees")
def get_attendees():
    # Retrieve all attendees from the database
    attendees = list(db.attendees.find())
    for attendee in attendees:
        attendee["_id"] = str(attendee["_id"])
    return attendees

@app.get("/attendees/{attendee_id}")
def get_attendee(attendee_id: str):
    # Retrieve a specific attendee by ID
    try:
        obj_id = validate_object_id(attendee_id)
        attendee = db.attendees.find_one({"_id": obj_id})
        if not attendee:
            raise HTTPException(status_code=404, detail="Attendee not found")
        attendee["_id"] = str(attendee["_id"])
        return attendee
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid attendee ID")

@app.put("/attendees/{attendee_id}")
def update_attendee(attendee_id: str, attendee: Attendee):
    # Update an existing attendee's information by ID
    try:
        obj_id = validate_object_id(attendee_id)
        result = db.attendees.update_one(
            {"_id": obj_id},
            {"$set": attendee.dict()}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Attendee not found")
        return {"message": "Attendee updated", "id": attendee_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid attendee ID")

@app.delete("/attendees/{attendee_id}")
def delete_attendee(attendee_id: str):
    # Delete an attendee record by ID
    try:
        obj_id = validate_object_id(attendee_id)
        result = db.attendees.delete_one({"_id": obj_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Attendee not found")
        return {"message": "Attendee deleted", "id": attendee_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid attendee ID")

# ==================== VENUE ENDPOINTS ====================

@app.post("/venues")
def create_venue(venue: Venue):
    # Add a new venue to the system
    venue_doc = venue.dict()
    venue_doc["created_at"] = datetime.utcnow()
    result = db.venues.insert_one(venue_doc)
    return {"message": "Venue created", "id": str(result.inserted_id)}

@app.get("/venues")
def get_venues():
    # Retrieve all venues from the database
    venues = list(db.venues.find())
    for venue in venues:
        venue["_id"] = str(venue["_id"])
    return venues

@app.get("/venues/{venue_id}")
def get_venue(venue_id: str):
    # Retrieve a specific venue by ID
    try:
        obj_id = validate_object_id(venue_id)
        venue = db.venues.find_one({"_id": obj_id})
        if not venue:
            raise HTTPException(status_code=404, detail="Venue not found")
        venue["_id"] = str(venue["_id"])
        return venue
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid venue ID")

@app.put("/venues/{venue_id}")
def update_venue(venue_id: str, venue: Venue):
    # Update an existing venue's information by ID
    try:
        obj_id = validate_object_id(venue_id)
        result = db.venues.update_one(
            {"_id": obj_id},
            {"$set": venue.dict()}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Venue not found")
        return {"message": "Venue updated", "id": venue_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid venue ID")

@app.delete("/venues/{venue_id}")
def delete_venue(venue_id: str):
    # Delete a venue record by ID
    try:
        obj_id = validate_object_id(venue_id)
        result = db.venues.delete_one({"_id": obj_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Venue not found")
        return {"message": "Venue deleted", "id": venue_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid venue ID")

# ==================== BOOKING ENDPOINTS ====================

@app.post("/bookings")
def create_booking(booking: Booking):
    # Create a new ticket booking for an event
    booking_doc = booking.dict()
    booking_doc["booked_at"] = datetime.utcnow()
    result = db.bookings.insert_one(booking_doc)
    return {"message": "Booking created", "id": str(result.inserted_id)}

@app.get("/bookings")
def get_bookings():
    # Retrieve all bookings from the database
    bookings = list(db.bookings.find())
    for booking in bookings:
        booking["_id"] = str(booking["_id"])
    return bookings

@app.get("/bookings/{booking_id}")
def get_booking(booking_id: str):
    # Retrieve a specific booking by ID
    try:
        obj_id = validate_object_id(booking_id)
        booking = db.bookings.find_one({"_id": obj_id})
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        booking["_id"] = str(booking["_id"])
        return booking
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid booking ID")

@app.put("/bookings/{booking_id}")
def update_booking(booking_id: str, booking: Booking):
    # Update an existing booking by ID
    try:
        obj_id = validate_object_id(booking_id)
        result = db.bookings.update_one(
            {"_id": obj_id},
            {"$set": booking.dict()}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Booking not found")
        return {"message": "Booking updated", "id": booking_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid booking ID")

@app.delete("/bookings/{booking_id}")
def delete_booking(booking_id: str):
    # Delete a booking record by ID
    try:
        obj_id = validate_object_id(booking_id)
        result = db.bookings.delete_one({"_id": obj_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Booking not found")
        return {"message": "Booking deleted", "id": booking_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid booking ID")

# ==================== MULTIMEDIA ENDPOINTS ====================

@app.post("/upload_event_poster/{event_id}")
def upload_event_poster(event_id: str, file: UploadFile = File(...)):
    # Upload a poster image for an event
    try:
        obj_id = validate_object_id(event_id)
        content = file.file.read()
        if not file.filename:
            raise ValueError("Filename is required")
        sanitized_filename = sanitize_filename(file.filename or "file")
        poster_doc = {
            "event_id": str(obj_id),
            "filename": sanitized_filename,
            "content_type": file.content_type,
            "media_type": MediaType.poster.value,
            "content": content,
            "uploaded_at": datetime.utcnow()
        }
        result = db.event_posters.insert_one(poster_doc)
        return {"message": "Event poster uploaded", "id": str(result.inserted_id)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail="Failed to upload poster")

@app.post("/upload_promo_video/{event_id}")
def upload_promo_video(event_id: str, file: UploadFile = File(...)):
    # Upload a promotional video for an event
    try:
        obj_id = validate_object_id(event_id)
        content = file.file.read()
        if not file.filename:
            raise ValueError("Filename is required")
        sanitized_filename = sanitize_filename(file.filename or "file")
        video_doc = {
            "event_id": str(obj_id),
            "filename": sanitized_filename,
            "content_type": file.content_type,
            "media_type": MediaType.promo_video.value,
            "content": content,
            "uploaded_at": datetime.utcnow()
        }
        result = db.promo_videos.insert_one(video_doc)
        return {"message": "Promotional video uploaded", "id": str(result.inserted_id)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail="Failed to upload video")

@app.post("/upload_venue_photo/{venue_id}")
def upload_venue_photo(venue_id: str, file: UploadFile = File(...)):
    # Upload a photo image for a venue
    try:
        obj_id = validate_object_id(venue_id)
        content = file.file.read()
        sanitized_filename = sanitize_filename(file.filename or "file")
        photo_doc = {
            "venue_id": str(obj_id),
            "filename": sanitized_filename,
            "content_type": file.content_type,
            "media_type": MediaType.venue_photo.value,
            "content": content,
            "uploaded_at": datetime.utcnow()
        }
        result = db.venue_photos.insert_one(photo_doc)
        return {"message": "Venue photo uploaded", "id": str(result.inserted_id)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail="Failed to upload photo")