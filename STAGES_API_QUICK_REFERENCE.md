# Project Stages API - Quick Reference

## Base URL
```
/api/project-stages/
```

## Endpoints Summary

| Method | Endpoint | Action | Payload |
|--------|----------|--------|---------|
| **GET** | `/` | List all stages | - |
| **GET** | `/?project_id=:id` | List stages by project | - |
| **GET** | `/:id/` | Get specific stage | - |
| **POST** | `/` | Create new stage | `{project_id, title}` |
| **PUT** | `/:id/` | Full update stage | `{project_id, title, is_end_stage}` |
| **PATCH** | `/:id/` | Partial update | `{title}` or `{is_end_stage}` |
| **DELETE** | `/:id/` | Delete stage | - |

---

## Quick Examples

### Create Stage
```bash
curl -X POST http://localhost:8000/api/project-stages/ \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": 1,
    "title": "Review"
  }'
```

### Get Stages for Project
```bash
curl -X GET "http://localhost:8000/api/project-stages/?project_id=1"
```

### Update Stage Title
```bash
curl -X PATCH http://localhost:8000/api/project-stages/1/ \
  -H "Content-Type: application/json" \
  -d '{"title": "New Title"}'
```

### Delete Stage
```bash
curl -X DELETE http://localhost:8000/api/project-stages/1/
```

---

## Response Format

### Success (200/201)
```json
{
  "id": 1,
  "project_id": 1,
  "project": {"id": 1, "title": "Project Name"},
  "title": "Stage Name",
  "sequence": 1,
  "is_end_stage": false
}
```

### List Response
```json
{
  "count": 3,
  "data": [...]
}
```

### Error (400/404)
```json
{
  "error": "Message",
  "field": ["Validation error"]
}
```

---

## Field Reference

| Field | Type | Required | Read-Only | Notes |
|-------|------|----------|-----------|-------|
| `id` | Integer | - | ✓ | Auto-generated |
| `project_id` | Integer | ✓ (POST) | - | Project this stage belongs to |
| `project` | Object | - | ✓ | Project details |
| `title` | String | ✓ | - | Max 200 chars |
| `sequence` | Integer | - | ✓ | Auto-calculated order |
| `is_end_stage` | Boolean | - | - | Final stage flag |

---

## Status Codes

- `200` - Success (GET, PUT, PATCH)
- `201` - Created (POST)
- `204` - Deleted (DELETE)
- `400` - Bad Request (validation error)
- `404` - Not Found (ID doesn't exist)

---

## Created Using Django REST Framework

- **Serializer:** ProjectStageSerializer ([api_views.py](project/api_views.py#L39))
- **ViewSet:** ProjectStageViewSet ([api_views.py](project/api_views.py#L120))
- **Model:** ProjectStage ([models.py](project/models.py#L255))
- **Router:** DefaultRouter in [urls_api.py](project/urls_api.py)
