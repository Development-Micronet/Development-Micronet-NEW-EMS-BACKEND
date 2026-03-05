# Project Stages API - Testing Guide

## Testing the Stages Endpoints

This guide helps you test all the created endpoints for Project Stages.

---

## Prerequisites

- Django development server running: `python manage.py runserver`
- Authentication token (if required by your permissions)
- Projects already created in the system

---

## Using Postman

### 1. Create a New Stage

**Request:**
```
POST /api/project-stages/
Content-Type: application/json
```

**Body:**
```json
{
  "project_id": 1,
  "title": "QA Testing"
}
```

**Expected Response:** `201 Created`
```json
{
  "id": 3,
  "project_id": 1,
  "project": {
    "id": 1,
    "title": "Website Redesign"
  },
  "title": "QA Testing",
  "sequence": 3,
  "is_end_stage": false
}
```

---

### 2. List All Stages

**Request:**
```
GET /api/project-stages/
```

**Expected Response:** `200 OK`
```json
{
  "count": 3,
  "data": [
    {
      "id": 1,
      "project_id": 1,
      "project": {"id": 1, "title": "Website Redesign"},
      "title": "Todo",
      "sequence": 1,
      "is_end_stage": false
    },
    {
      "id": 2,
      "project_id": 1,
      "project": {"id": 1, "title": "Website Redesign"},
      "title": "In Progress",
      "sequence": 2,
      "is_end_stage": false
    },
    {
      "id": 3,
      "project_id": 1,
      "project": {"id": 1, "title": "Website Redesign"},
      "title": "QA Testing",
      "sequence": 3,
      "is_end_stage": false
    }
  ]
}
```

---

### 3. List Stages for Specific Project

**Request:**
```
GET /api/project-stages/?project_id=1
```

**Expected Response:** `200 OK`
```json
{
  "count": 3,
  "data": [...]
}
```

---

### 4. Retrieve Specific Stage

**Request:**
```
GET /api/project-stages/3/
```

**Expected Response:** `200 OK`
```json
{
  "id": 3,
  "project_id": 1,
  "project": {
    "id": 1,
    "title": "Website Redesign"
  },
  "title": "QA Testing",
  "sequence": 3,
  "is_end_stage": false
}
```

---

### 5. Update Stage (Full Update)

**Request:**
```
PUT /api/project-stages/3/
Content-Type: application/json
```

**Body:**
```json
{
  "project_id": 1,
  "title": "Quality Assurance",
  "is_end_stage": false
}
```

**Expected Response:** `200 OK`
```json
{
  "id": 3,
  "project_id": 1,
  "project": {
    "id": 1,
    "title": "Website Redesign"
  },
  "title": "Quality Assurance",
  "sequence": 3,
  "is_end_stage": false
}
```

---

### 6. Partial Update Stage

**Request:**
```
PATCH /api/project-stages/3/
Content-Type: application/json
```

**Body (only update title):**
```json
{
  "title": "Deploy & Review"
}
```

**Expected Response:** `200 OK`
```json
{
  "id": 3,
  "project_id": 1,
  "project": {
    "id": 1,
    "title": "Website Redesign"
  },
  "title": "Deploy & Review",
  "sequence": 3,
  "is_end_stage": false
}
```

**Alternative - Mark as End Stage:**
```json
{
  "is_end_stage": true
}
```

---

### 7. Delete Stage

**Request:**
```
DELETE /api/project-stages/3/
```

**Expected Response:** `204 No Content`

(If you want to see the success message, the response will be:)
```json
{
  "message": "Stage deleted successfully"
}
```

---

## Using cURL

### Create Stage
```bash
curl -X POST http://localhost:8000/api/project-stages/ \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": 1,
    "title": "Testing Stage"
  }'
```

### List All Stages
```bash
curl -X GET http://localhost:8000/api/project-stages/
```

### Filter by Project
```bash
curl -X GET "http://localhost:8000/api/project-stages/?project_id=1"
```

### Get Single Stage
```bash
curl -X GET http://localhost:8000/api/project-stages/1/
```

### Update Stage (PATCH)
```bash
curl -X PATCH http://localhost:8000/api/project-stages/1/ \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Updated Title"
  }'
```

