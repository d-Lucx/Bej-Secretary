/** Monotonic active recording time; interval delays cannot make it drift. */
export class RecordingClock {
  private accumulated = 0;
  private startedAt: number | null = null;

  start(now: number) { this.accumulated = 0; this.startedAt = now; }
  resume(now: number) { if (this.startedAt === null) this.startedAt = now; }
  pause(now: number) { this.accumulated = this.elapsed(now); this.startedAt = null; }
  elapsed(now: number) { return this.accumulated + (this.startedAt === null ? 0 : Math.max(0, now - this.startedAt)); }
}

export function formatElapsed(milliseconds: number): string {
  const seconds = Math.floor(Math.max(0, milliseconds) / 1000);
  return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
}
