import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft, Loader2, AlertTriangle, Camera, X, ChevronDown,
  Search, Check, Plus, ImageIcon,
} from 'lucide-react';
import { workOrderApi } from '@/api/workOrders';
import { sitesApi } from '@/api/sites';
import { assetsApi } from '@/api/assets';
import { useAuthStore } from '@/stores/authStore';
import { useIdempotencyKey } from '@/hooks/useIdempotencyKey';
import { useOfflineQueue } from '@/hooks/useOfflineQueue';
import { isOnline } from '@/utils/offlineDetect';
import { WorkOrderPriority, WorkOrderType } from '@/types/enums';
import { getPriorityConfig } from '@/utils/priority';
import type { Site, Asset, WorkOrder, User } from '@/types/api';
import apiClient from '@/api/client';

interface FormData {
  title: string;
  description: string;
  priority: WorkOrderPriority;
  type: WorkOrderType;
  safety_flag: boolean;
  safety_notes: string;
  site_id: string;
  asset_id: string;
  assigned_to: string;
  custom_fields: Record<string, string>;
}

interface FormErrors {
  title?: string;
  description?: string;
  site_id?: string;
  form?: string;
}

const initialForm: FormData = {
  title: '',
  description: '',
  priority: WorkOrderPriority.SCHEDULED,
  type: WorkOrderType.REACTIVE,
  safety_flag: false,
  safety_notes: '',
  site_id: '',
  asset_id: '',
  assigned_to: '',
  custom_fields: {},
};

// ------- Sub-components -------

