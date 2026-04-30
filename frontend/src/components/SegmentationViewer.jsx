import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { segmentationApi } from '../services/api';
import { Download, Filter, BarChart3, Loader2 } from 'lucide-react';

export default function SegmentationViewer() {
  const { jobId } = useParams();
  const [minDuration, setMinDuration] = useState('');
  const [maxDuration, setMaxDuration] = useState('');

  const { data, isLoading } = useQuery({
    queryKey: ['segmentation', jobId],
    queryFn: () => segmentationApi.get(jobId).then((r) => r.data),
  });

  const { data: stats } = useQuery({
    queryKey: ['segmentation-stats', jobId],
    queryFn: () => segmentationApi.statistics(jobId).then((r) => r.data),
  });

  if (isLoading) return <div className="flex justify-center py-16"><Loader2 className="w-8 h-8 animate-spin text-primary-600" /></div>;
  if (!data) return <div className="card text-center py-16">No segmentation found</div>;

  let segments = data.segments || [];
  if (minDuration) segments = segments.filter((s) => s.duration >= parseFloat(minDuration));
  if (maxDuration) segments = segments.filter((s) => s.duration <= parseFloat(maxDuration));

  const fmtTime = (s) => {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, '0')}`;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <h2 className="text-xl font-bold">Segmentation Result</h2>
        <div className="flex items-center gap-2">
          <button onClick={() => segmentationApi.export(jobId, 'csv').then((r) => { const blob = new Blob([r.data]); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = 'segments.csv'; a.click(); })} className="btn-secondary flex items-center gap-1 text-sm"><Download className="w-4 h-4" /> Export CSV</button>
        </div>
      </div>

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="card text-center"><p className="text-2xl font-bold">{stats.total_segments}</p><p className="text-xs text-gray-500">Segments</p></div>
          <div className="card text-center"><p className="text-2xl font-bold">{stats.average_segment_duration?.toFixed(1)}s</p><p className="text-xs text-gray-500">Avg Duration</p></div>
          <div className="card text-center"><p className="text-2xl font-bold">{fmtTime(stats.total_duration || 0)}</p><p className="text-xs text-gray-500">Total Duration</p></div>
          <div className="card text-center"><p className="text-sm font-medium capitalize">{stats.method_used || 'N/A'}</p><p className="text-xs text-gray-500">Method</p></div>
        </div>
      )}

      <div className="card">
        <div className="flex items-center gap-4 mb-4">
          <Filter className="w-4 h-4 text-gray-400" />
          <span className="text-sm font-medium">Filter</span>
          <input type="number" placeholder="Min duration (s)" value={minDuration} onChange={(e) => setMinDuration(e.target.value)} className="input-primary w-32 text-sm" />
          <input type="number" placeholder="Max duration (s)" value={maxDuration} onChange={(e) => setMaxDuration(e.target.value)} className="input-primary w-32 text-sm" />
        </div>

        <div className="space-y-3">
          {segments.map((seg) => (
            <div key={seg.segment_id} className="p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <span className="text-xs font-mono bg-primary-100 text-primary-700 px-2 py-0.5 rounded">#{seg.segment_id}</span>
                  <span className="text-xs font-mono text-gray-500">{fmtTime(seg.start)} - {fmtTime(seg.end)}</span>
                  <span className="text-xs text-gray-400">{seg.duration?.toFixed(1)}s</span>
                </div>
                <div className="flex items-center gap-2">
                  {seg.confidence && (
                    <div className="flex items-center gap-1">
                      <div className="w-16 bg-gray-200 rounded-full h-1.5">
                        <div className={`h-1.5 rounded-full ${seg.confidence > 0.8 ? 'bg-green-500' : seg.confidence > 0.6 ? 'bg-yellow-500' : 'bg-red-500'}`} style={{ width: `${seg.confidence * 100}%` }} />
                      </div>
                      <span className="text-xs text-gray-500">{(seg.confidence * 100).toFixed(0)}%</span>
                    </div>
                  )}
                  {seg.speaker_id && <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded">{seg.speaker_id}</span>}
                </div>
              </div>
              <p className="text-gray-700">{seg.text}</p>
            </div>
          ))}
          {segments.length === 0 && <p className="text-center text-gray-400 py-8">No segments match the filters</p>}
        </div>
      </div>
    </div>
  );
}
