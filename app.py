import os
import re
import uvicorn
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import datetime, UTC
from dotenv import load_dotenv
from enum import Enum
from pymongo import MongoClient
from bson.objectid import ObjectId
from pathlib import Path

# Load environment variables from .env file
load_dotenv()

# Initialize FastAPI application
app = FastAPI()

# Configure CORS from environment variables
cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
cors_credentials = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"
cors_methods = os.getenv("CORS_ALLOW_METHODS", "*").split(",")
cors_headers = os.getenv("CORS_ALLOW_HEADERS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=cors_credentials,
    allow_methods=cors_methods,
    allow_headers=cors_headers,
)

# Mount static files directory
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Connect to MongoDB Atlas cluster using connection string from environment
client = MongoClient(os.getenv("MONGO_CONNECTION_STRING"))
db = client.event_management_db

# ==================== ROOT ENDPOINT ====================

@app.get("/")
def read_root():
    """Display all available API endpoints"""
    return {
        "message": "Welcome to Event Management API",
        "documentation": "http://127.0.0.1:8000/docs",
        "test_suite": "http://127.0.0.1:8000/static/test_suite.html",
        "endpoints": {
            "events": {
                "POST /events": "Create a new event",
                "GET /events": "Get all events",
                "GET /events/{event_id}": "Get a specific event",
                "PUT /events/{event_id}": "Update an event",
                "DELETE /events/{event_id}": "Delete an event"
            },
            "attendees": {
                "POST /attendees": "Register a new attendee",
                "GET /attendees": "Get all attendees",
                "GET /attendees/{attendee_id}": "Get a specific attendee",
                "PUT /attendees/{attendee_id}": "Update attendee information",
                "DELETE /attendees/{attendee_id}": "Delete an attendee"
            },
            "venues": {
                "POST /venues": "Create a new venue",
                "GET /venues": "Get all venues",
                "GET /venues/{venue_id}": "Get a specific venue",
                "PUT /venues/{venue_id}": "Update venue information",
                "DELETE /venues/{venue_id}": "Delete a venue"
            },
            "bookings": {
                "POST /bookings": "Create a new booking",
                "GET /bookings": "Get all bookings",
                "GET /bookings/{booking_id}": "Get a specific booking",
                "PUT /bookings/{booking_id}": "Update booking information",
                "DELETE /bookings/{booking_id}": "Delete a booking"
            },
            "multimedia": {
                "POST /upload_event_poster/{event_id}": "Upload an event poster",
                "POST /upload_promo_video/{event_id}": "Upload a promotional video",
                "POST /upload_venue_photo/{venue_id}": "Upload a venue photo"
            }
        }
    }

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
    attendee_ids: List[str]  # One booking can have multiple attendees
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
    event_doc = event.model_dump()
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
            {"$set": event.model_dump()}
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
    attendee_doc = attendee.model_dump()
    attendee_doc["registered_at"] = datetime.now(UTC)
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
            {"$set": attendee.model_dump()}
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
    venue_doc = venue.model_dump()
    venue_doc["created_at"] = datetime.now(UTC)
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
            {"$set": venue.model_dump()}
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
    booking_doc = booking.model_dump()
    booking_doc["booked_at"] = datetime.now(UTC)
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
            {"$set": booking.model_dump()}
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
            "uploaded_at": datetime.now(UTC)
        }
        result = db.event_posters.insert_one(poster_doc)
        return {"message": "Event poster uploaded", "id": str(result.inserted_id)}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Poster upload error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to upload poster: {str(e)}")

@app.get("/event_poster/{event_id}")
def get_event_poster(event_id: str):
    # Retrieve all poster images for an event
    try:
        obj_id = validate_object_id(event_id)
        posters = list(db.event_posters.find(
            {"event_id": str(obj_id)},
            sort=[("uploaded_at", -1)]
        ))
        if not posters:
            raise HTTPException(status_code=404, detail="No posters found")
        # Return metadata about all posters
        return [
            {
                "id": str(poster["_id"]),
                "filename": poster.get("filename", "unknown"),
                "content_type": poster.get("content_type", "image/jpeg"),
                "uploaded_at": poster.get("uploaded_at", None),
                "download_url": f"/media/poster/{str(poster['_id'])}"
            }
            for poster in posters
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail="Failed to retrieve posters")

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
            "uploaded_at": datetime.now(UTC)
        }
        result = db.promo_videos.insert_one(video_doc)
        return {"message": "Promotional video uploaded", "id": str(result.inserted_id)}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Video upload error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to upload video: {str(e)}")

