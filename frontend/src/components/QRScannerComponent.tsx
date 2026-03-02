import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Camera, CameraOff, Flashlight, FlashlightOff, RotateCcw,
  ScanLine, X, AlertCircle, ExternalLink,
} from 'lucide-react';
import { Html5Qrcode, Html5QrcodeScannerState } from 'html5-qrcode';

interface Props {
  onScanResult?: (decodedText: string) => void;
  autoNavigate?: boolean;
}

type ScanState = 'idle' | 'scanning' | 'result' | 'error';

interface ParsedQRResult {
  entityType: string;
  token: string;
  navigateTo: string;
  label: string;
}

function parseQRResult(text: string): ParsedQRResult | null {
  try {
    const url = new URL(text);
    const path = url.pathname;

    const patterns: { pattern: string; type: string; label: string; route: string }[] = [
      { pattern: '/scan/site/', type: 'site', label: 'Site', route: '/scan?type=site&token=' },
      { pattern: '/scan/asset/', type: 'asset', label: 'Asset', route: '/scan?type=asset&token=' },
      { pattern: '/scan/location/', type: 'location', label: 'Location', route: '/scan?type=location&token=' },
      { pattern: '/scan/part/', type: 'part', label: 'Part', route: '/scan?type=part&token=' },
    ];

    for (const { pattern, type, label, route } of patterns) {
      if (path.includes(pattern)) {
        const token = path.split(pattern)[1];
        if (token) {
          return {
            entityType: type,
            token,
            navigateTo: `${route}${token}`,
            label,
          };
        }
      }
    }

    return null;
  } catch {
    return null;
  }
}

