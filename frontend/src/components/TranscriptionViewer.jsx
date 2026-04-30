import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { transcriptionApi } from '../services/api';
import { Download, Copy, Search, FileText, Clock, Loader2 } from 'lucide-react';
import toast from 'react-hot-toast';

export default function TranscriptionViewer() {
  const { jobId } = useParams();
  const [search, setSearch] = useState('');
  const [viewMode, setViewMode] = useState('segments');

  const { data, isLoading } = useQuery({
    queryKey: ['transcription', jobId],
    queryFn: () => transcriptionApi.get(jobId).then((r) => r.data),
  });

  if (isLoading) return <div className="flex justify-center py-16"><Loader2 className="w-8 h-8 animate-spin text-primary-600" /></div>;
  if (!data) return <div className="card text-center py-16">No transcription found</div>;

  const segments = data.segments || [];
  const filteredSegments = search ? segments.filter((s) => s.text.toLowerCase().includes(search.toLowerCase())) : segments;

  const handleCopy = () => {
    navigator.clipboard.writeText(data.text || segments.map((s) => s.text).join(' '));
    toast.success('Copied to clipboard');
  };

  const handleDownload = (format) => {
    transcriptionApi.download(jobId, format).then((r) => {
      const blob = new Blob([r.data]);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `transcription.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    });
  };

  const fmtTime = (s) => {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, '0')}`;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h2 className="text-xl font-bold">Transcription Result</h2>
          <div className="flex items-center gap-4 text-sm text-gray-500 mt-1">
            {data.language && <span className="flex items-center gap-1"><FileText className="w-4 h-4" /> {data.language.toUpperCase()}</span>}
            {data.duration && <span className="flex items-center gap-1"><Clock className="w-4 h-4" /> {fmtTime(data.duration)}</span>}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={handleCopy} className="btn-secondary flex items-center gap-1 text-sm"><Copy className="w-4 h-4" /> Copy</button>
          <button onClick={() => handleDownload('srt')} className="btn-secondary flex items-center gap-1 text-sm"><Download className="w-4 h-4" /> SRT</button>
          <button onClick={() => handleDownload('vtt')} className="btn-secondary flex items-center gap-1 text-sm"><Download className="w-4 h-4" /> VTT</button>
          <button onClick={() => handleDownload('text')} className="btn-secondary flex items-center gap-1 text-sm"><Download className="w-4 h-4" /> TXT</button>
        </div>
      </div>

      <div className="relative">
        <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
        <input type="text" placeholder="Search in transcription..." value={search} onChange={(e) => setSearch(e.target.value)} className="input-primary pl-9" />
      </div>

      <div className="flex gap-2">
        <button onClick={() => setViewMode('full')} className={`px-3 py-1 rounded-lg text-sm ${viewMode === 'full' ? 'bg-primary-600 text-white' : 'bg-gray-100'}`}>Full Text</button>
        <button onClick={() => setViewMode('segments')} className={`px-3 py-1 rounded-lg text-sm ${viewMode === 'segments' ? 'bg-primary-600 text-white' : 'bg-gray-100'}`}>Segments</button>
      </div>

      <div className="card">
        {viewMode === 'full' ? (
          <div className="prose max-w-none whitespace-pre-wrap text-gray-700 leading-relaxed">{data.text}</div>
        ) : (
          <div className="space-y-3">
            {filteredSegments.map((seg, i) => (
              <div key={i} className="p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-mono text-primary-600">{fmtTime(seg.start)} - {fmtTime(seg.end)}</span>
                  {seg.words && <span className="text-xs text-gray-400">{seg.words.length} words</span>}
                </div>
                <p className="text-gray-700">{seg.text}</p>
              </div>
            ))}
            {filteredSegments.length === 0 && <p className="text-center text-gray-400 py-8">No matching segments</p>}
          </div>
        )}
      </div>
    </div>
  );
}
