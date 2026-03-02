import { Copy, Check } from 'lucide-react';
import { useState } from 'react';

interface Props {
  number: string;
  size?: 'sm' | 'md' | 'lg';
  copyable?: boolean;
}

export default function HumanReadableNumber({ number, size = 'md', copyable = true }: Props) {
  const [copied, setCopied] = useState(false);
  const sizeClass = size === 'lg' ? 'text-xl font-bold' : size === 'md' ? 'text-base font-semibold' : 'text-sm font-medium';

  const handleCopy = async () => {
    await navigator.clipboard.writeText(number);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <span className={`inline-flex items-center gap-1.5 font-mono ${sizeClass} text-navy-900`}>
      {number}
      {copyable && (
        <button onClick={handleCopy} className="p-1 hover:bg-gray-100 rounded" title="Copy WO number">
          {copied ? <Check size={14} className="text-green-600" /> : <Copy size={14} className="text-gray-400" />}
        </button>
      )}
    </span>
  );
}
