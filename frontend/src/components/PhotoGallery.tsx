import { useState, useRef, useCallback } from 'react';
import {
  Camera, X, ChevronLeft, ChevronRight, Download,
  FileText, Image as ImageIcon, User, Clock,
} from 'lucide-react';
import type { Attachment } from '@/types/api';
import { timeAgo } from '@/utils/dateFormat';

interface Props {
  attachments: Attachment[];
  onUpload: (file: File) => void;
}

const IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'heic', 'heif', 'bmp', 'svg'];

function isImageAttachment(attachment: Attachment): boolean {
  const ext = attachment.filename.split('.').pop()?.toLowerCase() || '';
  if (IMAGE_EXTENSIONS.includes(ext)) return true;
  if (attachment.mime_type?.startsWith('image/')) return true;
  return false;
}

function getFileExtension(filename: string): string {
  return filename.split('.').pop()?.toUpperCase() || 'FILE';
}

export default function PhotoGallery({ attachments, onUpload }: Props) {
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const imageAttachments = attachments.filter(isImageAttachment);
  const allAttachments = attachments;

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files) {
      Array.from(files).forEach((file) => onUpload(file));
    }
    // Reset input so the same file can be selected again
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const openLightbox = (index: number) => {
    setLightboxIndex(index);
  };

  const closeLightbox = () => {
    setLightboxIndex(null);
  };

  const goToPrev = useCallback(() => {
    setLightboxIndex((prev) => {
      if (prev === null || prev === 0) return imageAttachments.length - 1;
      return prev - 1;
    });
  }, [imageAttachments.length]);

  const goToNext = useCallback(() => {
    setLightboxIndex((prev) => {
      if (prev === null) return 0;
      return (prev + 1) % imageAttachments.length;
    });
  }, [imageAttachments.length]);

  const handleLightboxKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') closeLightbox();
    if (e.key === 'ArrowLeft') goToPrev();
    if (e.key === 'ArrowRight') goToNext();
  };

  const currentLightboxImage = lightboxIndex !== null ? imageAttachments[lightboxIndex] : null;

  return (
    <div className="p-4">
      {/* Upload button */}
      <div className="mb-4">
        <button
          onClick={() => fileInputRef.current?.click()}
          className="
            inline-flex items-center gap-2 px-4 py-3 min-h-[48px] min-w-[48px]
            bg-navy-900 hover:bg-navy-800 text-white rounded-lg
            font-medium text-sm transition-colors
          "
        >
          <Camera size={18} />
          Upload Photo
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*,application/pdf,.doc,.docx"
          multiple
          className="hidden"
          onChange={handleFileSelect}
          capture="environment"
        />
      </div>

      {/* Image gallery grid */}
      {imageAttachments.length > 0 && (
        <div className="mb-6">
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
            Photos ({imageAttachments.length})
          </h3>
          <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-2">
            {imageAttachments.map((attachment, index) => (
              <button
                key={attachment.id}
                onClick={() => openLightbox(index)}
                className="
                  relative aspect-square rounded-lg overflow-hidden
                  bg-gray-100 hover:ring-2 hover:ring-navy-400
                  focus:ring-2 focus:ring-navy-500 focus:outline-none
                  min-h-[48px] min-w-[48px] transition-all
                "
                aria-label={`View ${attachment.filename}`}
              >
                {attachment.download_url ? (
                  <img
                    src={attachment.download_url}
                    alt={attachment.caption || attachment.filename}
                    className="w-full h-full object-cover"
                    loading="lazy"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <ImageIcon size={24} className="text-gray-400" />
                  </div>
                )}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Non-image files */}
      {allAttachments.filter((a) => !isImageAttachment(a)).length > 0 && (
        <div>
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
            Documents
          </h3>
          <div className="space-y-2">
            {allAttachments
              .filter((a) => !isImageAttachment(a))
              .map((attachment) => (
                <div
                  key={attachment.id}
                  className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg border border-gray-200"
                >
                  <div className="w-10 h-10 bg-gray-200 rounded flex items-center justify-center shrink-0">
                    <FileText size={20} className="text-gray-500" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">
                      {attachment.filename}
                    </p>
                    <div className="flex items-center gap-3 text-xs text-gray-500">
                      <span>{getFileExtension(attachment.filename)}</span>
                      {attachment.size_bytes && (
                        <span>{(attachment.size_bytes / 1024).toFixed(0)} KB</span>
                      )}
                      <span>{timeAgo(attachment.created_at)}</span>
                    </div>
                  </div>
                  {attachment.download_url && (
                    <a
                      href={attachment.download_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="min-h-[48px] min-w-[48px] flex items-center justify-center p-2 hover:bg-gray-200 rounded-lg transition-colors"
                      aria-label={`Download ${attachment.filename}`}
                    >
                      <Download size={18} className="text-gray-600" />
                    </a>
                  )}
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Empty state */}
      {allAttachments.length === 0 && (
        <div className="text-center py-12">
          <Camera size={40} className="mx-auto text-gray-300 mb-3" />
          <p className="text-sm text-gray-500 mb-1">No attachments yet</p>
          <p className="text-xs text-gray-400">
            Tap the upload button to add photos or documents.
          </p>
        </div>
      )}

      {/* Lightbox overlay */}
      {lightboxIndex !== null && currentLightboxImage && (
        <div
          className="fixed inset-0 z-50 bg-black/90 flex flex-col"
          role="dialog"
          aria-modal="true"
          aria-label="Image lightbox"
          onKeyDown={handleLightboxKeyDown}
          tabIndex={-1}
          ref={(el) => el?.focus()}
        >
          {/* Lightbox header */}
          <div className="flex items-center justify-between p-4 text-white shrink-0">
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium truncate">{currentLightboxImage.filename}</p>
              <p className="text-xs text-gray-300">
                {lightboxIndex + 1} / {imageAttachments.length}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {currentLightboxImage.download_url && (
                <a
                  href={currentLightboxImage.download_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="min-h-[48px] min-w-[48px] flex items-center justify-center p-3 hover:bg-white/10 rounded-lg transition-colors"
                  aria-label="Download image"
                >
                  <Download size={20} />
                </a>
              )}
              <button
                onClick={closeLightbox}
                className="min-h-[48px] min-w-[48px] flex items-center justify-center p-3 hover:bg-white/10 rounded-lg transition-colors"
                aria-label="Close lightbox"
              >
                <X size={24} />
              </button>
            </div>
          </div>

          {/* Image display */}
          <div className="flex-1 flex items-center justify-center relative min-h-0 px-4">
            {imageAttachments.length > 1 && (
              <button
                onClick={goToPrev}
                className="absolute left-2 z-10 min-h-[48px] min-w-[48px] flex items-center justify-center p-3 bg-black/50 hover:bg-black/70 text-white rounded-full transition-colors"
                aria-label="Previous image"
              >
                <ChevronLeft size={24} />
              </button>
            )}

            {currentLightboxImage.download_url ? (
              <img
                src={currentLightboxImage.download_url}
                alt={currentLightboxImage.caption || currentLightboxImage.filename}
                className="max-w-full max-h-full object-contain"
              />
            ) : (
              <div className="text-white text-center">
                <ImageIcon size={48} className="mx-auto mb-2 text-gray-400" />
                <p className="text-sm text-gray-400">Image not available</p>
              </div>
            )}

            {imageAttachments.length > 1 && (
              <button
                onClick={goToNext}
                className="absolute right-2 z-10 min-h-[48px] min-w-[48px] flex items-center justify-center p-3 bg-black/50 hover:bg-black/70 text-white rounded-full transition-colors"
                aria-label="Next image"
              >
                <ChevronRight size={24} />
              </button>
            )}
          </div>

          {/* Lightbox footer */}
          <div className="p-4 text-white text-center shrink-0">
            {currentLightboxImage.caption && (
              <p className="text-sm mb-1">{currentLightboxImage.caption}</p>
            )}
            <p className="text-xs text-gray-400">
              {timeAgo(currentLightboxImage.created_at)}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