@app.get("/promo_video/{event_id}")
def get_promo_video(event_id: str):
    # Retrieve all promotional videos for an event
    try:
        obj_id = validate_object_id(event_id)
        videos = list(db.promo_videos.find(
            {"event_id": str(obj_id)},
            sort=[("uploaded_at", -1)]
        ))
        if not videos:
            raise HTTPException(status_code=404, detail="No promo videos found")
        # Return metadata about all videos
        return [
            {
                "id": str(video["_id"]),
                "filename": video.get("filename", "unknown"),
                "content_type": video.get("content_type", "video/mp4"),
                "uploaded_at": video.get("uploaded_at", None),
                "download_url": f"/media/video/{str(video['_id'])}"
            }
            for video in videos
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail="Failed to retrieve promo videos")

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
            "uploaded_at": datetime.now(UTC)
        }
        result = db.venue_photos.insert_one(photo_doc)
        return {"message": "Venue photo uploaded", "id": str(result.inserted_id)}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Photo upload error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to upload photo: {str(e)}")

@app.get("/venue_photo/{venue_id}")
def get_venue_photo(venue_id: str):
    # Retrieve all photos for a venue
    try:
        obj_id = validate_object_id(venue_id)
        photos = list(db.venue_photos.find(
            {"venue_id": str(obj_id)},
            sort=[("uploaded_at", -1)]
        ))
        if not photos:
            raise HTTPException(status_code=404, detail="No venue photos found")
        # Return metadata about all photos
        return [
            {
                "id": str(photo["_id"]),
                "filename": photo.get("filename", "unknown"),
                "content_type": photo.get("content_type", "image/jpeg"),
                "uploaded_at": photo.get("uploaded_at", None),
                "download_url": f"/media/photo/{str(photo['_id'])}"
            }
            for photo in photos
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail="Failed to retrieve venue photos")

@app.get("/media/poster/{poster_id}")
def download_event_poster(poster_id: str):
    # Download a specific event poster by ID
    try:
        obj_id = validate_object_id(poster_id)
        poster = db.event_posters.find_one({"_id": obj_id})
        if not poster:
            raise HTTPException(status_code=404, detail="Poster not found")
        return StreamingResponse(
            iter([poster["content"]]),
            media_type=poster.get("content_type", "image/jpeg"),
            headers={"Content-Disposition": f"attachment; filename={poster.get('filename', 'poster.jpg')}"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail="Failed to download poster")

@app.get("/media/video/{video_id}")
def download_promo_video(video_id: str):
    # Download a specific promotional video by ID
    try:
        obj_id = validate_object_id(video_id)
        video = db.promo_videos.find_one({"_id": obj_id})
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        return StreamingResponse(
            iter([video["content"]]),
            media_type=video.get("content_type", "video/mp4"),
            headers={"Content-Disposition": f"attachment; filename={video.get('filename', 'video.mp4')}"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail="Failed to download video")

@app.get("/media/photo/{photo_id}")
def download_venue_photo(photo_id: str):
    # Download a specific venue photo by ID
    try:
        obj_id = validate_object_id(photo_id)
        photo = db.venue_photos.find_one({"_id": obj_id})
        if not photo:
            raise HTTPException(status_code=404, detail="Photo not found")
        return StreamingResponse(
            iter([photo["content"]]),
            media_type=photo.get("content_type", "image/jpeg"),
            headers={"Content-Disposition": f"attachment; filename={photo.get('filename', 'photo.jpg')}"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail="Failed to download photo")



if __name__ == "__main__":

    uvicorn.run(app, host="127.0.0.1", port=8000)