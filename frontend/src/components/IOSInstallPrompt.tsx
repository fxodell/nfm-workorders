import { X, Share, PlusSquare } from 'lucide-react';
import { useIOSInstallPrompt } from '@/hooks/useIOSInstallPrompt';

export default function IOSInstallPrompt() {
  const { showPrompt, dismiss } = useIOSInstallPrompt();

  if (!showPrompt) return null;

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-white border-t-2 border-navy-900 p-4 z-50 shadow-lg">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <h3 className="font-semibold text-navy-900">Install OilfieldMaint</h3>
          <p className="text-sm text-gray-600 mt-1">
            Install this app to your Home Screen for the best experience and push notifications.
          </p>
          <ol className="text-sm text-gray-600 mt-2 space-y-1">
            <li className="flex items-center gap-2">1. Tap <Share size={16} className="text-blue-500" /> Share in Safari</li>
            <li className="flex items-center gap-2">2. Tap <PlusSquare size={16} /> Add to Home Screen</li>
            <li>3. Open the app from your home screen</li>
          </ol>
        </div>
        <button onClick={dismiss} className="p-2 hover:bg-gray-100 rounded min-h-touch min-w-touch flex items-center justify-center">
          <X size={20} />
        </button>
      </div>
    </div>
  );
}
