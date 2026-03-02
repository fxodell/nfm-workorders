import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Loader2 } from 'lucide-react';
import { workOrderApi } from '@/api/workOrders';
import WorkOrderDetailPanel from '@/components/WorkOrderDetailPanel';

export default function WorkOrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const {
    data: workOrder,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['workOrders', id],
    queryFn: () => workOrderApi.get(id!),
    enabled: !!id,
    refetchInterval: 30_000,
  });

  const timelineQuery = useQuery({
    queryKey: ['workOrders', id, 'timeline'],
    queryFn: () => workOrderApi.getTimeline(id!),
    enabled: !!id,
  });

  const partsQuery = useQuery({
    queryKey: ['workOrders', id, 'parts'],
    queryFn: () => workOrderApi.getParts(id!),
    enabled: !!id,
  });

  const laborQuery = useQuery({
    queryKey: ['workOrders', id, 'labor'],
    queryFn: () => workOrderApi.getLabor(id!),
    enabled: !!id,
  });

  const attachmentsQuery = useQuery({
    queryKey: ['workOrders', id, 'attachments'],
    queryFn: () => workOrderApi.getAttachments(id!),
    enabled: !!id,
  });

  const messagesQuery = useQuery({
    queryKey: ['workOrders', id, 'messages'],
    queryFn: () => workOrderApi.getMessages(id!),
    enabled: !!id,
    refetchInterval: 15_000,
  });

  const transitionMutation = useMutation({
    mutationFn: ({ action, body }: { action: string; body?: Record<string, unknown> }) =>
      workOrderApi.transition(id!, action, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workOrders', id] });
      queryClient.invalidateQueries({ queryKey: ['workOrders', id, 'timeline'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });

  const addPartMutation = useMutation({
    mutationFn: (data: { part_id: string; quantity: number }) =>
      workOrderApi.addPart(id!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workOrders', id, 'parts'] });
    },
  });

  const addLaborMutation = useMutation({
    mutationFn: (data: { description: string; minutes: number }) =>
      workOrderApi.addLabor(id!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workOrders', id, 'labor'] });
    },
  });

  const sendMessageMutation = useMutation({
    mutationFn: (message: string) =>
      workOrderApi.sendMessage(id!, { message }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workOrders', id, 'messages'] });
    },
  });

  const uploadAttachmentMutation = useMutation({
    mutationFn: (file: File) =>
      workOrderApi.createAttachment(id!, file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workOrders', id, 'attachments'] });
    },
  });

  const toggleSafetyFlagMutation = useMutation({
    mutationFn: (safety_flag: boolean) =>
      workOrderApi.update(id!, { safety_flag }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workOrders', id] });
      queryClient.invalidateQueries({ queryKey: ['workOrders', id, 'timeline'] });
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 animate-spin text-navy-600" />
      </div>
    );
  }

  if (error || !workOrder) {
    return (
      <div className="p-4">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-2 text-gray-600 min-h-[48px]"
        >
          <ArrowLeft className="w-5 h-5" />
          Back
        </button>
        <div className="mt-8 text-center">
          <p className="text-gray-500 text-lg">Work order not found</p>
          <button
            onClick={() => navigate('/work-orders')}
            className="mt-4 px-6 py-3 bg-navy-600 text-white rounded-lg min-h-[48px]"
          >
            View All Work Orders
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="pb-4">
      <div className="px-4 py-2">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-2 text-gray-600 hover:text-gray-900 min-h-[48px]"
        >
          <ArrowLeft className="w-5 h-5" />
          Back
        </button>
      </div>

      <WorkOrderDetailPanel
        workOrder={workOrder}
        timeline={timelineQuery.data ?? []}
        messages={messagesQuery.data ?? []}
        parts={partsQuery.data ?? []}
        labor={laborQuery.data ?? []}
        attachments={attachmentsQuery.data ?? []}
        onTransition={(action, body) => transitionMutation.mutate({ action, body })}
        onAddPart={(data) => addPartMutation.mutate(data)}
        onRemovePart={(partId) => workOrderApi.removePart(id!, partId).then(() =>
          queryClient.invalidateQueries({ queryKey: ['workOrders', id, 'parts'] })
        )}
        onAddLabor={(data) => addLaborMutation.mutate(data)}
        onRemoveLabor={(laborId) => workOrderApi.removeLabor(id!, laborId).then(() =>
          queryClient.invalidateQueries({ queryKey: ['workOrders', id, 'labor'] })
        )}
        onSendMessage={(msg) => sendMessageMutation.mutate(msg)}
        onUploadAttachment={(file) => uploadAttachmentMutation.mutate(file)}
        onToggleSafetyFlag={(flag) => toggleSafetyFlagMutation.mutate(flag)}
        isTransitioning={transitionMutation.isPending}
      />
    </div>
  );
}
