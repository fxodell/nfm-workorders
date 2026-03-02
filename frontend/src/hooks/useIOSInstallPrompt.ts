import { useState, useEffect } from 'react';

export function useIOSInstallPrompt() {
  const [showPrompt, setShowPrompt] = useState(false);

  const isIOS = /iPhone|iPad|iPod/.test(navigator.userAgent);
  const isStandalone = 'standalone' in window.navigator && (window.navigator as { standalone?: boolean }).standalone === true;

  useEffect(() => {
    if (!isIOS || isStandalone) return;

    const dismissed = localStorage.getItem('ofmaint-ios-install-dismissed');
    if (dismissed) {
      const dismissedAt = new Date(dismissed).getTime();
      const sevenDays = 7 * 24 * 60 * 60 * 1000;
      if (Date.now() - dismissedAt < sevenDays) return;
    }

    setShowPrompt(true);
  }, [isIOS, isStandalone]);

  const dismiss = () => {
    setShowPrompt(false);
    localStorage.setItem('ofmaint-ios-install-dismissed', new Date().toISOString());
  };

  return { showPrompt, dismiss, isIOS, isStandalone };
}
