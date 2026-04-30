import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, FileAudio, Check, X, Loader2 } from 'lucide-react';
import { uploadApi } from '../services/api';
import toast from 'react-hot-toast';

const ALLOWED_EXTENSIONS = ['.mp3', '.wav', '.mp4', '.m4a', '.ogg', '.flac', '.aac'];
const MAX_SIZE = 100 * 1024 * 1024;

export default function UploadZone({ onUploadSuccess }) {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [options, setOptions] = useState({ jobType: 'transcription', segmentation: false, method: 'silence', language: '' });

  const onDrop = useCallback(async (acceptedFiles) => {
    const file = acceptedFiles[0];
    if (!file) return;

    const ext = '.' + file.name.split('.').pop().toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      toast.error(`File type ${ext} not supported`);
      return;
    }
    if (file.size > MAX_SIZE) {
      toast.error('File exceeds 100MB limit');
      return;
    }

    setUploading(true);
    setProgress(0);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('job_type', options.jobType);
      formData.append('do_segmentation', options.segmentation);
      formData.append('segmentation_method', options.method);
      if (options.language) formData.append('language', options.language);

      const response = await uploadApi.uploadDirect(formData);
      setProgress(100);
      toast.success(`"${file.name}" uploaded successfully`);
      onUploadSuccess?.(response.data);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
      setProgress(0);
    }
  }, [options, onUploadSuccess]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'audio/*': ALLOWED_EXTENSIONS },
    maxSize: MAX_SIZE,
    multiple: false,
    noClick: uploading,
  });

  return (
    <div className="card">
      <h2 className="text-lg font-semibold mb-4">Upload Audio File</h2>

      <div {...getRootProps()} className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors cursor-pointer ${isDragActive ? 'border-primary-500 bg-primary-50' : 'border-gray-300 hover:border-primary-400'} ${uploading ? 'pointer-events-none opacity-60' : ''}`}>
        <input {...getInputProps()} />
        {uploading ? (
          <div className="space-y-4">
            <Loader2 className="w-12 h-12 text-primary-600 animate-spin mx-auto" />
            <p className="text-gray-600">Uploading and processing...</p>
            <div className="w-full max-w-xs mx-auto bg-gray-200 rounded-full h-2">
              <div className="bg-primary-600 h-2 rounded-full transition-all duration-300" style={{ width: `${progress}%` }} />
            </div>
          </div>
        ) : isDragActive ? (
          <div className="space-y-2">
            <FileAudio className="w-12 h-12 text-primary-500 mx-auto" />
            <p className="text-primary-600 font-medium">Drop your audio file here</p>
          </div>
        ) : (
          <div className="space-y-2">
            <Upload className="w-12 h-12 text-gray-400 mx-auto" />
            <p className="text-gray-600">Drag & drop your audio file, or <span className="text-primary-600 font-medium">browse</span></p>
            <p className="text-xs text-gray-400">{ALLOWED_EXTENSIONS.join(', ')} - Max 100MB</p>
          </div>
        )}
      </div>

      <div className="mt-6 space-y-4">
        <div className="flex flex-wrap gap-4">
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="radio" name="jobType" value="transcription" checked={options.jobType === 'transcription'} onChange={() => setOptions({ ...options, jobType: 'transcription' })} className="text-primary-600" />
            <span className="text-sm">Transcription only</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={options.segmentation} onChange={() => setOptions({ ...options, segmentation: !options.segmentation })} className="rounded text-primary-600" />
            <span className="text-sm">Also segment</span>
          </label>
        </div>

        {options.segmentation && (
          <select value={options.method} onChange={(e) => setOptions({ ...options, method: e.target.value })} className="input-primary max-w-xs">
            <option value="silence">By Silence Gaps</option>
            <option value="sentence">By Sentences</option>
            <option value="time">By Time (30s chunks)</option>
            <option value="speaker">By Speaker (heuristic)</option>
          </select>
        )}
      </div>
    </div>
  );
}
