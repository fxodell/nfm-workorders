import { useState, useRef, useEffect } from 'react';
import { X, Copy, Check, ShieldCheck, Loader2 } from 'lucide-react';
import type { MFASetupResponse } from '@/types/api';

interface Props {
  mfaSetup: MFASetupResponse;
  onVerify: (code: string) => Promise<boolean>;
  onCancel: () => void;
}

export default function MFASetupModal({ mfaSetup, onVerify, onCancel }: Props) {
  const [code, setCode] = useState<string[]>(['', '', '', '', '', '']);
  const [error, setError] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [secretCopied, setSecretCopied] = useState(false);
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  // Focus first input on mount
  useEffect(() => {
    inputRefs.current[0]?.focus();
  }, []);

  const handleInputChange = (index: number, value: string) => {
    // Only allow digits
    const digit = value.replace(/\D/g, '').slice(-1);

    const newCode = [...code];
    newCode[index] = digit;
    setCode(newCode);
    setError(null);

    // Auto-advance to next input
    if (digit && index < 5) {
      inputRefs.current[index + 1]?.focus();
    }

    // Auto-submit when all 6 digits are entered
    if (digit && index === 5) {
      const fullCode = [...newCode].join('');
      if (fullCode.length === 6) {
        handleVerify(fullCode);
      }
    }
  };

  const handleKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Backspace' && !code[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    e.preventDefault();
    const pastedText = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
    if (pastedText.length === 0) return;

    const newCode = [...code];
    for (let i = 0; i < 6; i++) {
      newCode[i] = pastedText[i] || '';
    }
    setCode(newCode);

    // Focus the next empty input or the last input
    const nextEmpty = newCode.findIndex((d) => !d);
    if (nextEmpty >= 0) {
      inputRefs.current[nextEmpty]?.focus();
    } else {
      inputRefs.current[5]?.focus();
      // Auto-submit
      handleVerify(newCode.join(''));
    }
  };

  const handleVerify = async (fullCode?: string) => {
    const codeToVerify = fullCode || code.join('');
    if (codeToVerify.length !== 6) {
      setError('Please enter all 6 digits.');
      return;
    }

    setVerifying(true);
    setError(null);

    try {
      const success = await onVerify(codeToVerify);
      if (!success) {
        setError('Invalid verification code. Please try again.');
        setCode(['', '', '', '', '', '']);
        inputRefs.current[0]?.focus();
      }
    } catch {
      setError('Verification failed. Please try again.');
      setCode(['', '', '', '', '', '']);
      inputRefs.current[0]?.focus();
    } finally {
      setVerifying(false);
    }
  };

  const handleCopySecret = async () => {
    try {
      await navigator.clipboard.writeText(mfaSetup.secret);
      setSecretCopied(true);
      setTimeout(() => setSecretCopied(false), 2000);
    } catch {
      // Fallback: select text for manual copy
    }
  };

  const handleBackdropClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) {
      onCancel();
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Set up two-factor authentication"
      onClick={handleBackdropClick}
    >
      <div className="bg-white rounded-xl shadow-xl max-w-md w-full max-h-[90vh] overflow-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <div className="flex items-center gap-2">
            <ShieldCheck size={20} className="text-green-600" />
            <h2 className="text-lg font-bold text-gray-900">Set Up MFA</h2>
          </div>
          <button
            onClick={onCancel}
            className="min-h-[48px] min-w-[48px] flex items-center justify-center p-2 hover:bg-gray-100 rounded-lg transition-colors"
            aria-label="Close"
          >
            <X size={20} />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-6">
          {/* Step 1: QR Code */}
          <div>
            <p className="text-sm text-gray-600 mb-3">
              <span className="font-semibold text-gray-900">Step 1:</span>{' '}
              Scan this QR code with your authenticator app (Google Authenticator, Authy, etc.)
            </p>
            <div className="flex justify-center py-4 bg-gray-50 rounded-lg border border-gray-200">
              <img
                src={mfaSetup.qr_code_data_url}
                alt="MFA setup QR code"
                className="w-48 h-48"
              />
            </div>
          </div>

          {/* Manual secret */}
          <div>
            <p className="text-sm text-gray-600 mb-2">
              Or enter this secret key manually:
            </p>
            <div className="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-lg p-3">
              <code className="flex-1 font-mono text-sm text-gray-900 break-all select-all">
                {mfaSetup.secret}
              </code>
              <button
                onClick={handleCopySecret}
                className="min-h-[48px] min-w-[48px] flex items-center justify-center p-2 hover:bg-gray-200 rounded-lg transition-colors shrink-0"
                aria-label="Copy secret key"
              >
                {secretCopied ? (
                  <Check size={18} className="text-green-600" />
                ) : (
                  <Copy size={18} className="text-gray-500" />
                )}
              </button>
            </div>
          </div>

          {/* Step 2: Verify */}
          <div>
            <p className="text-sm text-gray-600 mb-3">
              <span className="font-semibold text-gray-900">Step 2:</span>{' '}
              Enter the 6-digit code from your authenticator app:
            </p>

            <div className="flex items-center justify-center gap-2" onPaste={handlePaste}>
              {code.map((digit, index) => (
                <input
                  key={index}
                  ref={(el) => {
                    inputRefs.current[index] = el;
                  }}
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  maxLength={1}
                  value={digit}
                  onChange={(e) => handleInputChange(index, e.target.value)}
                  onKeyDown={(e) => handleKeyDown(index, e)}
                  disabled={verifying}
                  className={`
                    w-12 h-14 text-center text-xl font-bold font-mono
                    border-2 rounded-lg
                    focus:ring-2 focus:ring-navy-500 focus:border-navy-500
                    disabled:bg-gray-100 disabled:cursor-not-allowed
                    transition-colors
                    ${error ? 'border-red-400' : 'border-gray-300'}
                  `}
                  aria-label={`Digit ${index + 1}`}
                />
              ))}
            </div>

            {/* Error message */}
            {error && (
              <p className="mt-3 text-sm text-red-600 text-center">{error}</p>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center gap-3 p-4 border-t border-gray-200 bg-gray-50 rounded-b-xl">
          <button
            onClick={onCancel}
            disabled={verifying}
            className="
              flex-1 px-4 py-3 min-h-[48px] bg-gray-200 hover:bg-gray-300
              text-gray-700 rounded-lg font-medium text-sm transition-colors
              disabled:opacity-50 disabled:cursor-not-allowed
            "
          >
            Cancel
          </button>
          <button
            onClick={() => handleVerify()}
            disabled={verifying || code.join('').length !== 6}
            className="
              flex-1 px-4 py-3 min-h-[48px] bg-green-600 hover:bg-green-700
              text-white rounded-lg font-medium text-sm transition-colors
              disabled:opacity-50 disabled:cursor-not-allowed
              inline-flex items-center justify-center gap-2
            "
          >
            {verifying ? (
              <>
                <Loader2 size={18} className="animate-spin" />
                Verifying...
              </>
            ) : (
              'Verify & Enable'
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
