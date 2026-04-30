import { useState } from 'react';
import { useJobs } from '../hooks/useJobs';
import JobCard from './JobCard';
import { Activity, CheckCircle, Clock, AlertCircle, Loader2, Search } from 'lucide-react';

export default function JobDashboard() {
  const { jobs, isLoading, isConnected, refetch } = useJobs();
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');

  const stats = {
    total: jobs.length,
    pending: jobs.filter((j) => j.status === 'pending').length,
    processing: jobs.filter((j) => j.status === 'processing').length,
    completed: jobs.filter((j) => j.status === 'completed').length,
    failed: jobs.filter((j) => j.status === 'failed').length,
  };

  const filtered = jobs.filter((job) => {
    if (filter !== 'all' && job.status !== filter) return false;
    if (search && !job.filename.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="card flex items-center gap-3">
          <Clock className="w-8 h-8 text-gray-400" />
          <div><p className="text-2xl font-bold">{stats.pending}</p><p className="text-xs text-gray-500">Pending</p></div>
        </div>
        <div className="card flex items-center gap-3">
          <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
          <div><p className="text-2xl font-bold">{stats.processing}</p><p className="text-xs text-gray-500">Processing</p></div>
        </div>
        <div className="card flex items-center gap-3">
          <CheckCircle className="w-8 h-8 text-green-500" />
          <div><p className="text-2xl font-bold">{stats.completed}</p><p className="text-xs text-gray-500">Completed</p></div>
        </div>
        <div className="card flex items-center gap-3">
          <AlertCircle className="w-8 h-8 text-red-500" />
          <div><p className="text-2xl font-bold">{stats.failed}</p><p className="text-xs text-gray-500">Failed</p></div>
        </div>
      </div>

      <div className="flex items-center gap-4 flex-wrap">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input type="text" placeholder="Search by filename..." value={search} onChange={(e) => setSearch(e.target.value)} className="input-primary pl-9" />
        </div>
        <div className="flex gap-2">
          {['all', 'pending', 'processing', 'completed', 'failed'].map((f) => (
            <button key={f} onClick={() => setFilter(f)} className={`px-3 py-1 rounded-lg text-sm font-medium capitalize transition-colors ${filter === f ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
              {f}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-8 h-8 text-primary-600 animate-spin" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="card text-center py-16">
          <Activity className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-500">No jobs found</p>
          <p className="text-sm text-gray-400">Upload an audio file to get started</p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filtered.map((job) => (
            <JobCard key={job.id} job={job} onAction={refetch} />
          ))}
        </div>
      )}
    </div>
  );
}
