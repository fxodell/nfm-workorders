import { useState, useMemo, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Search, Plus, X, Package, AlertTriangle, QrCode, ArrowDownCircle,
  ArrowUpCircle, RefreshCw, ChevronRight, Loader2, Download,
  ArrowLeft, DollarSign, Hash, MapPin, Truck, Filter,
} from 'lucide-react';
import { format, parseISO } from 'date-fns';
import { partsApi } from '@/api/parts';
import type { Part, PartTransaction } from '@/types/api';
import { TransactionType } from '@/types/enums';
import { formatCurrency, formatNumber } from '@/utils/numberFormat';

type ViewMode = 'list' | 'detail';

const transactionTypeConfig: Record<TransactionType, { icon: React.ElementType; label: string; color: string }> = {
  [TransactionType.IN]: { icon: ArrowDownCircle, label: 'Stock In', color: 'text-green-600 bg-green-50' },
  [TransactionType.OUT]: { icon: ArrowUpCircle, label: 'Stock Out', color: 'text-red-600 bg-red-50' },
  [TransactionType.ADJUSTMENT]: { icon: RefreshCw, label: 'Adjustment', color: 'text-blue-600 bg-blue-50' },
};

export default function InventoryPage() {
  const queryClient = useQueryClient();
  const [viewMode, setViewMode] = useState<ViewMode>('list');
  const [selectedPartId, setSelectedPartId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [lowStockOnly, setLowStockOnly] = useState(false);
  const [showAddPartModal, setShowAddPartModal] = useState(false);
  const [showTransactionModal, setShowTransactionModal] = useState(false);

  // Data fetching
  const { data: parts = [], isLoading: partsLoading } = useQuery({
    queryKey: ['parts', lowStockOnly],
    queryFn: async () => {
      const res = await partsApi.list({ low_stock_only: lowStockOnly || undefined });
      return res.data;
    },
  });

  // Filtered parts
  const filteredParts = useMemo(() => {
    if (!searchQuery) return parts;
    const q = searchQuery.toLowerCase();
    return parts.filter(
      (p) =>
        p.part_number.toLowerCase().includes(q) ||
        p.description?.toLowerCase().includes(q) ||
        p.supplier_name?.toLowerCase().includes(q) ||
        p.storage_location?.toLowerCase().includes(q)
    );
  }, [parts, searchQuery]);

  // Total inventory value
  const totalInventoryValue = useMemo(() => {
    return parts.reduce((sum, p) => sum + (p.unit_cost || 0) * p.stock_quantity, 0);
  }, [parts]);

  const lowStockCount = useMemo(() => {
    return parts.filter((p) => p.stock_quantity <= p.reorder_threshold).length;
  }, [parts]);

  const selectedPart = useMemo(() => {
    return parts.find((p) => p.id === selectedPartId) || null;
  }, [parts, selectedPartId]);

  const handleSelectPart = useCallback((partId: string) => {
    setSelectedPartId(partId);
    setViewMode('detail');
  }, []);

  const handleBackToList = useCallback(() => {
    setViewMode('list');
    setSelectedPartId(null);
  }, []);

  const handleDownloadQr = useCallback(async (partId: string, partNumber: string) => {
    try {
      const res = await partsApi.getQrCode(partId);
      const blob = res.data as Blob;
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `qr-part-${partNumber}.png`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      // QR download failed silently
    }
  }, []);

  // ── List View ──────────────────────────────────────────────────────────────

  if (viewMode === 'list') {
    return (
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">Inventory</h1>
          <button
            onClick={() => setShowAddPartModal(true)}
            className="flex items-center gap-2 px-4 py-2.5 bg-navy-900 text-white rounded-lg font-medium min-h-[48px] active:bg-navy-800 transition-colors"
          >
            <Plus size={18} />
            Add Part
          </button>
        </div>

        {/* Summary cards */}
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="flex items-center gap-2 text-gray-500 text-xs mb-1">
              <Package size={14} />
              Total Parts
            </div>
            <div className="text-2xl font-bold text-gray-900">{formatNumber(parts.length)}</div>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="flex items-center gap-2 text-gray-500 text-xs mb-1">
              <DollarSign size={14} />
              Inventory Value
            </div>
            <div className="text-2xl font-bold text-gray-900">{formatCurrency(totalInventoryValue)}</div>
          </div>
          <div className={`rounded-lg border p-4 ${lowStockCount > 0 ? 'bg-red-50 border-red-200' : 'bg-white border-gray-200'}`}>
            <div className="flex items-center gap-2 text-gray-500 text-xs mb-1">
              <AlertTriangle size={14} className={lowStockCount > 0 ? 'text-red-500' : ''} />
              Low Stock
            </div>
            <div className={`text-2xl font-bold ${lowStockCount > 0 ? 'text-red-600' : 'text-gray-900'}`}>
              {lowStockCount}
            </div>
          </div>
        </div>

        {/* Search and filters */}
        <div className="flex flex-wrap gap-3">
          <div className="relative flex-1 min-w-[200px]">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Search parts..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-2.5 border border-gray-300 rounded-lg text-sm min-h-[48px] focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
            />
          </div>
          <button
            onClick={() => setLowStockOnly(!lowStockOnly)}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-lg font-medium text-sm min-h-[48px] transition-colors ${
              lowStockOnly
                ? 'bg-red-100 text-red-800 border border-red-300'
                : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
            }`}
          >
            <AlertTriangle size={14} />
            Low Stock
          </button>
        </div>

        {/* Parts list */}
        {partsLoading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 size={32} className="animate-spin text-navy-600" />
          </div>
        )}

        {!partsLoading && filteredParts.length === 0 && (
          <div className="text-center py-12">
            <Package size={48} className="mx-auto text-gray-300 mb-3" />
            <p className="text-gray-500">
              {searchQuery ? 'No parts match your search' : 'No parts in inventory'}
            </p>
          </div>
        )}

        <div className="space-y-2">
          {filteredParts.map((part) => {
            const isLowStock = part.stock_quantity <= part.reorder_threshold;
            const lineValue = (part.unit_cost || 0) * part.stock_quantity;

            return (
              <button
                key={part.id}
                onClick={() => handleSelectPart(part.id)}
                className={`w-full text-left bg-white rounded-lg border p-4 hover:shadow-md active:bg-gray-50 transition-all min-h-[48px] ${
                  isLowStock ? 'border-red-300' : 'border-gray-200'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-mono text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
                        {part.part_number}
                      </span>
                      {isLowStock && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-red-100 text-red-700 text-xs rounded-full font-semibold">
                          <AlertTriangle size={10} />
                          LOW
                        </span>
                      )}
                    </div>
                    <h3 className="font-semibold text-gray-900 truncate">
                      {part.description || part.part_number}
                    </h3>
                    <div className="flex flex-wrap items-center gap-3 mt-1.5 text-xs text-gray-500">
                      <span className="flex items-center gap-1">
                        <Hash size={11} />
                        Qty: <span className={`font-semibold ${isLowStock ? 'text-red-600' : 'text-gray-900'}`}>
                          {part.stock_quantity}
                        </span>
                        {' '}/ {part.reorder_threshold} min
                      </span>
                      {part.unit_cost != null && (
                        <span className="flex items-center gap-1">
                          <DollarSign size={11} />
                          {formatCurrency(part.unit_cost)} ea
                        </span>
                      )}
                      {part.storage_location && (
                        <span className="flex items-center gap-1">
                          <MapPin size={11} />
                          {part.storage_location}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <div className="text-right">
                      <div className="text-xs text-gray-400">Value</div>
                      <div className="text-sm font-semibold text-gray-900">
                        {formatCurrency(lineValue)}
                      </div>
                    </div>
                    <ChevronRight size={16} className="text-gray-400" />
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        {/* Add Part Modal */}
        {showAddPartModal && (
          <AddPartModal
            onClose={() => setShowAddPartModal(false)}
          />
        )}
      </div>
    );
  }

  // ── Detail View ────────────────────────────────────────────────────────────

  return (
    <div className="space-y-4">
      {selectedPart && (
        <PartDetailView
          part={selectedPart}
          onBack={handleBackToList}
          onDownloadQr={() => handleDownloadQr(selectedPart.id, selectedPart.part_number)}
          onCreateTransaction={() => setShowTransactionModal(true)}
        />
      )}

      {/* Transaction Modal */}
      {showTransactionModal && selectedPart && (
        <TransactionModal
          partId={selectedPart.id}
          onClose={() => setShowTransactionModal(false)}
        />
      )}
    </div>
  );
}

// ── Part Detail View ──────────────────────────────────────────────────────────

interface PartDetailViewProps {
  part: Part;
  onBack: () => void;
  onDownloadQr: () => void;
  onCreateTransaction: () => void;
}

function PartDetailView({ part, onBack, onDownloadQr, onCreateTransaction }: PartDetailViewProps) {
  const isLowStock = part.stock_quantity <= part.reorder_threshold;

  const { data: transactions = [], isLoading: txLoading } = useQuery({
    queryKey: ['part-transactions', part.id],
    queryFn: async () => {
      const res = await partsApi.getTransactions(part.id);
      return res.data;
    },
  });

  return (
    <>
      {/* Back header */}
      <div className="flex items-center gap-3">
        <button
          onClick={onBack}
          className="p-3 hover:bg-gray-100 rounded-lg min-h-[48px] min-w-[48px] flex items-center justify-center"
          aria-label="Back to list"
        >
          <ArrowLeft size={20} />
        </button>
        <div className="min-w-0 flex-1">
          <h1 className="text-xl font-bold text-gray-900 truncate">
            {part.description || part.part_number}
          </h1>
          <span className="font-mono text-xs text-gray-500">{part.part_number}</span>
        </div>
        <div className="flex gap-1">
          <button
            onClick={onDownloadQr}
            className="p-3 hover:bg-gray-100 rounded-lg min-h-[48px] min-w-[48px] flex items-center justify-center"
            aria-label="Download QR code"
          >
            <QrCode size={20} className="text-gray-600" />
          </button>
        </div>
      </div>

      {/* Part info card */}
      <div className={`bg-white rounded-lg border p-4 space-y-3 ${isLowStock ? 'border-red-300' : 'border-gray-200'}`}>
        {isLowStock && (
          <div className="flex items-center gap-2 px-3 py-2 bg-red-50 rounded-lg text-red-700 text-sm font-medium">
            <AlertTriangle size={16} />
            Stock below reorder threshold ({part.reorder_threshold})
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="text-xs text-gray-500">Stock Quantity</div>
            <div className={`text-2xl font-bold ${isLowStock ? 'text-red-600' : 'text-gray-900'}`}>
              {part.stock_quantity}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500">Reorder Threshold</div>
            <div className="text-2xl font-bold text-gray-900">{part.reorder_threshold}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500">Unit Cost</div>
            <div className="text-lg font-semibold text-gray-900">
              {part.unit_cost != null ? formatCurrency(part.unit_cost) : '--'}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500">Total Value</div>
            <div className="text-lg font-semibold text-gray-900">
              {formatCurrency((part.unit_cost || 0) * part.stock_quantity)}
            </div>
          </div>
        </div>

        {/* Additional details */}
        <div className="border-t border-gray-100 pt-3 space-y-2 text-sm">
          {part.supplier_name && (
            <div className="flex items-center gap-2 text-gray-600">
              <Truck size={14} className="text-gray-400 shrink-0" />
              <span>Supplier: {part.supplier_name}</span>
              {part.supplier_part_number && (
                <span className="text-gray-400">({part.supplier_part_number})</span>
              )}
            </div>
          )}
          {part.storage_location && (
            <div className="flex items-center gap-2 text-gray-600">
              <MapPin size={14} className="text-gray-400 shrink-0" />
              <span>Location: {part.storage_location}</span>
            </div>
          )}
          {part.barcode_value && (
            <div className="flex items-center gap-2 text-gray-600">
              <QrCode size={14} className="text-gray-400 shrink-0" />
              <span className="font-mono text-xs">{part.barcode_value}</span>
            </div>
          )}
        </div>

        {/* Action button */}
        <button
          onClick={onCreateTransaction}
          className="w-full mt-2 flex items-center justify-center gap-2 px-4 py-3 bg-navy-900 text-white rounded-lg font-medium min-h-[48px] active:bg-navy-800 transition-colors"
        >
          <RefreshCw size={16} />
          Adjust Stock
        </button>
      </div>

      {/* Transaction history */}
      <div className="bg-white rounded-lg border border-gray-200">
        <div className="px-4 py-3 border-b border-gray-200">
          <h2 className="font-semibold text-gray-900">Transaction History</h2>
        </div>

        {txLoading && (
          <div className="flex items-center justify-center py-8">
            <Loader2 size={24} className="animate-spin text-navy-600" />
          </div>
        )}

        {!txLoading && transactions.length === 0 && (
          <div className="text-center py-8 text-gray-500 text-sm">
            No transactions recorded
          </div>
        )}

        <div className="divide-y divide-gray-100">
          {transactions.map((tx) => {
            const config = transactionTypeConfig[tx.transaction_type];
            const Icon = config.icon;
            return (
              <div key={tx.id} className="px-4 py-3 flex items-center gap-3">
                <div className={`p-2 rounded-lg ${config.color}`}>
                  <Icon size={16} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-900">{config.label}</span>
                    <span className={`text-sm font-bold ${
                      tx.transaction_type === TransactionType.OUT ? 'text-red-600' : 'text-green-600'
                    }`}>
                      {tx.transaction_type === TransactionType.OUT ? '-' : '+'}{tx.quantity}
                    </span>
                  </div>
                  {tx.notes && (
                    <p className="text-xs text-gray-500 truncate">{tx.notes}</p>
                  )}
                </div>
                <div className="text-xs text-gray-400 shrink-0">
                  {format(parseISO(tx.created_at), 'MMM d, h:mm a')}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}

// ── Add Part Modal ───────────────────────────────────────────────────────────

function AddPartModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    part_number: '',
    description: '',
    unit_cost: '',
    stock_quantity: '',
    reorder_threshold: '',
    supplier_name: '',
    supplier_part_number: '',
    storage_location: '',
    barcode_value: '',
  });

  const updateField = (key: string, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const createMutation = useMutation({
    mutationFn: () =>
      partsApi.create({
        part_number: form.part_number,
        description: form.description || undefined,
        unit_cost: form.unit_cost ? parseFloat(form.unit_cost) : undefined,
        stock_quantity: parseInt(form.stock_quantity) || 0,
        reorder_threshold: parseInt(form.reorder_threshold) || 0,
        supplier_name: form.supplier_name || undefined,
        supplier_part_number: form.supplier_part_number || undefined,
        storage_location: form.storage_location || undefined,
        barcode_value: form.barcode_value || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['parts'] });
      onClose();
    },
  });

  return (
    <div className="fixed inset-0 bg-black/50 flex items-end md:items-center justify-center z-50">
      <div className="bg-white rounded-t-2xl md:rounded-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between z-10">
          <h2 className="text-lg font-semibold text-gray-900">Add Part</h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg min-h-[48px] min-w-[48px] flex items-center justify-center"
          >
            <X size={20} />
          </button>
        </div>

        <div className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Part Number <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={form.part_number}
              onChange={(e) => updateField('part_number', e.target.value)}
              placeholder="e.g. BRG-001"
              className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm min-h-[48px] focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
            <input
              type="text"
              value={form.description}
              onChange={(e) => updateField('description', e.target.value)}
              placeholder="Part description..."
              className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm min-h-[48px] focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Unit Cost ($)</label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={form.unit_cost}
                onChange={(e) => updateField('unit_cost', e.target.value)}
                placeholder="0.00"
                className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm min-h-[48px] focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Initial Stock <span className="text-red-500">*</span>
              </label>
              <input
                type="number"
                min="0"
                value={form.stock_quantity}
                onChange={(e) => updateField('stock_quantity', e.target.value)}
                placeholder="0"
                className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm min-h-[48px] focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Reorder Threshold</label>
            <input
              type="number"
              min="0"
              value={form.reorder_threshold}
              onChange={(e) => updateField('reorder_threshold', e.target.value)}
              placeholder="Minimum stock before reorder"
              className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm min-h-[48px] focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Supplier</label>
              <input
                type="text"
                value={form.supplier_name}
                onChange={(e) => updateField('supplier_name', e.target.value)}
                placeholder="Supplier name"
                className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm min-h-[48px] focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Supplier P/N</label>
              <input
                type="text"
                value={form.supplier_part_number}
                onChange={(e) => updateField('supplier_part_number', e.target.value)}
                placeholder="Supplier part #"
                className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm min-h-[48px] focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Storage Location</label>
            <input
              type="text"
              value={form.storage_location}
              onChange={(e) => updateField('storage_location', e.target.value)}
              placeholder="e.g. Warehouse B, Shelf 3"
              className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm min-h-[48px] focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Barcode Value</label>
            <input
              type="text"
              value={form.barcode_value}
              onChange={(e) => updateField('barcode_value', e.target.value)}
              placeholder="UPC or barcode"
              className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm min-h-[48px] focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
            />
          </div>
        </div>

        <div className="sticky bottom-0 bg-white border-t border-gray-200 px-6 py-4 flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg font-medium text-gray-700 min-h-[48px]"
          >
            Cancel
          </button>
          <button
            onClick={() => createMutation.mutate()}
            disabled={!form.part_number.trim() || createMutation.isPending}
            className="flex-1 px-4 py-2.5 bg-navy-900 text-white rounded-lg font-medium min-h-[48px] disabled:opacity-50"
          >
            {createMutation.isPending ? 'Adding...' : 'Add Part'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Transaction Modal ────────────────────────────────────────────────────────

function TransactionModal({ partId, onClose }: { partId: string; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [txType, setTxType] = useState<TransactionType>(TransactionType.IN);
  const [quantity, setQuantity] = useState('');
  const [notes, setNotes] = useState('');

  const createMutation = useMutation({
    mutationFn: () =>
      partsApi.createTransaction(partId, {
        transaction_type: txType,
        quantity: parseInt(quantity) || 0,
        notes: notes || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['parts'] });
      queryClient.invalidateQueries({ queryKey: ['part-transactions', partId] });
      onClose();
    },
  });

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl w-full max-w-md p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Stock Transaction</h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg min-h-[48px] min-w-[48px] flex items-center justify-center"
          >
            <X size={20} />
          </button>
        </div>

        {/* Transaction type selector */}
        <div className="grid grid-cols-3 gap-2">
          {Object.values(TransactionType).map((type) => {
            const config = transactionTypeConfig[type];
            const Icon = config.icon;
            return (
              <button
                key={type}
                onClick={() => setTxType(type)}
                className={`flex flex-col items-center gap-1 p-3 rounded-lg border-2 min-h-[48px] transition-colors ${
                  txType === type
                    ? 'border-navy-500 bg-navy-50'
                    : 'border-gray-200 hover:bg-gray-50'
                }`}
              >
                <Icon size={20} className={txType === type ? 'text-navy-700' : 'text-gray-400'} />
                <span className={`text-xs font-medium ${txType === type ? 'text-navy-700' : 'text-gray-500'}`}>
                  {config.label}
                </span>
              </button>
            );
          })}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Quantity <span className="text-red-500">*</span>
          </label>
          <input
            type="number"
            min="1"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            placeholder="Enter quantity"
            className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm min-h-[48px] focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
            autoFocus
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Notes</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            placeholder="Reason for transaction..."
            className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
          />
        </div>

        <div className="flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg font-medium text-gray-700 min-h-[48px]"
          >
            Cancel
          </button>
          <button
            onClick={() => createMutation.mutate()}
            disabled={!quantity || parseInt(quantity) <= 0 || createMutation.isPending}
            className="flex-1 px-4 py-2.5 bg-navy-900 text-white rounded-lg font-medium min-h-[48px] disabled:opacity-50"
          >
            {createMutation.isPending ? 'Saving...' : 'Submit'}
          </button>
        </div>
      </div>
    </div>
  );
}
