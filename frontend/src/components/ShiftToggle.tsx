import { useShiftToggle } from '@/hooks/useShiftToggle';

export default function ShiftToggle() {
  const { onShift, toggleShift } = useShiftToggle();
  return (
    <button
      onClick={toggleShift}
      className={`inline-flex items-center gap-2 px-3 py-2 rounded-full text-sm font-medium transition-colors min-h-touch ${
        onShift ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-500'
      }`}
    >
      <span className={`w-2 h-2 rounded-full ${onShift ? 'bg-green-500' : 'bg-gray-400'}`} />
      {onShift ? 'On Shift' : 'Off Shift'}
    </button>
  );
}
