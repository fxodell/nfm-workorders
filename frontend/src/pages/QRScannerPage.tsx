import { useState, useCallback, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ArrowLeft, Camera, Keyboard,
  MapPin, Wrench, Box, AlertTriangle, Loader2,
} from 'lucide-react';
import { useQRScanner } from '@/hooks/useQRScanner';
import QRScannerComponent from '@/components/QRScannerComponent';
import apiClient from '@/api/client';
import type { ScanResponse } from '@/types/api';

type EntityType = 'site' | 'asset' | 'location' | 'part';

export default function QRScannerPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { error: scanError, setError, handleScanResult } = useQRScanner();

  const [manualMode, setManualMode] = useState(false);
  const [manualInput, setManualInput] = useState('');

  // Check if we arrived via a scan redirect (e.g. /scan?type=site&token=xyz)
  const scannedType = searchParams.get('type') as EntityType | null;
  const scannedToken = searchParams.get('token');

  const { data: scanResult, isLoading: scanLoading, error: lookupError } = useQuery({
    queryKey: ['scan', scannedType, scannedToken],
    queryFn: async () => {
      const res = await apiClient.get<ScanResponse>(
        `/scan/${scannedType}/${scannedToken}`
      );
      return res.data;
    },
    enabled: !!scannedType && !!scannedToken,
  });

  // Navigate to detail page once we have the scan result
  useEffect(() => {
    if (!scanResult || !scannedType) return;

    const routes: Record<EntityType, string> = {
      site: `/sites/${scanResult.id}`,
      asset: `/assets/${scanResult.id}`,
      location: `/sites/${scanResult.parent_id || scanResult.id}`,
      part: `/inventory/${scanResult.id}`,
    };

    const target = routes[scannedType];
    if (target) {
      navigate(target, { replace: true });
    }
  }, [scanResult, scannedType, navigate]);

  const handleManualSubmit = useCallback(() => {
    const value = manualInput.trim();
    if (!value) return;

    // Try to parse as a full URL or as a path pattern
    try {
      let path = value;
      try {
        const url = new URL(value);
        path = url.pathname;
      } catch {
        // Not a full URL, treat as path
      }

      const scanPattern = /\/scan\/(site|asset|location|part)\/(.+)/;
      const match = path.match(scanPattern);

      if (match) {
        const [, entityType, token] = match;
        navigate(`/scan?type=${entityType}&token=${token}`, { replace: true });
      } else {
        setError('Unrecognized format. Expected: /scan/{type}/{token}');
      }
    } catch {
      setError('Invalid input. Please enter a valid QR code value.');
    }
  }, [manualInput, navigate, setError]);

  // Loading state for scan lookup
  if (scannedType && scannedToken) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        {scanLoading && (
          <>
            <Loader2 size={48} className="animate-spin text-navy-600" />
            <p className="text-gray-600 text-lg">Looking up {scannedType}...</p>
          </>
        )}
        {lookupError && (
          <div className="text-center space-y-4">
            <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto">
              <AlertTriangle size={32} className="text-red-600" />
            </div>
            <h2 className="text-lg font-semibold text-gray-900">Not Found</h2>
            <p className="text-gray-500">
              Could not find {scannedType} with this QR code. It may have been deactivated.
            </p>
            <button
              onClick={() => navigate('/scan', { replace: true })}
              className="mt-4 px-6 py-3 bg-navy-900 text-white rounded-lg font-medium min-h-[48px]"
            >
              Scan Again
            </button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full -m-4">
      {/* Header */}
      <div className="bg-navy-900 text-white px-4 py-3 flex items-center justify-between z-10">
        <button
          onClick={() => navigate(-1)}
          className="p-3 hover:bg-navy-800 rounded-lg min-h-[48px] min-w-[48px] flex items-center justify-center"
          aria-label="Go back"
        >
          <ArrowLeft size={24} />
        </button>
        <h1 className="text-lg font-semibold">QR Scanner</h1>
        <button
          onClick={() => setManualMode(!manualMode)}
          className="p-3 hover:bg-navy-800 rounded-lg min-h-[48px] min-w-[48px] flex items-center justify-center"
          aria-label={manualMode ? 'Use camera' : 'Manual entry'}
        >
          {manualMode ? <Camera size={24} /> : <Keyboard size={24} />}
        </button>
      </div>

      {/* Main content area */}
      <div className="flex-1 flex flex-col bg-black relative">
        {!manualMode ? (
          <div className="flex-1 flex items-center justify-center p-4">
            <QRScannerComponent onScanResult={handleScanResult} autoNavigate={false} />
          </div>
        ) : (
          /* Manual entry mode */
          <div className="flex-1 bg-gray-50 p-6 flex flex-col">
            <div className="flex-1 flex flex-col items-center justify-center max-w-md mx-auto w-full gap-6">
              <div className="w-20 h-20 bg-navy-100 rounded-2xl flex items-center justify-center">
                <Keyboard size={40} className="text-navy-600" />
              </div>
              <div className="text-center">
                <h2 className="text-xl font-semibold text-gray-900 mb-2">
                  Manual Entry
                </h2>
                <p className="text-gray-500 text-sm">
                  Enter the QR code value or URL printed below the code
                </p>
              </div>
              <div className="w-full space-y-4">
                <input
                  type="text"
                  value={manualInput}
                  onChange={(e) => {
                    setManualInput(e.target.value);
                    if (scanError) setError(null);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleManualSubmit();
                  }}
                  placeholder="e.g. https://app.example.com/scan/site/abc123"
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-navy-500 focus:border-navy-500 min-h-[48px]"
                  autoFocus
                />
                <button
                  onClick={handleManualSubmit}
                  disabled={!manualInput.trim()}
                  className="w-full py-3 bg-navy-900 text-white rounded-lg font-semibold min-h-[48px] disabled:opacity-50 disabled:cursor-not-allowed active:bg-navy-800 transition-colors"
                >
                  Look Up
                </button>
              </div>

              {/* Quick type shortcuts */}
              <div className="w-full">
                <p className="text-xs text-gray-400 mb-2 text-center">Supported types</p>
                <div className="flex flex-wrap justify-center gap-2">
                  {[
                    { type: 'site', icon: MapPin, label: 'Site' },
                    { type: 'asset', icon: Wrench, label: 'Asset' },
                    { type: 'location', icon: MapPin, label: 'Location' },
                    { type: 'part', icon: Box, label: 'Part' },
                  ].map(({ type, icon: Icon, label }) => (
                    <span
                      key={type}
                      className="inline-flex items-center gap-1 px-3 py-1.5 bg-gray-100 text-gray-600 text-xs rounded-full"
                    >
                      <Icon size={12} />
                      {label}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Error toast */}
      {scanError && (
        <div className="absolute bottom-24 left-4 right-4 bg-red-600 text-white px-4 py-3 rounded-lg shadow-lg flex items-center gap-3 z-20">
          <AlertTriangle size={20} className="shrink-0" />
          <span className="text-sm flex-1">{scanError}</span>
          <button
            onClick={() => setError(null)}
            className="text-white/80 hover:text-white font-bold text-lg min-h-[48px] min-w-[48px] flex items-center justify-center"
          >
            &times;
          </button>
        </div>
      )}
    </div>
  );
}
