import { useState } from 'react';
import { Plus, Trash2, Timer } from 'lucide-react';
import type { LaborLog } from '@/types/api';
import { formatMinutesAsHours } from '@/utils/numberFormat';
import { formatDate, formatDateTime } from '@/utils/dateFormat';

interface Props {
  laborLogs: LaborLog[];
  currentUserId: string;
  onAddLabor: (entry: { minutes: number; notes: string }) => void;
  onDeleteLabor: (laborId: string) => void;
}

interface NewLaborForm {
  hours: string;
  minutes: string;
  notes: string;
}

const emptyForm: NewLaborForm = {
  hours: '0',
  minutes: '0',
  notes: '',
};

export default function LaborTable({ laborLogs, currentUserId, onAddLabor, onDeleteLabor }: Props) {
  const [showAddForm, setShowAddForm] = useState(false);
  const [form, setForm] = useState<NewLaborForm>(emptyForm);

  const totalMinutes = laborLogs.reduce((sum, log) => sum + log.minutes, 0);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const totalMins = (parseInt(form.hours, 10) || 0) * 60 + (parseInt(form.minutes, 10) || 0);
    if (totalMins <= 0) return;

    onAddLabor({
      minutes: totalMins,
      notes: form.notes.trim(),
    });

    setForm(emptyForm);
    setShowAddForm(false);
  };

  const handleCancel = () => {
    setForm(emptyForm);
    setShowAddForm(false);
  };

  return (
    <div className="p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-700">
          Labor Logs ({laborLogs.length})
        </h3>
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="
            inline-flex items-center gap-1.5 px-3 py-2 min-h-[48px]
            bg-navy-900 hover:bg-navy-800 text-white rounded-lg
            text-sm font-medium transition-colors
          "
        >
          <Plus size={16} />
          Add Labor
        </button>
      </div>

      {/* Add labor form */}
      {showAddForm && (
        <form onSubmit={handleSubmit} className="bg-gray-50 rounded-lg border border-gray-200 p-4 mb-4 space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Hours
              </label>
              <input
                type="number"
                min="0"
                step="1"
                value={form.hours}
                onChange={(e) => setForm({ ...form, hours: e.target.value })}
                className="w-full px-3 py-2 min-h-[48px] border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Minutes
              </label>
              <input
                type="number"
                min="0"
                max="59"
                step="1"
                value={form.minutes}
                onChange={(e) => setForm({ ...form, minutes: e.target.value })}
                className="w-full px-3 py-2 min-h-[48px] border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
              />
            </div>
            <div className="sm:col-span-1">
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Description
              </label>
              <input
                type="text"
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
                placeholder="Work performed"
                className="w-full px-3 py-2 min-h-[48px] border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
              />
            </div>
          </div>
          <div className="flex items-center gap-2 pt-1">
            <button
              type="submit"
              className="px-4 py-2 min-h-[48px] bg-green-600 hover:bg-green-700 text-white rounded-lg text-sm font-medium transition-colors"
            >
              Log Time
            </button>
            <button
              type="button"
              onClick={handleCancel}
              className="px-4 py-2 min-h-[48px] bg-gray-200 hover:bg-gray-300 text-gray-700 rounded-lg text-sm font-medium transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {/* Labor table */}
      {laborLogs.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-left">
                <th className="py-2 pr-3 text-xs font-semibold text-gray-500 uppercase">Technician</th>
                <th className="py-2 pr-3 text-xs font-semibold text-gray-500 uppercase">Description</th>
                <th className="py-2 pr-3 text-xs font-semibold text-gray-500 uppercase text-right">Time</th>
                <th className="py-2 pr-3 text-xs font-semibold text-gray-500 uppercase">Date</th>
                <th className="py-2 text-xs font-semibold text-gray-500 uppercase w-12"></th>
              </tr>
            </thead>
            <tbody>
              {laborLogs.map((log) => {
                const isOwnEntry = log.user_id === currentUserId;
                const hours = Math.floor(log.minutes / 60);
                const mins = log.minutes % 60;
                const timeDisplay = `${hours}:${mins.toString().padStart(2, '0')}`;

                return (
                  <tr key={log.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-3 pr-3 text-gray-900 font-medium">
                      {log.user_name || 'Unknown'}
                    </td>
                    <td className="py-3 pr-3 text-gray-700">
                      {log.notes || '--'}
                    </td>
                    <td className="py-3 pr-3 text-right text-gray-900 font-mono font-medium">
                      {timeDisplay}
                    </td>
                    <td className="py-3 pr-3 text-gray-600">
                      {formatDate(log.logged_at)}
                    </td>
                    <td className="py-3 text-center">
                      {isOwnEntry ? (
                        <button
                          onClick={() => onDeleteLabor(log.id)}
                          className="min-h-[48px] min-w-[48px] inline-flex items-center justify-center p-2 text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                          aria-label={`Delete labor entry from ${formatDate(log.logged_at)}`}
                        >
                          <Trash2 size={16} />
                        </button>
                      ) : (
                        <span className="min-h-[48px] min-w-[48px] inline-flex items-center justify-center p-2">
                          {/* No action for other users' entries */}
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-gray-300">
                <td colSpan={2} className="py-3 pr-3 text-right font-semibold text-gray-700">
                  Total Time
                </td>
                <td className="py-3 pr-3 text-right font-bold text-gray-900 text-base font-mono">
                  {Math.floor(totalMinutes / 60)}:{(totalMinutes % 60).toString().padStart(2, '0')}
                </td>
                <td colSpan={2} className="py-3 pr-3 text-gray-500 text-xs">
                  ({formatMinutesAsHours(totalMinutes)})
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      ) : (
        <div className="text-center py-12">
          <Timer size={40} className="mx-auto text-gray-300 mb-3" />
          <p className="text-sm text-gray-500 mb-1">No labor logged</p>
          <p className="text-xs text-gray-400">
            Tap "Add Labor" to record time spent on this work order.
          </p>
        </div>
      )}
    </div>
  );
}
