import { useState } from 'react';
import { Plus, Trash2, Package } from 'lucide-react';
import type { WorkOrderPart } from '@/types/api';
import { formatCurrency } from '@/utils/numberFormat';

interface Props {
  parts: WorkOrderPart[];
  onAddPart: (part: {
    part_number: string;
    description: string;
    quantity: number;
    unit_cost: number;
  }) => void;
  onRemovePart: (partId: string) => void;
}

interface NewPartForm {
  part_number: string;
  description: string;
  quantity: string;
  unit_cost: string;
}

const emptyForm: NewPartForm = {
  part_number: '',
  description: '',
  quantity: '1',
  unit_cost: '0',
};

export default function PartsTable({ parts, onAddPart, onRemovePart }: Props) {
  const [showAddForm, setShowAddForm] = useState(false);
  const [form, setForm] = useState<NewPartForm>(emptyForm);

  const totalCost = parts.reduce((sum, p) => {
    const qty = p.quantity || 0;
    const cost = p.unit_cost || 0;
    return sum + qty * cost;
  }, 0);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.part_number.trim() && !form.description.trim()) return;

    onAddPart({
      part_number: form.part_number.trim(),
      description: form.description.trim(),
      quantity: parseInt(form.quantity, 10) || 1,
      unit_cost: parseFloat(form.unit_cost) || 0,
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
          Parts Used ({parts.length})
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
          Add Part
        </button>
      </div>

      {/* Add part form */}
      {showAddForm && (
        <form onSubmit={handleSubmit} className="bg-gray-50 rounded-lg border border-gray-200 p-4 mb-4 space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Part Number
              </label>
              <input
                type="text"
                value={form.part_number}
                onChange={(e) => setForm({ ...form, part_number: e.target.value })}
                placeholder="e.g., PN-12345"
                className="w-full px-3 py-2 min-h-[48px] border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Description
              </label>
              <input
                type="text"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="Part description"
                className="w-full px-3 py-2 min-h-[48px] border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Quantity
              </label>
              <input
                type="number"
                min="1"
                step="1"
                value={form.quantity}
                onChange={(e) => setForm({ ...form, quantity: e.target.value })}
                className="w-full px-3 py-2 min-h-[48px] border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Unit Cost ($)
              </label>
              <input
                type="number"
                min="0"
                step="0.01"
                value={form.unit_cost}
                onChange={(e) => setForm({ ...form, unit_cost: e.target.value })}
                className="w-full px-3 py-2 min-h-[48px] border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
              />
            </div>
          </div>
          <div className="flex items-center gap-2 pt-1">
            <button
              type="submit"
              className="px-4 py-2 min-h-[48px] bg-green-600 hover:bg-green-700 text-white rounded-lg text-sm font-medium transition-colors"
            >
              Add Part
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

      {/* Parts table */}
      {parts.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-left">
                <th className="py-2 pr-3 text-xs font-semibold text-gray-500 uppercase">Part</th>
                <th className="py-2 pr-3 text-xs font-semibold text-gray-500 uppercase">Description</th>
                <th className="py-2 pr-3 text-xs font-semibold text-gray-500 uppercase text-right">Qty</th>
                <th className="py-2 pr-3 text-xs font-semibold text-gray-500 uppercase text-right">Unit Cost</th>
                <th className="py-2 pr-3 text-xs font-semibold text-gray-500 uppercase text-right">Total</th>
                <th className="py-2 text-xs font-semibold text-gray-500 uppercase w-12"></th>
              </tr>
            </thead>
            <tbody>
              {parts.map((part) => {
                const lineTotal = (part.quantity || 0) * (part.unit_cost || 0);
                return (
                  <tr key={part.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-3 pr-3 font-mono text-gray-900">
                      {part.part_number || '--'}
                    </td>
                    <td className="py-3 pr-3 text-gray-700">
                      {part.description || '--'}
                    </td>
                    <td className="py-3 pr-3 text-right text-gray-900 font-medium">
                      {part.quantity}
                    </td>
                    <td className="py-3 pr-3 text-right text-gray-700">
                      {part.unit_cost != null ? formatCurrency(part.unit_cost) : '--'}
                    </td>
                    <td className="py-3 pr-3 text-right text-gray-900 font-medium">
                      {part.unit_cost != null ? formatCurrency(lineTotal) : '--'}
                    </td>
                    <td className="py-3 text-center">
                      <button
                        onClick={() => onRemovePart(part.id)}
                        className="min-h-[48px] min-w-[48px] inline-flex items-center justify-center p-2 text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                        aria-label={`Remove part ${part.part_number || part.description}`}
                      >
                        <Trash2 size={16} />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-gray-300">
                <td colSpan={4} className="py-3 pr-3 text-right font-semibold text-gray-700">
                  Total Cost
                </td>
                <td className="py-3 pr-3 text-right font-bold text-gray-900 text-base">
                  {formatCurrency(totalCost)}
                </td>
                <td></td>
              </tr>
            </tfoot>
          </table>
        </div>
      ) : (
        <div className="text-center py-12">
          <Package size={40} className="mx-auto text-gray-300 mb-3" />
          <p className="text-sm text-gray-500 mb-1">No parts recorded</p>
          <p className="text-xs text-gray-400">
            Tap "Add Part" to log parts used on this work order.
          </p>
        </div>
      )}
    </div>
  );
}