export default function QRScannerComponent({ onScanResult, autoNavigate = true }: Props) {
  const navigate = useNavigate();
  const [scanState, setScanState] = useState<ScanState>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [scannedText, setScannedText] = useState<string | null>(null);
  const [parsedResult, setParsedResult] = useState<ParsedQRResult | null>(null);
  const [flashEnabled, setFlashEnabled] = useState(false);
  const [facingMode, setFacingMode] = useState<'environment' | 'user'>('environment');
  const scannerRef = useRef<Html5Qrcode | null>(null);
  const scannerElementId = 'qr-scanner-viewport';

  const stopScanner = useCallback(async () => {
    try {
      if (scannerRef.current) {
        const state = scannerRef.current.getState();
        if (state === Html5QrcodeScannerState.SCANNING || state === Html5QrcodeScannerState.PAUSED) {
          await scannerRef.current.stop();
        }
      }
    } catch {
      // Scanner may already be stopped
    }
  }, []);

  const startScanner = useCallback(async () => {
    setErrorMessage(null);
    setScanState('scanning');
    setScannedText(null);
    setParsedResult(null);

    try {
      if (!scannerRef.current) {
        scannerRef.current = new Html5Qrcode(scannerElementId);
      } else {
        await stopScanner();
      }

      await scannerRef.current.start(
        { facingMode },
        {
          fps: 10,
          qrbox: { width: 250, height: 250 },
          aspectRatio: 1.0,
        },
        (decodedText) => {
          setScannedText(decodedText);
          const parsed = parseQRResult(decodedText);
          setParsedResult(parsed);
          setScanState('result');

          // Notify parent
          onScanResult?.(decodedText);

          // Stop scanner after successful scan
          stopScanner();

          // Auto-navigate if enabled and result is valid
          if (autoNavigate && parsed) {
            navigate(parsed.navigateTo);
          }
        },
        () => {
          // Scanning in progress - no QR found in this frame
        }
      );
    } catch (err) {
      const errorMsg =
        err instanceof Error ? err.message : 'Failed to start camera';

      if (errorMsg.includes('NotAllowed') || errorMsg.includes('Permission')) {
        setErrorMessage(
          'Camera permission denied. Please allow camera access in your browser settings to scan QR codes.'
        );
      } else if (errorMsg.includes('NotFound') || errorMsg.includes('no camera')) {
        setErrorMessage('No camera found on this device.');
      } else {
        setErrorMessage(`Camera error: ${errorMsg}`);
      }
      setScanState('error');
    }
  }, [facingMode, autoNavigate, navigate, onScanResult, stopScanner]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopScanner();
    };
  }, [stopScanner]);

  const handleToggleFlash = async () => {
    if (!scannerRef.current) return;
    try {
      const track = scannerRef.current.getRunningTrackSettings();
      if (track) {
        // Toggle flash via torch capability
        const capabilities = scannerRef.current.getRunningTrackCameraCapabilities();
        if (capabilities.torchFeature().isSupported()) {
          await capabilities.torchFeature().apply(!flashEnabled);
          setFlashEnabled(!flashEnabled);
        }
      }
    } catch {
      // Torch not supported on this device/browser
    }
  };

  const handleSwitchCamera = async () => {
    const newMode = facingMode === 'environment' ? 'user' : 'environment';
    setFacingMode(newMode);
    if (scanState === 'scanning') {
      await stopScanner();
      // startScanner will be triggered by the facingMode change through a useEffect
    }
  };

  // Restart scanner when facingMode changes and we were scanning
  useEffect(() => {
    if (scanState === 'scanning') {
      startScanner();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [facingMode]);

  const handleNavigate = () => {
    if (parsedResult) {
      navigate(parsedResult.navigateTo);
    }
  };

  const handleReset = () => {
    setScanState('idle');
    setScannedText(null);
    setParsedResult(null);
    setErrorMessage(null);
  };

  return (
    <div className="flex flex-col items-center w-full max-w-md mx-auto">
      {/* Scanner viewport */}
      <div className="relative w-full aspect-square bg-black rounded-xl overflow-hidden mb-4">
        <div id={scannerElementId} className="w-full h-full" />

        {/* Idle state overlay */}
        {scanState === 'idle' && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-gray-900 text-white">
            <Camera size={48} className="text-gray-400 mb-4" />
            <p className="text-sm text-gray-300 mb-6 text-center px-4">
              Point your camera at a QR code on any site, asset, or part label.
            </p>
            <button
              onClick={startScanner}
              className="
                min-h-[48px] px-6 py-3 bg-navy-600 hover:bg-navy-700
                text-white rounded-lg font-medium text-sm transition-colors
                inline-flex items-center gap-2
              "
            >
              <Camera size={20} />
              Start Scanner
            </button>
          </div>
        )}

        {/* Scanning overlay with viewfinder */}
        {scanState === 'scanning' && (
          <div className="absolute inset-0 pointer-events-none">
            {/* Corner brackets for viewfinder */}
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-[250px] h-[250px] relative">
                {/* Top-left corner */}
                <div className="absolute top-0 left-0 w-8 h-8 border-t-4 border-l-4 border-white rounded-tl-lg" />
                {/* Top-right corner */}
                <div className="absolute top-0 right-0 w-8 h-8 border-t-4 border-r-4 border-white rounded-tr-lg" />
                {/* Bottom-left corner */}
                <div className="absolute bottom-0 left-0 w-8 h-8 border-b-4 border-l-4 border-white rounded-bl-lg" />
                {/* Bottom-right corner */}
                <div className="absolute bottom-0 right-0 w-8 h-8 border-b-4 border-r-4 border-white rounded-br-lg" />
                {/* Scanning line animation */}
                <div className="absolute inset-x-4 h-0.5 bg-green-400 animate-scan-line" />
              </div>
            </div>
            <p className="absolute bottom-6 left-0 right-0 text-center text-white text-sm font-medium drop-shadow-lg">
              Scanning...
            </p>
          </div>
        )}

        {/* Error state overlay */}
        {scanState === 'error' && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-gray-900 text-white p-6">
            <CameraOff size={48} className="text-red-400 mb-4" />
            <p className="text-sm text-red-300 text-center mb-6">
              {errorMessage || 'Unable to access camera'}
            </p>
            <button
              onClick={startScanner}
              className="
                min-h-[48px] px-6 py-3 bg-navy-600 hover:bg-navy-700
                text-white rounded-lg font-medium text-sm transition-colors
                inline-flex items-center gap-2
              "
            >
              <RotateCcw size={18} />
              Try Again
            </button>
          </div>
        )}

        {/* Result state overlay */}
        {scanState === 'result' && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-gray-900/95 text-white p-6">
            {parsedResult ? (
              <>
                <div className="w-16 h-16 rounded-full bg-green-500/20 flex items-center justify-center mb-4">
                  <ScanLine size={32} className="text-green-400" />
                </div>
                <p className="text-lg font-bold mb-1">
                  {parsedResult.label} Found
                </p>
                <p className="text-sm text-gray-300 mb-6">
                  QR code recognized successfully.
                </p>
                <div className="flex flex-col gap-3 w-full max-w-xs">
                  <button
                    onClick={handleNavigate}
                    className="
                      min-h-[48px] px-6 py-3 bg-green-600 hover:bg-green-700
                      text-white rounded-lg font-medium text-sm transition-colors
                      inline-flex items-center justify-center gap-2
                    "
                  >
                    <ExternalLink size={18} />
                    View {parsedResult.label}
                  </button>
                  <button
                    onClick={handleReset}
                    className="
                      min-h-[48px] px-6 py-3 bg-gray-700 hover:bg-gray-600
                      text-white rounded-lg font-medium text-sm transition-colors
                      inline-flex items-center justify-center gap-2
                    "
                  >
                    <RotateCcw size={18} />
                    Scan Another
                  </button>
                </div>
              </>
            ) : (
              <>
                <div className="w-16 h-16 rounded-full bg-yellow-500/20 flex items-center justify-center mb-4">
                  <AlertCircle size={32} className="text-yellow-400" />
                </div>
                <p className="text-lg font-bold mb-1">Unknown QR Code</p>
                <p className="text-sm text-gray-300 text-center mb-2">
                  This QR code is not recognized as an OFMaint entity.
                </p>
                <p className="text-xs text-gray-500 font-mono break-all text-center mb-6 px-4">
                  {scannedText}
                </p>
                <button
                  onClick={handleReset}
                  className="
                    min-h-[48px] px-6 py-3 bg-gray-700 hover:bg-gray-600
                    text-white rounded-lg font-medium text-sm transition-colors
                    inline-flex items-center justify-center gap-2
                  "
                >
                  <RotateCcw size={18} />
                  Scan Again
                </button>
              </>
            )}
          </div>
        )}
      </div>

      {/* Controls bar (visible while scanning) */}
      {scanState === 'scanning' && (
        <div className="flex items-center justify-center gap-4 w-full">
          <button
            onClick={handleToggleFlash}
            className="
              min-h-[48px] min-w-[48px] flex items-center justify-center
              p-3 bg-gray-800 hover:bg-gray-700 text-white rounded-full transition-colors
            "
            aria-label={flashEnabled ? 'Turn off flash' : 'Turn on flash'}
          >
            {flashEnabled ? <FlashlightOff size={22} /> : <Flashlight size={22} />}
          </button>

          <button
            onClick={() => { stopScanner(); handleReset(); }}
            className="
              min-h-[48px] min-w-[48px] flex items-center justify-center
              p-3 bg-red-600 hover:bg-red-700 text-white rounded-full transition-colors
            "
            aria-label="Stop scanning"
          >
            <X size={22} />
          </button>

          <button
            onClick={handleSwitchCamera}
            className="
              min-h-[48px] min-w-[48px] flex items-center justify-center
              p-3 bg-gray-800 hover:bg-gray-700 text-white rounded-full transition-colors
            "
            aria-label={facingMode === 'environment' ? 'Switch to front camera' : 'Switch to rear camera'}
          >
            <RotateCcw size={22} />
          </button>
        </div>
      )}
    </div>
  );
}
