import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';

export function useQRScanner() {
  const navigate = useNavigate();
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleScanResult = useCallback(
    (decodedText: string) => {
      setScanning(false);

      try {
        const url = new URL(decodedText);
        const path = url.pathname;

        if (path.includes('/scan/site/')) {
          const token = path.split('/scan/site/')[1];
          navigate(`/scan?type=site&token=${token}`);
        } else if (path.includes('/scan/asset/')) {
          const token = path.split('/scan/asset/')[1];
          navigate(`/scan?type=asset&token=${token}`);
        } else if (path.includes('/scan/location/')) {
          const token = path.split('/scan/location/')[1];
          navigate(`/scan?type=location&token=${token}`);
        } else if (path.includes('/scan/part/')) {
          const token = path.split('/scan/part/')[1];
          navigate(`/scan?type=part&token=${token}`);
        } else {
          setError('Unrecognized QR code format');
        }
      } catch {
        setError('Invalid QR code');
      }
    },
    [navigate]
  );

  return { scanning, setScanning, error, setError, handleScanResult };
}
