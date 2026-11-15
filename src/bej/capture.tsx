import React, { useEffect, useRef, useState } from 'react';
import { api, RunAction } from './api';
import { RecordingClock, formatElapsed } from './recording-clock';

type Capture = { id: string; kind: string; createdAt: string; bytes: number };
type Transcript = { text: string; language: string; segments: { start: number; end: number; text: string }[] };

export function CapturePanel({ active, busy, run, notify, onRecording }: { active: boolean; busy: string; run: RunAction; notify: (message: string) => void; onRecording: (recording: boolean) => void }) {
  const [recording, setRecording] = useState(false);
  const [paused, setPaused] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const clock = useRef(new RecordingClock());
  const freezeClock = () => { clock.current.pause(performance.now()); setElapsed(clock.current.elapsed(performance.now())); };
  const [kind, setKind] = useState<'microphone' | 'screen'>('microphone');
  const [preview, setPreview] = useState<Blob | null>(null);
  const [previewUrl, setPreviewUrl] = useState('');
  const [captures, setCaptures] = useState<Capture[]>([]);
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [retained, setRetained] = useState<{blob:Blob;kind:string;id:string}|null>(null);
  const [retainedUrl, setRetainedUrl] = useState('');
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const chunks = useRef<Blob[]>([]);
  const timer = useRef<number | null>(null);
  const stop = () => {
    freezeClock();
    if (recorder.current && recorder.current.state !== 'inactive') recorder.current.stop();
    stream.current?.getTracks().forEach(track => track.stop());
    if (timer.current) window.clearTimeout(timer.current);
    setRecording(false); setPaused(false); onRecording(false);
  };
  const load = async () => { const result = await api<{ captures: Capture[] }>('captures'); setCaptures(result.captures); };
  useEffect(() => { if (active) load().catch(() => {}); }, [active]);
  useEffect(() => {
    if (!recording || paused) return;
    const interval = window.setInterval(() => setElapsed(clock.current.elapsed(performance.now())), 250);
    return () => window.clearInterval(interval);
  }, [recording, paused]);
  useEffect(() => {
    if (!preview) { setPreviewUrl(''); return; }
    const url = URL.createObjectURL(preview); setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [preview]);
  useEffect(() => {if(!retained){setRetainedUrl('');return;}const url=URL.createObjectURL(retained.blob);setRetainedUrl(url);return ()=>URL.revokeObjectURL(url);},[retained]);
  useEffect(() => () => { stream.current?.getTracks().forEach(track => track.stop()); if (timer.current) clearTimeout(timer.current); }, []);
  const start = (nextKind: 'microphone' | 'screen') => run('capture-start', async () => {
    if (recording) return;
    setPreview(null); setTranscript(null); chunks.current = [];
    const media = nextKind === 'microphone'
      ? await navigator.mediaDevices.getUserMedia({ audio: true })
      : await navigator.mediaDevices.getDisplayMedia({ video: true, audio: false });
    try {
      const mime = nextKind === 'microphone' ? 'audio/webm' : 'video/webm';
      if (!MediaRecorder.isTypeSupported(mime)) throw new Error('This browser cannot record WebM. Try current Chrome or Edge.');
      const next = new MediaRecorder(media, { mimeType: mime, ...(nextKind === 'screen' ? { videoBitsPerSecond: 700000 } : { audioBitsPerSecond: 64000 }) });
      let size = 0;
      next.ondataavailable = event => { if (event.data.size) { size += event.data.size; chunks.current.push(event.data); } if (size >= 45 * 1024 * 1024) stop(); };
      next.onstop = () => { freezeClock(); setPreview(new Blob(chunks.current, { type: mime })); media.getTracks().forEach(track => track.stop()); setRecording(false); setPaused(false); onRecording(false); if (timer.current) clearTimeout(timer.current); };
      media.getTracks().forEach(track => { track.onended = stop; });
      recorder.current = next; stream.current = media; setKind(nextKind); next.start(1000);
      clock.current.start(performance.now()); setElapsed(0);
      setRecording(true); setPaused(false); onRecording(true);
      timer.current = window.setTimeout(stop, 5 * 60 * 1000);
      notify('Recording started manually. It will stop after five minutes of session time (including pauses) or 45 MiB. The elapsed counter shows active recording time. Save only after reviewing.');
    } catch (error) { media.getTracks().forEach(track => track.stop()); throw error; }
  });
  const save = () => run('capture-save', async () => {
    if (!preview) return;
    const response = await fetch(`/api/captures/upload/${kind}`, { method: 'POST', headers: { Authorization: `Bearer ${sessionStorage.getItem('bej-session') || ''}`, 'Content-Type': preview.type }, body: preview });
    const result = await response.json(); if (!response.ok) throw new Error(result.detail || 'Capture could not be saved.');
    setPreview(null); await load(); notify('Recording saved only on this laptop. It remains until you delete it.');
  });
  return <section hidden={!active} className="capture-panel"><div className="panel"><h2>Capture only when you choose.</h2><p>Start each session manually. Ask meeting participants for consent where required. Microphone capture records your selected input; screen capture records the screen or window you choose, without audio.</p>
    <div className="plan-actions"><button className="button secondary" disabled={!!busy || recording || !!preview} onClick={() => start('microphone')}>Start microphone recording</button><button className="button secondary" disabled={!!busy || recording || !!preview} onClick={() => start('screen')}>Choose screen and record</button>{recording && <><button className="button secondary" onClick={() => { const current = recorder.current; if (!current) return; if (paused) { current.resume(); clock.current.resume(performance.now()); } else { current.pause(); freezeClock(); } setPaused(!paused); }}>{paused ? 'Resume capture' : 'Pause capture'}</button><button className="button primary recording-button" onClick={stop}>Stop recording</button></>}</div>
    {(recording || preview) && <div className="capture-elapsed"><span role="timer" aria-live="off" aria-label="Active recording elapsed time">{formatElapsed(elapsed)}</span><span>{recording ? paused ? 'Paused' : 'Recording' : 'Recorded'} · active capture time</span></div>}
    <p className="muted-note" role="status">{recording ? paused ? 'Capture is paused. The recording session is still open.' : 'Recording is active. Stop here or use the browser sharing control.' : 'Nothing is recording. No automatic capture is configured.'}</p>
    {previewUrl && <div className="capture-preview"><h3>Review before saving</h3>{kind === 'screen' ? <video src={previewUrl} controls /> : <audio src={previewUrl} controls />}<div className="plan-actions"><button className="button primary" disabled={!!busy} onClick={save}>Save recording locally</button><button className="button secondary" disabled={!!busy} onClick={() => setPreview(null)}>Discard unsaved recording</button></div></div>}
  </div><div className="panel"><div className="panel-heading"><div><h2>Local recordings</h2><p>Private storage. Retained until you explicitly delete them; never sent to Discord or Outlook.</p></div><button className="button secondary" disabled={!!busy} onClick={() => run('whisper-setup', async () => { await api('transcription/prepare', {}); notify('Local tiny speech model is ready. Future transcription works offline.'); })}>Prepare local speech model</button></div>
    {!captures.length ? <p className="inline-empty">No recordings saved yet.</p> : captures.map(capture => <article className="task-row" key={capture.id}><h3>{capture.kind === 'screen' ? 'Screen recording' : 'Microphone recording'}</h3><p>{new Date(capture.createdAt).toLocaleString('en', { timeZone: 'Asia/Manila' })} Manila · {(capture.bytes / 1024 / 1024).toFixed(1)} MiB</p><div className="plan-actions"><button className="button secondary" disabled={!!busy} onClick={()=>run('play-capture',async()=>{const response=await fetch(`/api/captures/${capture.id}/media`,{headers:{Authorization:`Bearer ${sessionStorage.getItem('bej-session') || ''}`}});if(!response.ok)throw new Error('The local recording could not be opened.');setRetained({blob:await response.blob(),kind:capture.kind,id:capture.id});})}>Play local recording</button>{capture.kind === 'microphone' && <button className="button secondary" disabled={!!busy} onClick={() => run('transcribe', async () => { setTranscript(await api<Transcript>(`captures/${capture.id}/transcribe`, {})); })}>Transcribe locally</button>}<button className="button secondary" disabled={!!busy} onClick={() => run('delete-capture', async () => { await api(`captures/${capture.id}/delete`, {}); setTranscript(null);if(retained?.id===capture.id)setRetained(null);await load(); notify('Deleted this local recording and its transcript.'); })}>Delete this recording</button></div></article>)}
    {retainedUrl && retained && <div className="capture-preview"><h3>Saved recording</h3>{retained.kind==='screen'?<video src={retainedUrl} controls/>:<audio src={retainedUrl} controls/>}<a className="text-button" href={retainedUrl} download={`${retained.id}.webm`}>Download local copy</a><button className="text-button" onClick={()=>setRetained(null)}>Close playback</button></div>}
    {transcript && <section className="ai-note"><h3>Local transcript · {transcript.language}</h3><p>{transcript.text}</p><details><summary>Show timestamped segments</summary>{transcript.segments.map((segment, index) => <p key={index}>{segment.start.toFixed(1)}s–{segment.end.toFixed(1)}s: {segment.text}</p>)}</details></section>}
  </div></section>;
}
