import { Link } from 'react-router-dom';
import { Mic2, Activity, Upload, LayoutDashboard } from 'lucide-react';

export default function Header({ isConnected, stats }) {
  return (
    <header className="bg-white border-b border-gray-200 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="bg-primary-600 p-2 rounded-lg">
              <Mic2 className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-900">TranscribeAI</h1>
              <p className="text-xs text-gray-500">Audio Transcription & Segmentation</p>
            </div>
          </div>

          <nav className="hidden md:flex items-center gap-6">
            <Link to="/" className="flex items-center gap-2 text-gray-600 hover:text-primary-600 transition-colors">
              <LayoutDashboard className="w-4 h-4" />
              <span>Dashboard</span>
            </Link>
            <Link to="/upload" className="flex items-center gap-2 text-gray-600 hover:text-primary-600 transition-colors">
              <Upload className="w-4 h-4" />
              <span>Upload</span>
            </Link>
          </nav>

          <div className="flex items-center gap-4">
            {stats && (
              <div className="hidden lg:flex items-center gap-4 text-sm text-gray-500">
                <span className="flex items-center gap-1"><Activity className="w-4 h-4" /> {stats.processing || 0} Active</span>
                <span>{stats.completed || 0} Done</span>
              </div>
            )}
            <div className={`flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium ${isConnected ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
              <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
              {isConnected ? 'Live' : 'Offline'}
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
