import { useEffect, useState } from 'react';
import { api } from './api';
import { Progress } from './planning-types';

export function usePlanProgress(planId?: string) {
  const [progress, setProgress] = useState<Progress | null>(null);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true;
    setProgress(null); setError('');
    if (!planId) return;
    const load = async () => {
      try {
        const result = await api<Progress>(`plans/${planId}/progress`);
        if (active) { setProgress(result); setError(''); }
      } catch { if (active) { setProgress(null); setError('Source progress could not be refreshed. Check vault access before completing a task.'); } }
    };
    load();
    const timer = window.setInterval(() => { if (document.visibilityState === 'visible') load(); }, 15000);
    return () => { active = false; window.clearInterval(timer); };
  }, [planId, revision]);
  return { progress, progressError: error, refreshProgress: () => setRevision(value => value + 1) };
}