function SearchableSelect<T extends { id: string }>({
  label,
  placeholder,
  items,
  selectedId,
  onSelect,
  renderItem,
  getLabel,
  disabled,
  error,
  isLoading,
}: {
  label: string;
  placeholder: string;
  items: T[];
  selectedId: string;
  onSelect: (id: string) => void;
  renderItem: (item: T) => React.ReactNode;
  getLabel: (item: T) => string;
  disabled?: boolean;
  error?: string;
  isLoading?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const dropdownRef = useRef<HTMLDivElement>(null);

  const selectedItem = items.find((item) => item.id === selectedId);
  const filtered = items.filter((item) =>
    getLabel(item).toLowerCase().includes(search.toLowerCase())
  );

  // Close on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [open]);

  return (
    <div className="relative" ref={dropdownRef}>
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      <button
        type="button"
        onClick={() => !disabled && setOpen(!open)}
        disabled={disabled}
        className={`w-full h-12 px-4 bg-white border rounded-lg text-left flex items-center justify-between transition-colors ${
          error
            ? 'border-red-300 bg-red-50'
            : open
              ? 'border-navy-500 ring-2 ring-navy-500'
              : 'border-gray-300 hover:border-gray-400'
        } ${disabled ? 'bg-gray-100 cursor-not-allowed text-gray-400' : 'text-gray-900'}`}
      >
        <span className={selectedItem ? 'text-gray-900' : 'text-gray-400'}>
          {isLoading ? 'Loading...' : selectedItem ? getLabel(selectedItem) : placeholder}
        </span>
        <ChevronDown size={16} className="text-gray-400 shrink-0" />
      </button>
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}

      {open && (
        <div className="absolute left-0 right-0 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-30 max-h-64 overflow-hidden flex flex-col">
          {/* Search within dropdown */}
          <div className="p-2 border-b border-gray-100">
            <div className="relative">
              <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search..."
                className="w-full h-10 pl-8 pr-3 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-1 focus:ring-navy-500"
                autoFocus
              />
            </div>
          </div>

          {/* Options */}
          <div className="overflow-y-auto flex-1">
            {/* Clear selection option */}
            {selectedId && (
              <button
                type="button"
                onClick={() => {
                  onSelect('');
                  setOpen(false);
                  setSearch('');
                }}
                className="w-full text-left px-4 py-3 text-sm text-gray-500 hover:bg-gray-50 min-h-[48px] border-b border-gray-100"
              >
                Clear selection
              </button>
            )}

            {filtered.length === 0 ? (
              <div className="px-4 py-6 text-sm text-gray-400 text-center">No results found</div>
            ) : (
              filtered.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => {
                    onSelect(item.id);
                    setOpen(false);
                    setSearch('');
                  }}
                  className={`w-full text-left px-4 py-3 text-sm min-h-[48px] transition-colors flex items-center justify-between ${
                    item.id === selectedId
                      ? 'bg-navy-50 text-navy-900'
                      : 'text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  <span>{renderItem(item)}</span>
                  {item.id === selectedId && <Check size={16} className="text-navy-600 shrink-0" />}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ------- Main Component -------

export default function NewWorkOrderPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const { user } = useAuthStore();
  const { generateKey, getKey, resetKey } = useIdempotencyKey();
  const { enqueue } = useOfflineQueue();

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Pre-fill from URL params
  const prefillSiteId = searchParams.get('site_id') || '';
  const prefillAssetId = searchParams.get('asset_id') || '';

  const [form, setForm] = useState<FormData>({
    ...initialForm,
    site_id: prefillSiteId,
    asset_id: prefillAssetId,
  });
  const [errors, setErrors] = useState<FormErrors>({});
  const [photos, setPhotos] = useState<File[]>([]);
  const [photoPreviewUrls, setPhotoPreviewUrls] = useState<string[]>([]);

  // Generate an idempotency key on mount
  useEffect(() => {
    generateKey();
  }, [generateKey]);

  // Fetch sites
  const { data: sites = [], isLoading: sitesLoading } = useQuery({
    queryKey: ['sites'],
    queryFn: () => sitesApi.list().then((r) => r.data),
  });

  // Fetch assets filtered by selected site
  const { data: assets = [], isLoading: assetsLoading } = useQuery({
    queryKey: ['assets', form.site_id],
    queryFn: () => assetsApi.list({ site_id: form.site_id || undefined }).then((r) => r.data),
    enabled: !!form.site_id,
  });

  // Fetch available technicians for assignment
  const { data: technicians = [] } = useQuery({
    queryKey: ['users', 'technicians'],
    queryFn: () =>
      apiClient.get<{ items: User[] }>('/users', { params: { role: 'TECHNICIAN', is_active: true } }).then((r) => r.data.items),
  });

  // Update form helper
  const updateForm = useCallback(<K extends keyof FormData>(key: K, value: FormData[K]) => {
    setForm((prev) => {
      const next = { ...prev, [key]: value };
      // Clear asset when site changes
      if (key === 'site_id' && value !== prev.site_id) {
        next.asset_id = '';
      }
      return next;
    });
    // Clear field error
    if (key in errors) {
      setErrors((prev) => ({ ...prev, [key]: undefined }));
    }
  }, [errors]);

  // Photo handlers
  const handleAddPhoto = () => {
    fileInputRef.current?.click();
  };

  const handlePhotoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;

    const newFiles = Array.from(files);
    setPhotos((prev) => [...prev, ...newFiles]);

    // Generate preview URLs
    const newUrls = newFiles.map((f) => URL.createObjectURL(f));
    setPhotoPreviewUrls((prev) => [...prev, ...newUrls]);

    // Reset input
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleRemovePhoto = (index: number) => {
    setPhotos((prev) => prev.filter((_, i) => i !== index));
    setPhotoPreviewUrls((prev) => {
      const url = prev[index];
      if (url) URL.revokeObjectURL(url);
      return prev.filter((_, i) => i !== index);
    });
  };

  // Cleanup preview URLs on unmount
  useEffect(() => {
    return () => {
      photoPreviewUrls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Validation
  const validate = (): boolean => {
    const newErrors: FormErrors = {};

    if (!form.title.trim()) {
      newErrors.title = 'Title is required';
    } else if (form.title.trim().length < 5) {
      newErrors.title = 'Title must be at least 5 characters';
    }

    if (!form.description.trim()) {
      newErrors.description = 'Description is required';
    }

    if (!form.site_id) {
      newErrors.site_id = 'Site selection is required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // Create mutation
  const createMutation = useMutation({
    mutationFn: async () => {
      const idempotencyKey = getKey();

      // Find the site's area and location for the WO
      const selectedSite = sites.find((s) => s.id === form.site_id);

      const payload: Partial<WorkOrder> = {
        title: form.title.trim(),
        description: form.description.trim(),
        priority: form.priority,
        type: form.type,
        safety_flag: form.safety_flag,
        safety_notes: form.safety_flag ? form.safety_notes.trim() : undefined,
        site_id: form.site_id,
        asset_id: form.asset_id || undefined,
        assigned_to: form.assigned_to || undefined,
        requested_by: user?.id,
        area_id: selectedSite?.org_id, // Will be resolved by backend from site
        location_id: selectedSite?.location_id,
        custom_fields: Object.keys(form.custom_fields).length > 0 ? form.custom_fields : undefined,
      };

      const response = await workOrderApi.create(payload, idempotencyKey);

      // Upload photos if any
      if (photos.length > 0) {
        for (const photo of photos) {
          const formData = new FormData();
          formData.append('file', photo);
          await workOrderApi.createAttachment(response.data.id, formData);
        }
      }

      return response.data;
    },
    onSuccess: (wo) => {
      queryClient.invalidateQueries({ queryKey: ['workOrders'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      resetKey();
      navigate(`/work-orders/${wo.id}`, { replace: true });
    },
    onError: (error: unknown) => {
      const axiosError = error as { response?: { status: number; data?: { detail?: string } } };
      setErrors({
        form: axiosError.response?.data?.detail || 'Failed to create work order. Please try again.',
      });
    },
  });

  // Offline-aware submit
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    if (!isOnline()) {
      // Enqueue for offline sync
      const idempotencyKey = getKey();
      const selectedSite = sites.find((s) => s.id === form.site_id);

      await enqueue({
        id: idempotencyKey,
        type: 'CREATE_WORK_ORDER',
        endpoint: '/work-orders',
        method: 'POST',
        payload: {
          title: form.title.trim(),
          description: form.description.trim(),
          priority: form.priority,
          type: form.type,
          safety_flag: form.safety_flag,
          safety_notes: form.safety_flag ? form.safety_notes.trim() : undefined,
          site_id: form.site_id,
          asset_id: form.asset_id || undefined,
          assigned_to: form.assigned_to || undefined,
          requested_by: user?.id,
          location_id: selectedSite?.location_id,
        },
        created_at: new Date().toISOString(),
      });

      resetKey();
      navigate('/work-orders', { replace: true });
      return;
    }

    createMutation.mutate();
  };

  const isSubmitting = createMutation.isPending;

  const priorityOptions = Object.values(WorkOrderPriority).map((p) => ({
    value: p,
    ...getPriorityConfig(p),
  }));

  const typeOptions = [
    { value: WorkOrderType.REACTIVE, label: 'Reactive' },
    { value: WorkOrderType.PREVENTIVE, label: 'Preventive' },
    { value: WorkOrderType.INSPECTION, label: 'Inspection' },
    { value: WorkOrderType.CORRECTIVE, label: 'Corrective' },
  ];

  return (
    <div className="max-w-2xl mx-auto pb-8">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => navigate(-1)}
          className="p-2 hover:bg-gray-100 rounded-lg min-w-[48px] min-h-[48px] flex items-center justify-center"
        >
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-xl font-bold text-gray-900">New Work Order</h1>
      </div>

      <form onSubmit={handleSubmit} noValidate>
        {/* Form error */}
        {errors.form && (
          <div className="flex items-start gap-2 p-3 mb-6 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
            <AlertTriangle size={16} className="shrink-0 mt-0.5" />
            <span>{errors.form}</span>
          </div>
        )}

        {/* Offline notice */}
        {!isOnline() && (
          <div className="flex items-start gap-2 p-3 mb-6 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-700">
            <AlertTriangle size={16} className="shrink-0 mt-0.5" />
            <span>You are offline. This work order will be queued and submitted when connectivity is restored.</span>
          </div>
        )}

        {/* ---- Safety Flag (prominent) ---- */}
        <div className={`rounded-xl p-4 mb-6 border-2 transition-colors ${
          form.safety_flag
            ? 'bg-amber-50 border-amber-400'
            : 'bg-gray-50 border-gray-200'
        }`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle size={20} className={form.safety_flag ? 'text-red-600' : 'text-gray-400'} />
              <div>
                <p className={`text-sm font-semibold ${form.safety_flag ? 'text-red-700' : 'text-gray-700'}`}>
                  Safety Flag
                </p>
                <p className="text-xs text-gray-500">Mark if this involves a safety hazard</p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => updateForm('safety_flag', !form.safety_flag)}
              className={`relative w-14 h-8 rounded-full transition-colors ${
                form.safety_flag ? 'bg-red-600' : 'bg-gray-300'
              }`}
              role="switch"
              aria-checked={form.safety_flag}
            >
              <span
                className={`absolute top-1 w-6 h-6 bg-white rounded-full transition-transform shadow ${
                  form.safety_flag ? 'translate-x-7' : 'translate-x-1'
                }`}
              />
            </button>
          </div>

          {form.safety_flag && (
            <div className="mt-3">
              <label className="block text-sm font-medium text-red-700 mb-1">Safety Notes</label>
              <textarea
                value={form.safety_notes}
                onChange={(e) => updateForm('safety_notes', e.target.value)}
                placeholder="Describe the safety concern..."
                rows={2}
                className="w-full px-4 py-3 border border-amber-300 rounded-lg text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-red-500 bg-white"
              />
            </div>
          )}
        </div>

        {/* ---- Title ---- */}
        <div className="mb-5">
          <label htmlFor="wo-title" className="block text-sm font-medium text-gray-700 mb-1">
            Title <span className="text-red-500">*</span>
          </label>
          <input
            id="wo-title"
            type="text"
            value={form.title}
            onChange={(e) => updateForm('title', e.target.value)}
            placeholder="Brief summary of the issue..."
            className={`w-full h-12 px-4 border rounded-lg text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-navy-500 focus:border-transparent ${
              errors.title ? 'border-red-300 bg-red-50' : 'border-gray-300'
            }`}
            disabled={isSubmitting}
          />
          {errors.title && <p className="mt-1 text-xs text-red-600">{errors.title}</p>}
        </div>

        {/* ---- Description ---- */}
        <div className="mb-5">
          <label htmlFor="wo-desc" className="block text-sm font-medium text-gray-700 mb-1">
            Description <span className="text-red-500">*</span>
          </label>
          <textarea
            id="wo-desc"
            value={form.description}
            onChange={(e) => updateForm('description', e.target.value)}
            placeholder="Detailed description of the work needed..."
            rows={4}
            className={`w-full px-4 py-3 border rounded-lg text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-navy-500 focus:border-transparent resize-y ${
              errors.description ? 'border-red-300 bg-red-50' : 'border-gray-300'
            }`}
            disabled={isSubmitting}
          />
          {errors.description && <p className="mt-1 text-xs text-red-600">{errors.description}</p>}
        </div>

        {/* ---- Priority & Type row ---- */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-5">
          {/* Priority */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Priority</label>
            <div className="grid grid-cols-2 gap-2">
              {priorityOptions.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => updateForm('priority', opt.value)}
                  className={`px-3 py-2.5 rounded-lg text-xs font-semibold min-h-[48px] transition-all border-2 ${
                    form.priority === opt.value
                      ? `${opt.bgColor} ${opt.textColor} ${opt.borderColor}`
                      : 'bg-white text-gray-600 border-gray-200 hover:border-gray-300'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Type */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Type</label>
            <div className="grid grid-cols-2 gap-2">
              {typeOptions.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => updateForm('type', opt.value)}
                  className={`px-3 py-2.5 rounded-lg text-xs font-semibold min-h-[48px] transition-all border-2 ${
                    form.type === opt.value
                      ? 'bg-navy-900 text-white border-navy-900'
                      : 'bg-white text-gray-600 border-gray-200 hover:border-gray-300'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* ---- Site selector ---- */}
        <div className="mb-5">
          <SearchableSelect<Site>
            label="Site *"
            placeholder="Select a site..."
            items={sites}
            selectedId={form.site_id}
            onSelect={(id) => updateForm('site_id', id)}
            renderItem={(site) => (
              <span>
                {site.name}{' '}
                <span className="text-xs text-gray-400 ml-1">{site.address || ''}</span>
              </span>
            )}
            getLabel={(site) => site.name}
            isLoading={sitesLoading}
            error={errors.site_id}
            disabled={isSubmitting}
          />
        </div>

        {/* ---- Asset selector (filtered by site) ---- */}
        <div className="mb-5">
          <SearchableSelect<Asset>
            label="Asset (optional)"
            placeholder={form.site_id ? 'Select an asset at this site...' : 'Select a site first'}
            items={assets}
            selectedId={form.asset_id}
            onSelect={(id) => updateForm('asset_id', id)}
            renderItem={(asset) => (
              <span>
                {asset.name}{' '}
                <span className="text-xs text-gray-400 ml-1">
                  {[asset.manufacturer, asset.model].filter(Boolean).join(' ')}
                </span>
              </span>
            )}
            getLabel={(asset) => asset.name}
            isLoading={assetsLoading}
            disabled={isSubmitting || !form.site_id}
          />
        </div>

        {/* ---- Assign To ---- */}
        <div className="mb-5">
          <SearchableSelect<User>
            label="Assign To (optional)"
            placeholder="Leave unassigned or select a technician..."
            items={technicians}
            selectedId={form.assigned_to}
            onSelect={(id) => updateForm('assigned_to', id)}
            renderItem={(tech) => (
              <span className="flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-navy-200 flex items-center justify-center text-[10px] font-semibold text-navy-800 shrink-0">
                  {tech.name?.charAt(0).toUpperCase() || '?'}
                </span>
                {tech.name}
              </span>
            )}
            getLabel={(tech) => tech.name}
            disabled={isSubmitting}
          />
        </div>

        {/* ---- Requested By (auto-filled) ---- */}
        <div className="mb-5">
          <label className="block text-sm font-medium text-gray-700 mb-1">Requested By</label>
          <div className="h-12 px-4 bg-gray-100 border border-gray-200 rounded-lg flex items-center gap-2 text-sm text-gray-600">
            {user && (
              <>
                <span className="w-6 h-6 rounded-full bg-navy-200 flex items-center justify-center text-[10px] font-semibold text-navy-800">
                  {user.name?.charAt(0).toUpperCase() || 'U'}
                </span>
                {user.name}
                <span className="text-gray-400 ml-1">({user.email})</span>
              </>
            )}
          </div>
        </div>

        {/* ---- Custom Fields ---- */}
        <div className="mb-5">
          <label className="block text-sm font-medium text-gray-700 mb-1">Custom Fields</label>
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
            {Object.entries(form.custom_fields).map(([key, value]) => (
              <div key={key} className="flex items-center gap-2 mb-2 last:mb-0">
                <input
                  type="text"
                  value={key}
                  readOnly
                  className="flex-1 h-10 px-3 text-sm border border-gray-200 rounded bg-white text-gray-700"
                />
                <input
                  type="text"
                  value={value}
                  onChange={(e) => {
                    const updated = { ...form.custom_fields, [key]: e.target.value };
                    updateForm('custom_fields', updated);
                  }}
                  className="flex-1 h-10 px-3 text-sm border border-gray-200 rounded bg-white text-gray-900 focus:outline-none focus:ring-1 focus:ring-navy-500"
                />
                <button
                  type="button"
                  onClick={() => {
                    const updated = { ...form.custom_fields };
                    delete updated[key];
                    updateForm('custom_fields', updated);
                  }}
                  className="p-2 text-gray-400 hover:text-red-500 min-w-[44px] min-h-[44px] flex items-center justify-center"
                >
                  <X size={16} />
                </button>
              </div>
            ))}

            <button
              type="button"
              onClick={() => {
                const key = `field_${Object.keys(form.custom_fields).length + 1}`;
                updateForm('custom_fields', { ...form.custom_fields, [key]: '' });
              }}
              className="inline-flex items-center gap-1 text-sm text-navy-600 hover:text-navy-800 font-medium mt-2 min-h-[48px]"
            >
              <Plus size={14} /> Add custom field
            </button>
          </div>
        </div>

        {/* ---- Photos ---- */}
        <div className="mb-8">
          <label className="block text-sm font-medium text-gray-700 mb-1">Photos</label>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            capture="environment"
            multiple
            onChange={handlePhotoChange}
            className="hidden"
          />

          <div className="flex flex-wrap gap-3">
            {/* Photo previews */}
            {photoPreviewUrls.map((url, index) => (
              <div key={index} className="relative w-20 h-20 rounded-lg overflow-hidden border border-gray-200">
                <img src={url} alt={`Photo ${index + 1}`} className="w-full h-full object-cover" />
                <button
                  type="button"
                  onClick={() => handleRemovePhoto(index)}
                  className="absolute top-0.5 right-0.5 p-1 bg-black/50 text-white rounded-full hover:bg-black/70"
                >
                  <X size={12} />
                </button>
              </div>
            ))}

            {/* Add photo button */}
            <button
              type="button"
              onClick={handleAddPhoto}
              className="w-20 h-20 border-2 border-dashed border-gray-300 rounded-lg flex flex-col items-center justify-center text-gray-400 hover:text-gray-600 hover:border-gray-400 transition-colors"
            >
              <Camera size={20} />
              <span className="text-[10px] mt-1">Add</span>
            </button>
          </div>
          {photos.length > 0 && (
            <p className="text-xs text-gray-400 mt-2">{photos.length} photo{photos.length !== 1 ? 's' : ''} attached</p>
          )}
        </div>

        {/* ---- Action buttons ---- */}
        <div className="flex flex-col sm:flex-row gap-3">
          <button
            type="submit"
            disabled={isSubmitting}
            className="flex-1 h-12 bg-navy-900 hover:bg-navy-800 disabled:bg-navy-400 text-white font-semibold rounded-lg transition-colors flex items-center justify-center gap-2"
          >
            {isSubmitting ? (
              <>
                <Loader2 size={18} className="animate-spin" />
                Creating...
              </>
            ) : (
              <>
                <Plus size={18} />
                Create Work Order
              </>
            )}
          </button>

          <button
            type="button"
            onClick={() => navigate(-1)}
            disabled={isSubmitting}
            className="sm:w-auto h-12 px-6 bg-white hover:bg-gray-50 text-gray-700 font-medium border border-gray-300 rounded-lg transition-colors"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
