import { useState, useMemo } from 'react';
import {
  ChevronLeft, ChevronRight, Calendar as CalendarIcon,
} from 'lucide-react';
import {
  startOfMonth, endOfMonth, startOfWeek, endOfWeek,
  eachDayOfInterval, format, isSameMonth, isSameDay, isToday,
  addMonths, subMonths,
} from 'date-fns';
import type { PMSchedule, PMTemplate } from '@/types/api';

interface Props {
  schedules: PMSchedule[];
  templates: PMTemplate[];
  onDateSelect?: (date: Date, schedulesOnDate: PMSchedule[]) => void;
}

type PMStatus = 'PENDING' | 'GENERATED' | 'SKIPPED' | 'OVERDUE';

const statusColors: Record<PMStatus, string> = {
  PENDING: 'bg-blue-500',
  GENERATED: 'bg-green-500',
  SKIPPED: 'bg-gray-400',
  OVERDUE: 'bg-red-500',
};

const statusLegend: { status: PMStatus; label: string; color: string }[] = [
  { status: 'PENDING', label: 'Pending', color: 'bg-blue-500' },
  { status: 'GENERATED', label: 'Generated', color: 'bg-green-500' },
  { status: 'SKIPPED', label: 'Skipped', color: 'bg-gray-400' },
  { status: 'OVERDUE', label: 'Overdue', color: 'bg-red-500' },
];

const WEEKDAY_LABELS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

