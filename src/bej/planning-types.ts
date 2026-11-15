export type Priority = 'urgent' | 'high' | 'normal' | 'low';
export type Task = {
  id: string; title: string; source: string; line: number; heading: string;
  fingerprint: string; needsReview: boolean; dueDate?: string | null; dueWarning?: string;
  dueDateOrigin?: 'local' | 'source'; priority?: Priority; minutes?: number; category?: 'work' | 'personal';
};
export type Choice = { category: 'work' | 'personal'; minutes: number; priority: Priority; dueDate: string | null };
export type Block = Task & Choice & { start: string; end: string; reason?: string };
export type Plan = {
  calendarStale?: boolean; savedPath?: string; id: string; date: string; blocks: Block[];
  unscheduled: Block[]; scheduledMinutes: number; capacity: number;
  deadlineWarnings?: { taskId: string; dueDate: string; message: string }[];
};
export type Progress = { completed: number; total: number; tasks: Record<string, { status: 'open' | 'completed' | 'unavailable'; task?: Task }>; warnings: string[] };
