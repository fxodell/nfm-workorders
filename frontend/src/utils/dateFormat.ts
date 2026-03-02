import { formatDistanceToNow, format, differenceInMinutes, differenceInHours, isPast } from 'date-fns';

export function timeAgo(dateStr: string): string {
  return formatDistanceToNow(new Date(dateStr), { addSuffix: true });
}

export function formatDateTime(dateStr: string): string {
  return format(new Date(dateStr), 'MMM d, yyyy h:mm a');
}

export function formatDate(dateStr: string): string {
  return format(new Date(dateStr), 'MMM d, yyyy');
}

export function formatTime(dateStr: string): string {
  return format(new Date(dateStr), 'h:mm a');
}

export interface CountdownResult {
  text: string;
  color: 'green' | 'yellow' | 'red';
  isPast: boolean;
  pulsing: boolean;
}

export function getCountdown(deadlineStr: string): CountdownResult {
  const deadline = new Date(deadlineStr);
  const now = new Date();

  if (isPast(deadline)) {
    const minutesAgo = differenceInMinutes(now, deadline);
    const hoursAgo = differenceInHours(now, deadline);
    return {
      text: hoursAgo > 0 ? `${hoursAgo}h overdue` : `${minutesAgo}m overdue`,
      color: 'red',
      isPast: true,
      pulsing: true,
    };
  }

  const minutesLeft = differenceInMinutes(deadline, now);
  const hoursLeft = differenceInHours(deadline, now);

  if (minutesLeft < 15) {
    return { text: `${minutesLeft}m`, color: 'red', isPast: false, pulsing: true };
  }
  if (minutesLeft < 60) {
    return { text: `${minutesLeft}m`, color: 'yellow', isPast: false, pulsing: false };
  }
  if (hoursLeft < 24) {
    const mins = minutesLeft % 60;
    return { text: `${hoursLeft}h ${mins}m`, color: hoursLeft < 2 ? 'yellow' : 'green', isPast: false, pulsing: false };
  }

  const days = Math.floor(hoursLeft / 24);
  return { text: `${days}d ${hoursLeft % 24}h`, color: 'green', isPast: false, pulsing: false };
}

export function getETACountdown(etaMinutes: number, acceptedAt: string): CountdownResult {
  const accepted = new Date(acceptedAt);
  const deadline = new Date(accepted.getTime() + etaMinutes * 60 * 1000);
  return getCountdown(deadline.toISOString());
}
