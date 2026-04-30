import axios from 'axios';

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status >= 500) {
      const retries = error.config.__retryCount || 0;
      if (retries < 2) {
        error.config.__retryCount = retries + 1;
        await new Promise((r) => setTimeout(r, 1000 * (retries + 1)));
        return api(error.config);
      }
    }
    return Promise.reject(error);
  }
);

export const uploadApi = {
  uploadDirect: (formData) => api.post('/upload/direct', formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
  uploadMinio: (objectName, options = {}) => api.post('/upload/minio', { object_name: objectName, ...options }),
  uploadBatch: (objectNames, options = {}) => api.post('/upload/batch', { object_names: objectNames, ...options }),
  health: () => api.get('/upload/health'),
};

export const transcriptionApi = {
  create: (formData) => api.post('/transcription', formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
  get: (jobId) => api.get(`/transcription/${jobId}`),
  download: (jobId, format = 'text') => api.get(`/transcription/${jobId}/download?format=${format}`),
  segments: (jobId, page = 1, pageSize = 20) => api.get(`/transcription/${jobId}/segments?page=${page}&page_size=${pageSize}`),
  segment: (jobId, method = 'silence') => api.post(`/transcription/${jobId}/segment`, { method }),
};

export const segmentationApi = {
  create: (formData) => api.post('/segmentation', formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
  get: (jobId) => api.get(`/segmentation/${jobId}`),
  segments: (jobId, params = {}) => api.get(`/segmentation/${jobId}/segments`, { params }),
  resegment: (jobId, method, params = {}) => api.post(`/segmentation/${jobId}/resegment`, { method, params }),
  export: (jobId, format = 'json') => api.get(`/segmentation/${jobId}/export?format=${format}`),
  statistics: (jobId) => api.get(`/segmentation/${jobId}/statistics`),
};

export const jobsApi = {
  list: (params = {}) => api.get('/jobs', { params }),
  get: (jobId) => api.get(`/jobs/${jobId}`),
  status: (jobId) => api.get(`/jobs/${jobId}/status`),
  cancel: (jobId) => api.delete(`/jobs/${jobId}`),
  retry: (jobId) => api.post(`/jobs/${jobId}/retry`),
  stats: () => api.get('/jobs/stats'),
  recent: (limit = 10) => api.get(`/jobs/recent?limit=${limit}`),
};

export default api;
