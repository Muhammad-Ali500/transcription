import { useState, useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { jobsApi } from '../services/api';
import { useWebSocket } from './useWebSocket';

export function useJobs() {
  const queryClient = useQueryClient();
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${wsProtocol}//${window.location.host}/ws`;
  const { isConnected, messages } = useWebSocket(wsUrl);

  const { data: jobsData, isLoading, error, refetch } = useQuery({
    queryKey: ['jobs'],
    queryFn: () => jobsApi.recent(50).then((r) => r.data),
    refetchInterval: isConnected ? false : 10000,
  });

  useEffect(() => {
    for (const msg of messages) {
      if (msg.type === 'job_update' || msg.type === 'job_complete' || msg.type === 'job_error') {
        queryClient.invalidateQueries(['jobs']);
        queryClient.invalidateQueries(['job', msg.job_id]);
        queryClient.invalidateQueries(['jobs', 'stats']);
      }
    }
  }, [messages, queryClient]);

  return { jobs: jobsData || [], isLoading, error, refetch, isConnected };
}
