import { useState } from 'react';
import { Database, Loader2 } from 'lucide-react';
import { uploadApi } from '../services/api';
import toast from 'react-hot-toast';

export default function MinioUploader({ onUploadSuccess }) {
  const [objectName, setObjectName] = useState('');
  const [loading, setLoading] = useState(false);
  const [options, setOptions] = useState({ jobType: 'transcription', segmentation: false, method: 'silence' });

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!objectName.trim()) {
      toast.error('Please enter a MinIO object name');
      return;
    }
    setLoading(true);
    try {
      const response = await uploadApi.uploadMinio(objectName, {
        job_type: options.jobType,
        do_segmentation: options.segmentation,
        segmentation_method: options.method,
      });
      toast.success(`Submitted "${objectName}" for processing`);
      onUploadSuccess?.(response.data);
      setObjectName('');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to submit');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card">
      <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
        <Database className="w-5 h-5 text-primary-600" />
        Process from MinIO Storage
      </h2>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">MinIO Object Name</label>
          <input type="text" value={objectName} onChange={(e) => setObjectName(e.target.value)} placeholder="e.g., uploads/audio-file.mp3" className="input-primary" />
        </div>
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={options.segmentation} onChange={() => setOptions({ ...options, segmentation: !options.segmentation })} className="rounded text-primary-600" />
            <span className="text-sm">Include segmentation</span>
          </label>
        </div>
        <button type="submit" disabled={loading || !objectName.trim()} className="btn-primary flex items-center gap-2">
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Database className="w-4 h-4" />}
          {loading ? 'Submitting...' : 'Submit for Processing'}
        </button>
      </form>
    </div>
  );
}
