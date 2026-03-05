# Project Stages API Documentation

## Overview
Complete implementation of Project Stages endpoints with full CRUD operations (Create, Read, Update, Delete). Stages are used to organize and track task progression within a project.

---

## Models

### ProjectStage Model
Located in [project/models.py](project/models.py#L255)

**Fields:**
- `id` - Primary key (auto-generated)
- `title` - Stage name (max 200 chars) - **Required**
- `project` - Foreign key to Project - **Required**
- `sequence` - Auto-calculated order number (read-only)
- `is_end_stage` - Boolean to mark completion stage
- `created_at` - Timestamp (auto-generated)
- `updated_at` - Timestamp (auto-generated)
- `is_active` - Active status flag

### Task Model
Located in [project/models.py](project/models.py#L323)

**Key Field:**
- `stage` - Foreign key to ProjectStage (connects tasks to stages)

### Project Model
Located in [project/models.py](project/models.py#L49)

**Related Fields:**
- `project_stages` - Reverse relation to all stages in this project

---

## API Endpoints

### Base URL
```
/api/project-stages/
```

---

## GET Endpoints

### 1. List All Stages
**Endpoint:** `GET /api/project-stages/`

**Description:** Retrieve list of all stages, optionally filtered by project

**Query Parameters:**
- `project_id` (optional) - Filter stages by specific project

**Example Requests:**
```bash
# Get all stages
curl -X GET http://localhost:8000/api/project-stages/

# Get stages for specific project
curl -X GET http://localhost:8000/api/project-stages/?project_id=1
```

**Response:** `200 OK`
```json
{
  "count": 2,
  "data": [
    {
      "id": 1,
      "project_id": 1,
      "project": {
        "id": 1,
        "title": "Website Redesign"
      },
      "title": "Todo",
      "sequence": 1,
      "is_end_stage": false
    },
    {
      "id": 2,
      "project_id": 1,
      "project": {
        "id": 1,
        "title": "Website Redesign"
      },
      "title": "In Progress",
      "sequence": 2,
      "is_end_stage": false
    }
  ]
}
```

---

### 2. Retrieve Specific Stage
**Endpoint:** `GET /api/project-stages/{id}/`

**Description:** Get details of a specific stage by ID

**Path Parameters:**
- `id` (required) - Stage ID

**Example Request:**
```bash
curl -X GET http://localhost:8000/api/project-stages/1/
```

**Response:** `200 OK`
```json
{
  "id": 1,
  "project_id": 1,
  "project": {
    "id": 1,
    "title": "Website Redesign"
  },
  "title": "Todo",
  "sequence": 1,
  "is_end_stage": false
}
```

**Error Response:** `404 Not Found`
```json
{
  "error": "Stage not found"
}
```

---

## POST Endpoint

### 3. Create New Stage
**Endpoint:** `POST /api/project-stages/`

**Description:** Create a new project stage

**Required Fields:**
- `project_id` - ID of the parent project
- `title` - Name of the stage

**Optional Fields:**
- `is_end_stage` - Mark as final stage (boolean, default: false)

**Request Payload:**
```json
{
  "project_id": 1,
  "title": "Design Review"
}
```

**Example Request:**
```bash
curl -X POST http://localhost:8000/api/project-stages/ \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": 1,
    "title": "Design Review"
  }'
```

**Response:** `201 Created`
```json
{
  "id": 3,
  "project_id": 1,
  "project": {
    "id": 1,
    "title": "Website Redesign"
  },
  "title": "Design Review",
  "sequence": 3,
  "is_end_stage": false
}
```

**Error Response - Missing Fields:** `400 Bad Request`
```json
{
  "project_id": ["Project ID is required for creating a stage."],
  "title": ["Title is required for creating a stage."]
}
```

---

## PUT Endpoint

### 4. Update Stage (Full Update)
**Endpoint:** `PUT /api/project-stages/{id}/`

**Description:** Completely update a stage (all fields required)

**Path Parameters:**
- `id` (required) - Stage ID

**Request Payload:**
```json
{
  "project_id": 1,
  "title": "Code Review Updated",
  "is_end_stage": false
}
```

**Example Request:**
```bash
curl -X PUT http://localhost:8000/api/project-stages/2/ \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": 1,
    "title": "Code Review Updated",
    "is_end_stage": false
  }'
```

**Response:** `200 OK`
```json
{
  "id": 2,
  "project_id": 1,
  "project": {
    "id": 1,
    "title": "Website Redesign"
  },
  "title": "Code Review Updated",
  "sequence": 2,
  "is_end_stage": false
}
```

---

## PATCH Endpoint

### 5. Partial Update Stage
**Endpoint:** `PATCH /api/project-stages/{id}/`

**Description:** Partially update a stage (only specified fields required)

**Path Parameters:**
- `id` (required) - Stage ID

**Request Payload (only fields to update):**
```json
{
  "title": "Deployment"
}
```

**Example Request:**
```bash
curl -X PATCH http://localhost:8000/api/project-stages/2/ \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Deployment"
  }'
```

**Response:** `200 OK`
```json
{
  "id": 2,
  "project_id": 1,
  "project": {
    "id": 1,
    "title": "Website Redesign"
  },
  "title": "Deployment",
  "sequence": 2,
  "is_end_stage": false
}
```

---

## DELETE Endpoint

### 6. Delete Stage
**Endpoint:** `DELETE /api/project-stages/{id}/`

**Description:** Delete a stage (also deletes associated tasks)

**Path Parameters:**
- `id` (required) - Stage ID

**Example Request:**
```bash
curl -X DELETE http://localhost:8000/api/project-stages/3/
```

**Response:** `204 No Content`
```json
{
  "message": "Stage deleted successfully"
}
```

**Error Response - Not Found:** `404 Not Found`
```json
{
  "error": "Stage not found"
}
```

---

## Project Integration

### Project Response Now Includes Stages
When retrieving a project, it now includes all associated stages:

**Endpoint:** `GET /api/projects/{id}/`

**Response:** `200 OK`
```json
{
  "id": 1,
  "title": "Website Redesign",
  "managers": [1, 2],
  "members": [3, 4, 5],
  "status": "in_progress",
  "start_date": "2024-01-15",
  "end_date": "2024-06-30",
  "description": "Complete website redesign project",
  "stages": [
    {
      "id": 1,
      "project_id": 1,
      "project": {
        "id": 1,
        "title": "Website Redesign"
      },
      "title": "Todo",
      "sequence": 1,
      "is_end_stage": false
    },
    {
      "id": 2,
      "project_id": 1,
      "project": {
        "id": 1,
        "title": "Website Redesign"
      },
      "title": "In Progress",
      "sequence": 2,
      "is_end_stage": false
    }
  ]
}
```

---

## Task-Stage Connection

### Creating Tasks with Stages
Tasks can be assigned to stages during creation:

**Task Model Fields:**
- `project` - Foreign key to Project
- `stage` - Foreign key to ProjectStage
- `title`, `description`, `status`, etc.

**Example Task Creation Payload:**
```json
{
  "project": 1,
  "stage": 1,
  "title": "Design homepage mockup",
  "description": "Create mockup designs for homepage",
  "task_managers": [1, 2],
  "task_members": [3, 4],
  "status": "to_do",
  "start_date": "2024-01-20",
  "end_date": "2024-01-30"
}
```

---

## Implementation Details

### Serializers
Located in [project/api_views.py](project/api_views.py)

**ProjectStageSerializer:**
- Validates that POST requests include `project_id` and `title`
- Auto-calculates `sequence` number
- Returns read-only `project` details
- Supports both full (PUT) and partial (PATCH) updates

**ProjectSerializer:**
- Now includes nested `stages` field
- Returns all stages within a project response
- Maintains backward compatibility

### ViewSets
Located in [project/api_views.py](project/api_views.py#L120)

**ProjectStageViewSet:**
- Extends `ModelViewSet` for standard CRUD operations
- Custom actions for explicit endpoint routing
- Supports project filtering via query parameters
- Proper error handling with meaningful messages

### URL Routing
Located in [project/urls_api.py](project/urls_api.py)

```python
router.register(r"project-stages", ProjectStageViewSet, basename="project-stage")
```

---

## Error Handling

### Common HTTP Status Codes

| Code | Meaning | Example |
|------|---------|---------|
| 200 | Success (GET, PUT, PATCH) | Retrieve or update succeeded |
| 201 | Created (POST) | New stage created |
| 204 | No Content (DELETE) | Deletion successful |
| 400 | Bad Request | Missing required fields |
| 404 | Not Found | Stage ID doesn't exist |
| 403 | Forbidden | Permission denied |
| 500 | Server Error | Internal error |

### Validation Errors
```json
{
  "project_id": ["Project ID is required for creating a stage."],
  "title": ["Ensure this field has at most 200 characters."]
}
```

---

## Usage Examples

### JavaScript/Fetch Examples

**Get all stages:**
```javascript
fetch('/api/project-stages/', {
  method: 'GET',
  headers: {
    'Authorization': 'Bearer YOUR_TOKEN',
  }
})
.then(res => res.json())
.then(data => console.log(data));
```

**Create a stage:**
```javascript
fetch('/api/project-stages/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer YOUR_TOKEN',
  },
  body: JSON.stringify({
    project_id: 1,
    title: 'New Stage'
  })
})
.then(res => res.json())
.then(data => console.log(data));
```

**Update a stage:**
```javascript
fetch('/api/project-stages/1/', {
  method: 'PATCH',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer YOUR_TOKEN',
  },
  body: JSON.stringify({
    title: 'Updated Stage Title'
  })
})
.then(res => res.json())
.then(data => console.log(data));
```

**Delete a stage:**
```javascript
fetch('/api/project-stages/1/', {
  method: 'DELETE',
  headers: {
    'Authorization': 'Bearer YOUR_TOKEN',
  }
})
.then(res => res.json())
.then(data => console.log(data));
```

---

## Summary of Changes

✅ **Created ProjectStageSerializer** with:
- Project ID and title validation for POST requests
- Read-only sequence calculation
- Support for full and partial updates

✅ **Enhanced ProjectStageViewSet** with:
- GET list with project filtering
- GET retrieve for single stage
- POST create with validation
- PUT/PATCH update with error handling
- DELETE with proper responses

✅ **Updated ProjectSerializer** to:
- Include nested stages in project responses
- Maintain all project details
- Show stage information when retrieving projects

✅ **Task Model Integration:**
- Already supports stage relationships
- Tasks can be assigned to stages
- Stages define task workflow

---

## Database Sequence Management

The system automatically manages stage sequences:
- New stages get the next sequence number
- Deleting a stage reorders subsequent stages
- Sequence is read-only in API (auto-calculated)
