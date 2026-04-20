import React from 'react';

const DIRECTION_STYLES = {
  sent: 'bg-blue-50 text-blue-700 border-blue-200',
  received: 'bg-purple-50 text-purple-700 border-purple-200',
};

export default function ResultsList({ items, onSelect, selectedId }) {
  const count = items?.length ?? 0;
  if (!items || items.length === 0) {
    return (
      <div className="border border-dashed border-gray-200 rounded-lg min-h-[120px] flex flex-col">
        <div className="px-3 py-2 border-b border-gray-100 text-sm text-gray-600">
          0 log(s) displayed
        </div>
        <div className="text-gray-500 flex-1 flex items-center justify-center text-sm">
          No results found
        </div>
      </div>
    );
  }

  return (
    <aside className="bg-white border border-gray-200 rounded-lg overflow-hidden flex flex-col max-h-[60vh]">
      <div className="px-3 py-2 border-b border-gray-100 text-sm text-gray-600 shrink-0">
        {count.toLocaleString()} log(s) displayed
      </div>
      <div className="p-2 overflow-auto flex-1">
        {items.map((log) => {
          const isRejectedOrError = log.status === 'Rejected' || log.status === 'Error';
          const isSelected = selectedId === log.id;
          const dirLabel = (log.direction || 'sent').toLowerCase();
          const dirStyle = DIRECTION_STYLES[dirLabel] || DIRECTION_STYLES.sent;

          // Show first recipient or all if only one
          const recipientDisplay = Array.isArray(log.recipients) && log.recipients.length > 0
            ? log.recipients[0] + (log.recipients.length > 1 ? ` +${log.recipients.length - 1}` : '')
            : (log.recipient || '—');

          return (
            <div
              key={log.id}
              className={`p-2.5 rounded-md cursor-pointer border mb-2 transition-colors ${
                isSelected
                  ? 'shadow-[0_0_0_2px_rgba(11,116,255,0.12)] border-blue-200 bg-blue-50'
                  : isRejectedOrError
                    ? 'border-red-200 bg-red-50/80 hover:bg-red-100'
                    : 'border-transparent hover:bg-gray-50'
              }`}
              onClick={() => onSelect(log)}
              role="button"
              tabIndex={0}
            >
              <div className="flex justify-between gap-2 mb-1.5">
                <div className="text-sm truncate max-w-[45%]">
                  <strong>From:</strong> {log.sender || '—'}
                </div>
                <div className="text-sm truncate max-w-[45%]">
                  <strong>To:</strong> {recipientDisplay}
                </div>
              </div>
              <div className={`flex items-center gap-2 text-sm ${isRejectedOrError ? 'text-red-800' : 'text-gray-500'}`}>
                <div className="flex-1 text-xs">
                  {log.date ? new Date(log.date).toLocaleDateString() : (log.sourceFile || '')}
                </div>

                {/* Direction badge */}
                <span className={`px-2 py-0.5 rounded-full text-xs font-semibold border capitalize ${dirStyle}`}>
                  {dirLabel}
                </span>

                {/* Status badge */}
                <div
                  className={`px-2 py-1 rounded-full text-xs font-semibold ${
                    (log.status === 'Rejected' || log.status === 'Error')
                      ? 'bg-red-50 text-red-700 border border-red-200'
                      : log.status === 'Pending'
                        ? 'bg-amber-50 text-amber-800 border border-amber-200'
                        : log.status === 'Discarded'
                          ? 'bg-gray-50 text-gray-600 border border-gray-200'
                          : 'bg-green-50 text-green-700 border border-green-200'
                  }`}
                >
                  {log.status === 'Error' ? 'Rejected' : log.status}
                </div>

                {/* SMTP error code */}
                {(log.status === 'Error' || log.status === 'Rejected') && log.errorCode && (
                  <span
                    className="px-2 py-0.5 rounded text-xs font-mono bg-red-100 text-red-900 border border-red-200"
                    title="SMTP error code"
                  >
                    {log.errorCode}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </aside>
  );
}