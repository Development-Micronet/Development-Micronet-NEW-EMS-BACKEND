# Project Stages API - Frontend Integration Examples

## JavaScript/Frontend Integration

### Using Fetch API

#### 1. Create Stage
```javascript
async function createStage(projectId, title) {
  try {
    const response = await fetch('/api/project-stages/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getToken()}`,  // if needed
      },
      body: JSON.stringify({
        project_id: projectId,
        title: title
      })
    });

    if (response.ok) {
      const stage = await response.json();
      console.log('Stage created:', stage);
      return stage;
    } else {
      const errors = await response.json();
      console.error('Error creating stage:', errors);
      throw new Error(errors.detail || 'Failed to create stage');
    }
  } catch (error) {
    console.error('Request failed:', error);
  }
}

// Usage
createStage(1, 'Code Review').then(stage => {
  console.log('Created stage with ID:', stage.id);
});
```

#### 2. Get All Stages for a Project
```javascript
async function getProjectStages(projectId) {
  try {
    const response = await fetch(`/api/project-stages/?project_id=${projectId}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${getToken()}`,
      }
    });

    if (response.ok) {
      const data = await response.json();
      console.log(`Found ${data.count} stages`);
      return data.data;
    }
  } catch (error) {
    console.error('Failed to fetch stages:', error);
  }
}

// Usage
getProjectStages(1).then(stages => {
  stages.forEach(stage => {
    console.log(`${stage.sequence}. ${stage.title}`);
  });
});
```

#### 3. Get Single Stage
```javascript
async function getStage(stageId) {
  try {
    const response = await fetch(`/api/project-stages/${stageId}/`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${getToken()}`,
      }
    });

    if (response.ok) {
      return await response.json();
    } else if (response.status === 404) {
      console.log('Stage not found');
      return null;
    }
  } catch (error) {
    console.error('Error:', error);
  }
}

// Usage
getStage(1).then(stage => {
  if (stage) {
    console.log(`Stage: ${stage.title} in Project: ${stage.project.title}`);
  }
});
```

#### 4. Update Stage (Partial)
```javascript
async function updateStageTitle(stageId, newTitle) {
  try {
    const response = await fetch(`/api/project-stages/${stageId}/`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getToken()}`,
      },
      body: JSON.stringify({
        title: newTitle
      })
    });

    if (response.ok) {
      return await response.json();
    }
  } catch (error) {
    console.error('Update failed:', error);
  }
}

