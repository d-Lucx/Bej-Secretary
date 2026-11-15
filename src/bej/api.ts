export type BejStatus = {
  vaultPath: string; vaultName: string; vaultExists: boolean; today: string;
  ollama: { available: boolean; modelReady: boolean; model: string };
  discord: { destinationConfigured: boolean; tokenStored: boolean; deliveryVerified: boolean; enabled: boolean };
  outlook: { configured: boolean; clientId?: string; connected: boolean; accountEmail?: string | null; authPending: boolean; error?: string; calendarId?: string; lastSyncedAt?: string };
  desktop?: { startupEnabled: boolean };
};

const fragment = new URLSearchParams(location.hash.slice(1));
if (fragment.has('token')) {
  sessionStorage.setItem('bej-session', fragment.get('token') || '');
  history.replaceState(null, '', location.pathname + location.search);
}

export async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api/${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { Authorization: `Bearer ${sessionStorage.getItem('bej-session') || ''}`, ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Check your inputs and try again.');
  return result as T;
}

export type RunAction = (name: string, action: () => Promise<void>) => Promise<void>;