export default function PMCalendar({ schedules, templates, onDateSelect }: Props) {
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const [selectedDate, setSelectedDate] = useState<Date | null>(null);

  const templateMap = useMemo(() => {
    const map = new Map<string, PMTemplate>();
    templates.forEach((t) => map.set(t.id, t));
    return map;
  }, [templates]);

  // Build a map from date string -> PMSchedule[]
  const schedulesByDate = useMemo(() => {
    const map = new Map<string, PMSchedule[]>();
    schedules.forEach((s) => {
      const dateKey = s.due_date.slice(0, 10); // YYYY-MM-DD
      const existing = map.get(dateKey) || [];
      existing.push(s);
      map.set(dateKey, existing);
    });
    return map;
  }, [schedules]);

  // Calendar grid days
  const calendarDays = useMemo(() => {
    const monthStart = startOfMonth(currentMonth);
    const monthEnd = endOfMonth(currentMonth);
    const calStart = startOfWeek(monthStart);
    const calEnd = endOfWeek(monthEnd);
    return eachDayOfInterval({ start: calStart, end: calEnd });
  }, [currentMonth]);

  const goToPrevMonth = () => setCurrentMonth(subMonths(currentMonth, 1));
  const goToNextMonth = () => setCurrentMonth(addMonths(currentMonth, 1));
  const goToToday = () => setCurrentMonth(new Date());

  const handleDateClick = (date: Date) => {
    setSelectedDate(date);
    const dateKey = format(date, 'yyyy-MM-dd');
    const schedulesOnDate = schedulesByDate.get(dateKey) || [];
    onDateSelect?.(date, schedulesOnDate);
  };

  // Get schedules for the selected date
  const selectedDateKey = selectedDate ? format(selectedDate, 'yyyy-MM-dd') : null;
  const selectedSchedules = selectedDateKey ? schedulesByDate.get(selectedDateKey) || [] : [];

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
      {/* Header: Month navigation */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-gray-50">
        <button
          onClick={goToPrevMonth}
          className="min-h-[48px] min-w-[48px] flex items-center justify-center p-2 hover:bg-gray-200 rounded-lg transition-colors"
          aria-label="Previous month"
        >
          <ChevronLeft size={20} />
        </button>

        <div className="flex items-center gap-3">
          <h2 className="text-lg font-bold text-gray-900">
            {format(currentMonth, 'MMMM yyyy')}
          </h2>
          <button
            onClick={goToToday}
            className="px-3 py-1 min-h-[36px] text-xs font-medium bg-white border border-gray-300 hover:bg-gray-100 rounded-md transition-colors"
          >
            Today
          </button>
        </div>

        <button
          onClick={goToNextMonth}
          className="min-h-[48px] min-w-[48px] flex items-center justify-center p-2 hover:bg-gray-200 rounded-lg transition-colors"
          aria-label="Next month"
        >
          <ChevronRight size={20} />
        </button>
      </div>

      {/* Weekday header row */}
      <div className="grid grid-cols-7 border-b border-gray-200">
        {WEEKDAY_LABELS.map((day) => (
          <div
            key={day}
            className="text-center text-xs font-semibold text-gray-500 uppercase py-2"
          >
            {day}
          </div>
        ))}
      </div>

      {/* Calendar grid */}
      <div className="grid grid-cols-7">
        {calendarDays.map((day) => {
          const dateKey = format(day, 'yyyy-MM-dd');
          const daySchedules = schedulesByDate.get(dateKey) || [];
          const inCurrentMonth = isSameMonth(day, currentMonth);
          const isSelected = selectedDate && isSameDay(day, selectedDate);
          const dayIsToday = isToday(day);

          return (
            <button
              key={dateKey}
              onClick={() => handleDateClick(day)}
              className={`
                relative min-h-[48px] p-1 border-b border-r border-gray-100
                text-center transition-colors
                ${inCurrentMonth ? 'bg-white' : 'bg-gray-50'}
                ${isSelected ? 'ring-2 ring-inset ring-navy-500' : ''}
                hover:bg-gray-100 active:bg-gray-200
              `}
              aria-label={`${format(day, 'MMMM d, yyyy')}${daySchedules.length > 0 ? `, ${daySchedules.length} PM schedules` : ''}`}
            >
              <span
                className={`
                  text-sm font-medium
                  ${!inCurrentMonth ? 'text-gray-400' : 'text-gray-900'}
                  ${dayIsToday ? 'bg-navy-900 text-white rounded-full w-7 h-7 inline-flex items-center justify-center' : ''}
                `}
              >
                {format(day, 'd')}
              </span>

              {/* Schedule dots */}
              {daySchedules.length > 0 && (
                <div className="flex items-center justify-center gap-0.5 mt-0.5 flex-wrap">
                  {daySchedules.slice(0, 4).map((schedule) => {
                    const scheduleStatus = getScheduleStatus(schedule);
                    return (
                      <span
                        key={schedule.id}
                        className={`w-2 h-2 rounded-full ${statusColors[scheduleStatus]}`}
                        title={`${templateMap.get(schedule.pm_template_id)?.title || 'PM'} - ${scheduleStatus}`}
                      />
                    );
                  })}
                  {daySchedules.length > 4 && (
                    <span className="text-xs text-gray-500 font-medium">
                      +{daySchedules.length - 4}
                    </span>
                  )}
                </div>
              )}
            </button>
          );
        })}
      </div>

      {/* Legend */}
      <div className="px-4 py-3 border-t border-gray-200 bg-gray-50 flex flex-wrap items-center gap-4">
        {statusLegend.map(({ status, label, color }) => (
          <div key={status} className="flex items-center gap-1.5">
            <span className={`w-3 h-3 rounded-full ${color}`} />
            <span className="text-xs text-gray-600">{label}</span>
          </div>
        ))}
      </div>

      {/* Selected date details */}
      {selectedDate && selectedSchedules.length > 0 && (
        <div className="border-t border-gray-200 p-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">
            {format(selectedDate, 'EEEE, MMMM d, yyyy')} - {selectedSchedules.length} PM Schedule{selectedSchedules.length !== 1 ? 's' : ''}
          </h3>
          <div className="space-y-2">
            {selectedSchedules.map((schedule) => {
              const template = templateMap.get(schedule.pm_template_id);
              const scheduleStatus = getScheduleStatus(schedule);
              return (
                <div
                  key={schedule.id}
                  className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg border border-gray-200"
                >
                  <span className={`w-3 h-3 rounded-full shrink-0 ${statusColors[scheduleStatus]}`} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">
                      {template?.title || 'PM Schedule'}
                    </p>
                    {template?.description && (
                      <p className="text-xs text-gray-500 truncate">{template.description}</p>
                    )}
                  </div>
                  <span
                    className={`
                      px-2 py-0.5 text-xs font-semibold rounded
                      ${scheduleStatus === 'PENDING' ? 'bg-blue-100 text-blue-700' : ''}
                      ${scheduleStatus === 'GENERATED' ? 'bg-green-100 text-green-700' : ''}
                      ${scheduleStatus === 'SKIPPED' ? 'bg-gray-100 text-gray-600' : ''}
                      ${scheduleStatus === 'OVERDUE' ? 'bg-red-100 text-red-700' : ''}
                    `}
                  >
                    {scheduleStatus}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function getScheduleStatus(schedule: PMSchedule): PMStatus {
  // Check if the schedule's own status matches known values
  const s = schedule.status.toUpperCase();
  if (s === 'GENERATED' || schedule.generated_work_order_id) return 'GENERATED';
  if (s === 'SKIPPED') return 'SKIPPED';
  if (s === 'OVERDUE') return 'OVERDUE';

  // If pending but past due_date, it's overdue
  if (s === 'PENDING') {
    const dueDate = new Date(schedule.due_date);
    const now = new Date();
    if (dueDate < now) return 'OVERDUE';
    return 'PENDING';
  }

  return 'PENDING';
}
