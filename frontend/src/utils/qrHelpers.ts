export function buildScanUrl(entityType: string, token: string): string {
  const base = window.location.origin;
  return `${base}/scan/${entityType}/${token}`;
}

export function downloadQrImage(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
