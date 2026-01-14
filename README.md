# Database Essentials - Home Assignment

## Project Overview

This project is a Home Assignment for the Database Essentials course. It utilizes a modern Python web framework with asynchronous database access to demonstrate core database concepts and best practices.

## Development Environment

### Environment Overview

This project utilizes a Python-based asynchronous development environment designed for building modern web APIs with database integration. The environment consists of three primary components that work together to provide a complete web application stack.

### Technology Stack

#### FastAPI - Web Framework
FastAPI is a modern, high-performance Python web framework built on top of Starlette. It enables the construction of RESTful APIs with automatic validation, serialization, and documentation. FastAPI's key advantages include:
- Native support for asynchronous programming (async/await)
- Automatic interactive API documentation generation (Swagger UI and ReDoc)
- Built-in data validation using Pydantic models
- High performance comparable to Node.js and Go frameworks
- Type hints and static analysis capabilities

#### Uvicorn - ASGI Server
Uvicorn is an ASGI (Asynchronous Server Gateway Interface) server that serves FastAPI applications. It acts as the intermediary between HTTP requests and the FastAPI application, handling concurrent connections efficiently. The server:
- Manages incoming HTTP requests and routes them to the FastAPI application
- Handles multiple concurrent connections asynchronously
- Provides development server with hot-reloading capabilities for rapid development iteration
- Supports production-grade deployment configurations

#### PyMongo - MongoDB Driver
PyMongo is the official MongoDB driver for Python that provides synchronous access to MongoDB databases. It enables direct communication with MongoDB instances:
- Provides full MongoDB query language support
- Manages database connections and connection pooling
- Supports both local MongoDB instances and MongoDB Atlas clusters
- Offers comprehensive CRUD operations for document manipulation
- Includes support for bulk operations and aggregation pipelines

#### Pydantic - Data Validation
Pydantic is a data validation library using Python type annotations. It ensures data integrity at the API layer:
- Validates request data against defined models
- Automatically serializes and deserializes JSON
- Provides detailed error messages for validation failures
- Supports complex nested data structures and custom validators

#### Python-dotenv - Environment Configuration
Python-dotenv loads environment variables from `.env` files into the application runtime:
- Securely manages sensitive configuration (database connection strings, API keys)
- Enables environment-specific configuration without code changes
- Separates configuration from code for better security practices

#### Requests - HTTP Library
Requests is a popular HTTP library for Python:
- Simplifies making HTTP requests to external APIs
- Handles connection pooling and session management
- Supports authentication, cookies, and custom headers
- Can be used for integrating with third-party services

### Virtual Environment

The project uses Python's built-in virtual environment (`venv`) to create an isolated development environment. This separation ensures:
- Dependencies are isolated from the system Python installation
- Package versions remain consistent and predictable
- Multiple projects can coexist without dependency conflicts
- Reproducible environments across different development machines

All dependencies and their specific versions are documented in `requirements.txt`, enabling consistent replication of the environment.

### Version Control

Git provides comprehensive version control for the project, tracking all changes to code, configuration files, and documentation. This enables:
- Complete project history and changesets
- Collaboration and code review capabilities
- Branch management for feature development and bug fixes
- Documentation of development progress and decisions

### Architecture

The environment follows an asynchronous, event-driven architecture where:
1. Uvicorn receives HTTP requests and dispatches them to FastAPI
2. FastAPI processes requests concurrently using async/await patterns
3. Motor handles asynchronous database operations without blocking
4. Responses are returned to clients with minimal latency and maximum throughput

This architecture enables efficient handling of multiple concurrent requests while maintaining clean, readable code through Python's async/await syntax.

### Common Git Commands
```bash
git status              # Check repository status
git add .              # Stage changes
git commit -m "message" # Commit changes
git push               # Push changes to remote
git log                # View commit history
```

## Technologies Used