### Delete Stage
```bash
curl -X DELETE http://localhost:8000/api/project-stages/1/
```

---

## Using Python Requests

### Create Stage
```python
import requests

url = "http://localhost:8000/api/project-stages/"
payload = {
    "project_id": 1,
    "title": "API Testing"
}
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer YOUR_TOKEN"  # if needed
}

response = requests.post(url, json=payload, headers=headers)
print(response.json())
```

### List Stages
```python
import requests

url = "http://localhost:8000/api/project-stages/"
headers = {
    "Authorization": "Bearer YOUR_TOKEN"  # if needed
}

response = requests.get(url, headers=headers)
stages = response.json()
print(stages['count'], "stages found")
for stage in stages['data']:
    print(f"- {stage['title']} (sequence: {stage['sequence']})")
```

### Get by Project
```python
import requests

url = "http://localhost:8000/api/project-stages/?project_id=1"
response = requests.get(url)
print(response.json())
```

### Update Stage
```python
import requests

url = "http://localhost:8000/api/project-stages/1/"
payload = {"title": "New Name"}
headers = {"Content-Type": "application/json"}

response = requests.patch(url, json=payload, headers=headers)
print(response.json())
```

### Delete Stage
```python
import requests

url = "http://localhost:8000/api/project-stages/1/"
response = requests.delete(url)
print(response.status_code)  # Should be 204
```

---

## Testing Error Scenarios

### Missing Required Field
```bash
curl -X POST http://localhost:8000/api/project-stages/ \
  -H "Content-Type: application/json" \
  -d '{"title": "No Project"}'
```

**Response:** `400 Bad Request`
```json
{
  "project_id": ["Project ID is required for creating a stage."]
}
```

### Invalid Stage ID
```bash
curl -X GET http://localhost:8000/api/project-stages/9999/
```

**Response:** `404 Not Found`
```json
{
  "error": "Stage not found"
}
```

---

## Test Checklist

- [ ] Create stage with project_id and title
- [ ] List all stages
- [ ] Filter stages by project_id
- [ ] Get specific stage by ID
- [ ] Update stage (PUT) with all fields
- [ ] Partial update stage (PATCH) with single field
- [ ] Mark stage as end_stage
- [ ] Delete stage
- [ ] Verify error when missing required fields
- [ ] Verify 404 when stage doesn't exist
- [ ] Verify project includes stages when retrieved

---

## Database Verification

### Check Stages in Django Shell

```bash
python manage.py shell
```

```python
from project.models import ProjectStage, Project

# List all stages
stages = ProjectStage.objects.all()
for stage in stages:
    print(f"ID: {stage.id}, Title: {stage.title}, Project: {stage.project.title}, Seq: {stage.sequence}")

# Filter by project
project = Project.objects.get(id=1)
stages = project.project_stages.all()
for stage in stages:
    print(f"- {stage.title} (seq: {stage.sequence})")

# Get single stage
stage = ProjectStage.objects.get(id=1)
print(f"Stage: {stage.title}, Project: {stage.project.title}, Sequence: {stage.sequence}")
```

---

## Common Issues & Solutions

### Issue: "Project ID is required"
**Solution:** Make sure you're sending `project_id` in POST request, not `project`

### Issue: Sequence not incrementing
**Solution:** Sequence is auto-calculated. It's read-only in the API. Delete and recreate stages to reset sequences.

### Issue: Cannot delete stage
**Solution:** All tasks in that stage will be deleted too. Check if you have the right permissions.

### Issue: 404 Not Found on GET
**Solution:** Verify the stage ID exists with a list request first

---

## Performance Testing

### Load multiple stages
```python
import requests
import time

start = time.time()
for i in range(10):
    payload = {
        "project_id": 1,
        "title": f"Stage {i}"
    }
    requests.post("http://localhost:8000/api/project-stages/", json=payload)

end = time.time()
print(f"Created 10 stages in {end - start:.2f} seconds")
```

---

## Next Steps

1. **Test all endpoints** using the provided examples
2. **Verify database** entries using Django shell
3. **Test error scenarios** to ensure proper error handling
4. **Check task assignment** to stages
5. **Test project integration** - verify stages appear when getting project details
