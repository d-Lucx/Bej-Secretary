import { describe, expect, it } from 'vitest';
import { RecordingClock, formatElapsed } from '../src/bej/recording-clock';

describe('recording elapsed time', () => {
  it('counts active capture time, freezes while paused, and resets for another recording', () => {
    const clock = new RecordingClock();
    clock.start(1000);
    expect(clock.elapsed(3500)).toBe(2500);
    clock.pause(3500);
    expect(clock.elapsed(12000)).toBe(2500);
    clock.resume(12000);
    expect(clock.elapsed(13500)).toBe(4000);
    clock.pause(13500);
    clock.pause(14000); // Stop/onstop must not count twice.
    expect(clock.elapsed(20000)).toBe(4000);
    clock.start(21000);
    expect(clock.elapsed(21000)).toBe(0);
  });

  it('formats minutes and seconds from timestamps instead of interval tick counts', () => {
    expect(formatElapsed(999)).toBe('00:00');
    expect(formatElapsed(61500)).toBe('01:01');
    expect(formatElapsed(300000)).toBe('05:00');
    const clock = new RecordingClock();
    clock.start(0);
    expect(formatElapsed(clock.elapsed(76000))).toBe('01:16');
  });
});