// Usage
updateStageTitle(1, 'QA Testing').then(stage => {
  console.log('Updated to:', stage.title);
});
```

#### 5. Delete Stage
```javascript
async function deleteStage(stageId) {
  try {
    const response = await fetch(`/api/project-stages/${stageId}/`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${getToken()}`,
      }
    });

    if (response.status === 204) {
      console.log('Stage deleted successfully');
      return true;
    } else if (response.status === 404) {
      console.error('Stage not found');
      return false;
    }
  } catch (error) {
    console.error('Delete failed:', error);
  }
}

// Usage
deleteStage(1).then(success => {
  if (success) console.log('Deleted!');
});
```

---

### Using Axios

```javascript
import axios from 'axios';

const API_URL = '/api/project-stages';

// Setup axios instance with auth
const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Authorization': `Bearer ${getToken()}`
  }
});

// Create stage
async function createStage(projectId, title) {
  const response = await api.post('/', {
    project_id: projectId,
    title: title
  });
  return response.data;
}

// List stages
async function listStages(projectId = null) {
  const params = projectId ? { project_id: projectId } : {};
  const response = await api.get('/', { params });
  return response.data.data;
}

// Get stage
async function getStage(stageId) {
  const response = await api.get(`/${stageId}/`);
  return response.data;
}

// Update stage
async function updateStage(stageId, data) {
  const response = await api.patch(`/${stageId}/`, data);
  return response.data;
}

// Delete stage
async function deleteStage(stageId) {
  await api.delete(`/${stageId}/`);
  return true;
}

// Error handling
api.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 404) {
      console.error('Not found');
    } else if (error.response?.status === 400) {
      console.error('Validation error:', error.response.data);
    }
    return Promise.reject(error);
  }
);

export { createStage, listStages, getStage, updateStage, deleteStage };
```

---

### React Hook Example

```javascript
import { useState, useEffect } from 'react';

function useProjectStages(projectId) {
  const [stages, setStages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Fetch stages
  useEffect(() => {
    if (!projectId) return;

    const fetchStages = async () => {
      setLoading(true);
      try {
        const url = `/api/project-stages/?project_id=${projectId}`;
        const response = await fetch(url);
        if (response.ok) {
          const data = await response.json();
          setStages(data.data);
        } else {
          setError('Failed to fetch stages');
        }
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchStages();
  }, [projectId]);

  // Create stage
  const createStage = async (title) => {
    try {
      const response = await fetch('/api/project-stages/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_id: projectId, title })
      });
      if (response.ok) {
        const newStage = await response.json();
        setStages([...stages, newStage]);
        return newStage;
      }
    } catch (err) {
      setError(err.message);
    }
  };

  // Update stage
  const updateStage = async (stageId, title) => {
    try {
      const response = await fetch(`/api/project-stages/${stageId}/`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title })
      });
      if (response.ok) {
        const updated = await response.json();
        setStages(stages.map(s => s.id === stageId ? updated : s));
        return updated;
      }
    } catch (err) {
      setError(err.message);
    }
  };

  // Delete stage
  const deleteStage = async (stageId) => {
    try {
      const response = await fetch(`/api/project-stages/${stageId}/`, {
        method: 'DELETE'
      });
      if (response.status === 204) {
        setStages(stages.filter(s => s.id !== stageId));
        return true;
      }
    } catch (err) {
      setError(err.message);
    }
  };

  return { stages, loading, error, createStage, updateStage, deleteStage };
}

// Component usage
function ProjectStagesComponent({ projectId }) {
  const { stages, loading, error, createStage, updateStage, deleteStage }
    = useProjectStages(projectId);

  if (loading) return <p>Loading stages...</p>;
  if (error) return <p>Error: {error}</p>;

  return (
    <div className="stages">
      <h3>Project Stages</h3>
      {stages.map(stage => (
        <div key={stage.id} className="stage-card">
          <h4>{stage.title}</h4>
          <p>Sequence: {stage.sequence}</p>
          <button onClick={() => updateStage(stage.id, 'Updated')}>
            Edit
          </button>
          <button onClick={() => deleteStage(stage.id)}>
            Delete
          </button>
        </div>
      ))}
      <button onClick={() => createStage('New Stage')}>
        Add Stage
      </button>
    </div>
  );
}
```

---

### React Component with Form

```javascript
import React, { useState } from 'react';

function StageForm({ projectId, onStageCreated }) {
  const [title, setTitle] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!title.trim()) {
      setError('Title is required');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await fetch('/api/project-stages/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          project_id: projectId,
          title: title
        })
      });

      if (response.ok) {
        const stage = await response.json();
        setTitle('');
        onStageCreated(stage);
      } else {
        const data = await response.json();
        setError(data.title?.[0] || 'Failed to create stage');
      }
    } catch (err) {
      setError('Network error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <input
        type="text"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Enter stage name"
        disabled={loading}
      />
      <button type="submit" disabled={loading}>
        {loading ? 'Creating...' : 'Create Stage'}
      </button>
      {error && <p className="error">{error}</p>}
    </form>
  );
}

export default StageForm;
```

---

### Vue.js Example

```javascript
// stores/stages.js
import { defineStore } from 'pinia';

export const useStagesStore = defineStore('stages', {
  state: () => ({
    stages: [],
    loading: false,
    error: null,
  }),

  getters: {
    stagesByProject: (state) => (projectId) => {
      return state.stages.filter(s => s.project_id === projectId);
    }
  },

  actions: {
    async fetchStages(projectId) {
      this.loading = true;
      try {
        const response = await fetch(`/api/project-stages/?project_id=${projectId}`);
        const data = await response.json();
        this.stages = data.data;
      } catch (err) {
        this.error = err.message;
      } finally {
        this.loading = false;
      }
    },

    async createStage(projectId, title) {
      try {
        const response = await fetch('/api/project-stages/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ project_id: projectId, title })
        });
        const stage = await response.json();
        this.stages.push(stage);
        return stage;
      } catch (err) {
        this.error = err.message;
      }
    },

    async updateStage(stageId, updates) {
      try {
        const response = await fetch(`/api/project-stages/${stageId}/`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(updates)
        });
        const updated = await response.json();
        const index = this.stages.findIndex(s => s.id === stageId);
        if (index > -1) this.stages[index] = updated;
        return updated;
      } catch (err) {
        this.error = err.message;
      }
    },

    async deleteStage(stageId) {
      try {
        await fetch(`/api/project-stages/${stageId}/`, {
          method: 'DELETE'
        });
        this.stages = this.stages.filter(s => s.id !== stageId);
        return true;
      } catch (err) {
        this.error = err.message;
      }
    }
  }
});
```

```vue
<!-- StagesList.vue -->
<template>
  <div class="stages">
    <div v-if="loading" class="loading">Loading...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else class="stages-list">
      <div v-for="stage in stages" :key="stage.id" class="stage-item">
        <h4>{{ stage.title }}</h4>
        <span class="sequence">{{ stage.sequence }}</span>
        <button @click="deleteStage(stage.id)">Delete</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { useStagesStore } from '@/stores/stages';

const stagesStore = useStagesStore();

const stages = computed(() => stagesStore.stages);
const loading = computed(() => stagesStore.loading);
const error = computed(() => stagesStore.error);

const deleteStage = (stageId) => {
  stagesStore.deleteStage(stageId);
};
</script>
```

---

## API Response Caching Pattern

```javascript
const stageCache = new Map();

async function getCachedStages(projectId, cacheTime = 5 * 60 * 1000) {
  const now = Date.now();
  const cached = stageCache.get(projectId);

  if (cached && (now - cached.timestamp) < cacheTime) {
    return cached.data;
  }

  const url = `/api/project-stages/?project_id=${projectId}`;
  const response = await fetch(url);
  const data = await response.json();

  stageCache.set(projectId, {
    data: data.data,
    timestamp: now
  });

  return data.data;
}

// Clear cache
function clearStageCache(projectId) {
  stageCache.delete(projectId);
}
```

---

## Error Handling Pattern

```javascript
class StageAPIError extends Error {
  constructor(message, status, data) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

async function handleStageRequest(url, options = {}) {
  try {
    const response = await fetch(url, options);
    const data = await response.json();

    if (!response.ok) {
      throw new StageAPIError(
        `API Error: ${response.status}`,
        response.status,
        data
      );
    }

    return data;
  } catch (error) {
    if (error instanceof StageAPIError) {
      if (error.status === 400) {
        console.error('Validation failed:', error.data);
      } else if (error.status === 404) {
        console.error('Stage not found');
      } else if (error.status === 500) {
        console.error('Server error');
      }
    } else {
      console.error('Network error:', error);
    }
    throw error;
  }
}
```

---

## Summary

Use these patterns to:
- ✅ Create stages from your frontend
- ✅ Display stage lists with filtering
- ✅ Update stage information
- ✅ Delete stages
- ✅ Handle errors gracefully
- ✅ Cache API responses
- ✅ Integrate with React, Vue, or vanilla JS

Choose the pattern that best fits your frontend framework!
