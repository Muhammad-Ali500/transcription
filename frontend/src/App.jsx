import { useState } from 'react';
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';
import Header from './components/Header';
import JobDashboard from './components/JobDashboard';
import UploadZone from './components/UploadZone';
import MinioUploader from './components/MinioUploader';
import TranscriptionViewer from './components/TranscriptionViewer';
import SegmentationViewer from './components/SegmentationViewer';
import { useJobs } from './hooks/useJobs';

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, staleTime: 5000 } },
});

function DashboardPage() {
  const { isConnected } = useJobs();
  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Job Dashboard</h2>
        <div className="flex gap-3">
          <Link to="/upload" className="btn-primary">Upload New File</Link>
        </div>
      </div>
      <JobDashboard />
    </div>
  );
}

function UploadPage() {
  const [lastJob, setLastJob] = useState(null);
  return (
    <div className="space-y-8 max-w-3xl mx-auto">
      <h2 className="text-2xl font-bold">Upload Audio</h2>
      <UploadZone onUploadSuccess={setLastJob} />
      <MinioUploader onUploadSuccess={setLastJob} />
      {lastJob && (
        <div className="card bg-green-50 border-green-200">
          <p className="font-medium text-green-800">Job submitted!</p>
          <p className="text-sm text-green-600">ID: {lastJob.id}</p>
          <Link to="/" className="btn-primary mt-3 inline-block">View Dashboard</Link>
        </div>
      )}
    </div>
  );
}

function JobDetailPage() {
  return (
    <div className="space-y-6">
      <Link to="/" className="text-primary-600 hover:underline text-sm">&larr; Back to Dashboard</Link>
      <TranscriptionViewer />
      <SegmentationViewer />
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="min-h-screen bg-gray-50">
          <AppContent />
        </div>
        <Toaster position="top-right" />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

function AppContent() {
  const { isConnected } = useJobs();
  return (
    <>
      <Header isConnected={isConnected} />
      <main className="max-w-7xl mx-auto px-4 py-8">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/jobs/:jobId" element={<JobDetailPage />} />
        </Routes>
      </main>
    </>
  );
}
