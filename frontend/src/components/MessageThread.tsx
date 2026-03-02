import { useState, useRef, useEffect } from 'react';
import { Send } from 'lucide-react';
import type { Message } from '@/types/api';
import { formatDateTime, timeAgo } from '@/utils/dateFormat';

interface Props {
  messages: Message[];
  currentUserId: string;
  onSendMessage: (content: string) => void;
}

export default function MessageThread({ messages, currentUserId, onSendMessage }: Props) {
  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to the bottom when new messages arrive
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages.length]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = inputValue.trim();
    if (!trimmed) return;
    onSendMessage(trimmed);
    setInputValue('');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Submit on Enter (without Shift)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Messages list */}
      <div ref={scrollContainerRef} className="flex-1 overflow-auto p-4 space-y-3">
        {messages.length === 0 && (
          <div className="text-center py-12">
            <p className="text-sm text-gray-500">No messages yet</p>
            <p className="text-xs text-gray-400 mt-1">
              Start a conversation about this work order.
            </p>
          </div>
        )}

        {messages.map((message) => {
          const isOwn = message.user_id === currentUserId;
          return (
            <div
              key={message.id}
              className={`flex ${isOwn ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`
                  max-w-[80%] sm:max-w-[70%] rounded-2xl px-4 py-3
                  ${
                    isOwn
                      ? 'bg-blue-600 text-white rounded-br-md'
                      : 'bg-gray-200 text-gray-900 rounded-bl-md'
                  }
                `}
              >
                {/* Sender name (only for others) */}
                {!isOwn && (
                  <p className="text-xs font-semibold text-gray-600 mb-1">
                    {message.sender_name}
                  </p>
                )}

                {/* Message body */}
                <p className="text-sm whitespace-pre-wrap break-words">
                  {message.content}
                </p>

                {/* Timestamp */}
                <p
                  className={`text-xs mt-1.5 ${
                    isOwn ? 'text-blue-200' : 'text-gray-500'
                  }`}
                  title={formatDateTime(message.created_at)}
                >
                  {timeAgo(message.created_at)}
                </p>
              </div>
            </div>
          );
        })}

        <div ref={messagesEndRef} />
      </div>

      {/* Input bar */}
      <form
        onSubmit={handleSubmit}
        className="border-t border-gray-200 bg-white p-3 flex items-end gap-2 shrink-0"
      >
        <textarea
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type a message..."
          rows={1}
          className="
            flex-1 px-4 py-3 min-h-[48px] max-h-[120px]
            border border-gray-300 rounded-xl text-sm
            resize-none focus:ring-2 focus:ring-navy-500 focus:border-navy-500
          "
          aria-label="Message input"
        />
        <button
          type="submit"
          disabled={!inputValue.trim()}
          className="
            min-h-[48px] min-w-[48px] flex items-center justify-center
            bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed
            text-white rounded-xl transition-colors
          "
          aria-label="Send message"
        >
          <Send size={20} />
        </button>
      </form>
    </div>
  );
}
