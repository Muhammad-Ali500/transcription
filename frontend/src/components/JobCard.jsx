import { useState } from 'react';
import { formatDistanceToNow } from 'date-fns';
import { FileAudio, ChevronDown, ChevronUp, Download, RotateCcw, Trash2, ExternalLink } from 'lucide-react';
import { Link } from 'react-router-dom';
import { jobsApi } from '../services/api';
import toast from 'react-hot-toast';

const statusColors = {
  pending: 'bg-gray-100 text-gray-700',
  processing: 'bg-blue-100 text-blue-700',
  completed: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
};

export default function JobCard({ job, onAction }) {
  const [expanded, setExpanded] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  const handleRetry = async () => {
    setActionLoading(true);
    try {
      await jobsApi.retry(job.id);
      toast.success('Job restarted');
      onAction?.();
    } catch (error) {
      toast.error('Retry failed');
    } finally {
      setActionLoading(false);
    }
  };

  const handleCancel = async () => {
    setActionLoading(true);
    try {
      await jobsApi.cancel(job.id);
      toast.success('Job cancelled');
      onAction?.();
    } catch (error) {
      toast.error('Cancel failed');
    } finally {
      setActionLoading(false);
    }
  };

  const formatSize = (bytes) => {
    if (!bytes) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    let i = 0;
    let size = bytes;
    while (size >= 1024 && i < units.length - 1) { size /= 1024; i++; }
    return `${size.toFixed(1)} ${units[i]}`;
  };

  return (
    <div className="card animate-slide-in">
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <div className={`p-2 rounded-lg ${job.job_type === 'transcription' ? 'bg-primary-100' : 'bg-purple-100'}`}>
            <FileAudio className={`w-5 h-5 ${job.job_type === 'transcription' ? 'text-primary-600' : 'text-purple-600'}`} />
          </div>
          <div className="min-w-0">
            <p className="font-medium text-gray-900 truncate">{job.filename}</p>
            <div className="flex items-center gap-3 mt-1">
              <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColors[job.status]}`}>
                {job.status}
              </span>
              <span className="text-xs text-gray-500 capitalize">{job.job_type}</span>
              <span className="text-xs text-gray-400">{formatSize(job.file_size)}</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2 ml-4">
          <span className="text-xs text-gray-400">{formatDistanceToNow(new Date(job.created_at), { addSuffix: true })}</span>
          <button onClick={() => setExpanded(!expanded)} className="p-1 hover:bg-gray-100 rounded" aria-label="Toggle details">
            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="mt-4 pt-4 border-t border-gray-100 space-y-3">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div><span className="text-gray-500">Job ID:</span><p className="font-mono text-xs truncate">{job.id}</p></div>
            <div><span className="text-gray-500">Created:</span><p className="text-xs">{new Date(job.created_at).toLocaleString()}</p></div>
            {job.error_message && <div className="col-span-2"><span className="text-red-500">Error:</span><p className="text-xs text-red-600">{job.error_message}</p></div>}
            {job.result && <div className="col-span-2"><span className="text-gray-500">Result:</span><pre className="text-xs bg-gray-50 p-2 rounded mt-1 overflow-auto max-h-32">{JSON.stringify(job.result, null, 2)}</pre></div>}
          </div>
          <div className="flex items-center gap-2 pt-2">
            {job.status === 'completed' && (
              <Link to={`/jobs/${job.id}`} className="btn-secondary flex items-center gap-1 text-sm">
                <ExternalLink className="w-3 h-3" /> View Results
              </Link>
            )}
            {job.status === 'failed' && (
              <button onClick={handleRetry} disabled={actionLoading} className="btn-secondary flex items-center gap-1 text-sm">
                <RotateCcw className="w-3 h-3" /> {actionLoading ? 'Retrying...' : 'Retry'}
              </button>
            )}
            {(job.status === 'pending' || job.status === 'processing') && (
              <button onClick={handleCancel} disabled={actionLoading} className="btn-secondary flex items-center gap-1 text-sm text-red-600 hover:text-red-700">
                <Trash2 className="w-3 h-3" /> {actionLoading ? 'Cancelling...' : 'Cancel'}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