| Technology | Purpose | Version |
|-----------|---------|---------|
| FastAPI | Web framework for building RESTful APIs | 0.128.0+ |
| Uvicorn | ASGI server for running FastAPI applications | 0.40.0+ |
| PyMongo | MongoDB database driver | 4.9+ |
| Pydantic | Data validation and serialization | 2.12.5+ |
| Python-dotenv | Environment variable management | 1.2.1+ |
| Requests | HTTP client library | 2.32.5+ |
| Python-multipart | Support for file uploads in FastAPI | 0.0.5+ |

## Getting Started

### Prerequisites
- Python 3.9 or higher
- MongoDB instance (local or Atlas)
- Virtual environment activated

### Installation

1. **Clone the repository** (if applicable)
```bash
git clone <repository-url>
cd HomeAssignment
```

2. **Activate the virtual environment**
```bash
# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables**
Create a `.env` file in the project root:
```env
MONGO_CONNECTION_STRING=your_mongodb_connection_string
```

5. **Run the server**
```bash
python -m uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

### Running the Test Suite

Once the server is running, access the test suite:

**URL:** `http://127.0.0.1:8000/static/test_suite.html`

The test suite provides an interactive web interface to test all API endpoints:
- **Events Management**: Create, read, update, and delete events
- **Attendees Management**: Register and manage event attendees
- **Venues Management**: Create and manage venue information
- **Bookings Management**: Create and manage ticket bookings
- **Multimedia Management**: Upload event posters, promotional videos, and venue photos

#### Test Suite Features
1. **Base URL Configuration** - Modify the API endpoint URL if needed (default: http://127.0.0.1:8000)
2. **ID Storage** - Automatically stores created resource IDs for easy reference
3. **Response Display** - Shows HTTP status codes and JSON responses
4. **All CRUD Operations** - Test all Create, Read, Update, and Delete operations
5. **File Upload** - Test multimedia upload functionality

#### Example Workflow
1. Open the test suite in your browser
2. Go to the **Venues** tab and create a new venue
3. Note the returned venue ID from the response
4. Go to the **Events** tab and create a new event (use the venue ID)
5. Go to the **Attendees** tab and register attendees
6. Go to the **Bookings** tab and create bookings for your event
7. Go to the **Multimedia** tab to upload posters and videos

## API Endpoints

### Events
- `POST /events` - Create a new event
- `GET /events` - Get all events
- `GET /events/{event_id}` - Get a specific event
- `PUT /events/{event_id}` - Update an event
- `DELETE /events/{event_id}` - Delete an event

### Attendees
- `POST /attendees` - Register a new attendee
- `GET /attendees` - Get all attendees
- `GET /attendees/{attendee_id}` - Get a specific attendee
- `PUT /attendees/{attendee_id}` - Update attendee information
- `DELETE /attendees/{attendee_id}` - Delete an attendee

### Venues
- `POST /venues` - Create a new venue
- `GET /venues` - Get all venues
- `GET /venues/{venue_id}` - Get a specific venue
- `PUT /venues/{venue_id}` - Update venue information
- `DELETE /venues/{venue_id}` - Delete a venue

### Bookings
- `POST /bookings` - Create a new booking
- `GET /bookings` - Get all bookings
- `GET /bookings/{booking_id}` - Get a specific booking
- `PUT /bookings/{booking_id}` - Update booking information
- `DELETE /bookings/{booking_id}` - Delete a booking

### Multimedia
- `POST /upload_event_poster/{event_id}` - Upload an event poster
- `POST /upload_promo_video/{event_id}` - Upload a promotional video
- `POST /upload_venue_photo/{venue_id}` - Upload a venue photo

## Notes

- Ensure the virtual environment is activated before running any commands
- Keep `requirements.txt` updated when adding new dependencies
- Follow the project's git commit conventions for clear version history
- All development should be done within the virtual environment to avoid system-wide package conflicts
- CORS is enabled to allow test suite communication with the API
- File uploads support common image and video formats

---

**Last Updated**: January 14, 2026
**Course**: Database Essentials
