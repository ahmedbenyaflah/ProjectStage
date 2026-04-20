import React, { useState } from 'react';
import { getErrorExplanation } from '../data/errorCodes';

function parseRejectionDetails(log) {
  if (!log) return {};

  const message =
    log.errorMessage ||
    log.error_details?.full_message ||   // sent_parser
    log.error_details?.message ||         // reception_parser
    log.rawDocument?.error_details?.full_message ||
    log.rawDocument?.error_details?.message ||
    '';

  let derivedErrorCode =
    log.errorCode ||
    log.error_details?.code ||
    log.rawDocument?.error_details?.code ||
    null;

  if (!derivedErrorCode && message) {
    const codeMatch = message.match(/\b([45]\d{2})\b/);
    if (codeMatch && codeMatch[1]) {
      derivedErrorCode = codeMatch[1];
    }
  }

  let supportUrl = null;
  if (message) {
    const urlMatch = message.match(/https?:\/\/\S+/);
    if (urlMatch && urlMatch[0]) {
      supportUrl = urlMatch[0];
    }
  }

  const cleanMessage = supportUrl ? message.replace(supportUrl, '').trim() : message;
  return { errorCode: derivedErrorCode, supportUrl, cleanMessage };
}

export default function DetailsPanel({ log }) {
  const [showAuditModal, setShowAuditModal] = useState(false);

  if (!log) {
    return (
      <section className="bg-white border border-gray-200 p-3 rounded-lg min-h-[120px] flex items-center justify-center text-gray-500">
        <div>Select a log to view details</div>
      </section>
    );
  }

  const isRejected = log.status === 'Rejected' || log.status === 'Failed' || log.status === 'Error';
  const isReceived = (log.direction || '').toLowerCase() === 'received';

  const {
    supportUrl: rejectionSupportUrl,
    cleanMessage: rejectionMessage,
    errorCode: parsedCode,
  } = isRejected ? parseRejectionDetails(log) : {};

  const effectiveErrorCode = log.errorCode || log.rawDocument?.error_details?.code || parsedCode;
  const errorExplanation =
    isRejected && effectiveErrorCode ? getErrorExplanation(effectiveErrorCode) : null;

  const queueId = log.queueId || log.queue_id || log.id;

  // Audit lines — backend normalises mx_lines → fes_lines for received mails
  const auditFesLines = log.auditFesLines || [];
  const auditMappedLines = log.auditMappedLines || [];

  const baseErrorMessage = rejectionMessage || log.errorMessage || '';
  const isLongErrorMessage = baseErrorMessage && baseErrorMessage.length > 160;

  // All recipients (both parsers store them as arrays)
  const allRecipients = log.recipients || (log.recipient ? [log.recipient] : []);

  return (
    <section className="bg-white border border-gray-200 p-3 rounded-lg min-h-[120px]">
      <h2 className="text-lg font-semibold mb-4 border-b pb-2 flex items-center gap-2">
        Log Details
        {/* Direction badge */}
        <span
          className={`text-xs px-2 py-0.5 rounded-full font-semibold border capitalize ${
            isReceived
              ? 'bg-purple-50 text-purple-700 border-purple-200'
              : 'bg-blue-50 text-blue-700 border-blue-200'
          }`}
        >
          {log.direction || 'sent'}
        </span>
      </h2>

      <div className="space-y-2 mb-4">
        <div className="text-sm"><strong>From:</strong> {log.sender || '—'}</div>

        {/* All recipients */}
        <div className="text-sm">
          <strong>To:</strong>{' '}
          {allRecipients.length === 0 && '—'}
          {allRecipients.length === 1 && allRecipients[0]}
          {allRecipients.length > 1 && (
            <ul className="mt-0.5 ml-3 list-disc list-inside space-y-0.5">
              {allRecipients.map((r) => (
                <li key={r} className="font-mono text-xs text-gray-700">{r}</li>
              ))}
            </ul>
          )}
        </div>

        <div className="text-sm"><strong>Date:</strong> {log.date || '—'}</div>
        <div className="text-sm">
          <strong>Queue ID:</strong>{' '}
          <span className="font-mono ml-1">{queueId}</span>
        </div>
        {log.delivery_id && (
          <div className="text-sm">
            <strong>Delivery ID:</strong>{' '}
            <span className="font-mono ml-1">{log.delivery_id}</span>
          </div>
        )}
        {log.server && (
          <div className="text-sm">
            <strong>Relay IP:</strong>{' '}
            <span className="font-mono ml-1">{log.server}</span>
          </div>
        )}
        {log.serverPath && log.serverPath.length > 0 && (
          <div className="text-sm">
            <strong>Server path:</strong>{' '}
            <span className="font-mono ml-1 text-xs">{log.serverPath.join(' → ')}</span>
          </div>
        )}
      </div>

      {/* KASPERSKY ANALYSIS */}
      <div className="py-3 border-t border-gray-100 mb-3">
        <h3 className="text-xs font-bold uppercase text-gray-400 mb-2">Kaspersky Analysis</h3>
        <div className="grid grid-cols-2 gap-2">
          <div className="bg-gray-50 p-2 rounded border border-gray-100">
            <div className="text-[10px] text-gray-500 uppercase font-bold">Spam Status</div>
            <div
              className={`text-xs font-mono font-bold ${
                log.kasperskySpam === 'KAS_STATUS_SPAM' ? 'text-red-600' : 'text-green-600'
              }`}
            >
              {log.kasperskySpam || 'KAS_STATUS_NOT_SPAM'}
            </div>
          </div>
          <div className="bg-gray-50 p-2 rounded border border-gray-100">
            <div className="text-[10px] text-gray-500 uppercase font-bold">Virus Status</div>
            <div
              className={`text-xs font-mono font-bold ${
                (log.kasperskyVirus || 'CLEAN') !== 'CLEAN' ? 'text-red-600' : 'text-green-600'
              }`}
            >
              {log.kasperskyVirus || 'CLEAN'}
            </div>
          </div>
        </div>

        <div className="mt-2 text-[10px] text-gray-400 font-mono">
          <strong>KAS level (X count):</strong>{' '}
          <span className="text-gray-700">{log.kasperskyLevel ?? 0}</span>
        </div>

        {/* Reception-only extras */}
        {isReceived && (
          <div className="mt-2 grid grid-cols-2 gap-2">
            {log.kasMethod && (
              <div className="bg-gray-50 p-2 rounded border border-gray-100">
                <div className="text-[10px] text-gray-500 uppercase font-bold">KAS Method</div>
                <div className="text-xs font-mono text-gray-700 break-all">{log.kasMethod}</div>
              </div>
            )}
            {log.kavStatus && (
              <div className="bg-gray-50 p-2 rounded border border-gray-100">
                <div className="text-[10px] text-gray-500 uppercase font-bold">KAV Status</div>
                <div
                  className={`text-xs font-mono font-bold ${
                    log.kavStatus === 'DETECT' ? 'text-red-600' : 'text-green-600'
                  }`}
                >
                  {log.kavStatus}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* TIMING */}
      <div className="space-y-2 py-3 border-t border-b border-gray-50 mb-3">
        <div className="text-sm">
          <strong>Time:</strong> {log.startTime || '—'} – {log.endTime || '—'}
        </div>
        {log.durationSeconds > 0 && (
          <div className="text-sm text-orange-700">
            <strong>Delay:</strong> {log.durationSeconds} seconds
          </div>
        )}
        {log.auditMetrics && (
          <div className="text-xs text-gray-500 font-mono">
            Audit lines (indexed): edge {log.auditMetrics.edge_line_count ?? '—'}
            {log.auditMetrics.downstream_line_count != null &&
              log.auditMetrics.downstream_line_count > 0 &&
              ` · downstream ${log.auditMetrics.downstream_line_count}`}
            {(() => {
              const m = log.auditMetrics;
              const edgeTrunc =
                (m.edge_line_count ?? 0) > (m.edge_lines_stored ?? 0);
              const downTrunc =
                (m.downstream_line_count ?? 0) > (m.downstream_lines_stored ?? 0);
              return edgeTrunc || downTrunc ? (
                <span className="text-amber-600"> · trail truncated for storage</span>
              ) : null;
            })()}
          </div>
        )}
      </div>

      {/* REJECTION INFO */}
      {isRejected && (
        <div className="bg-red-50 border border-red-200 p-3 rounded-md space-y-2 mb-4">
          <div className="flex items-center gap-2">
            {!isLongErrorMessage && (
              <strong className="text-sm text-red-800">
                {baseErrorMessage || 'Unknown transmission error'}
              </strong>
            )}
            {effectiveErrorCode && (
              <span className="text-xs bg-red-100 text-red-700 px-1.5 py-0.5 rounded font-mono font-bold">
                {effectiveErrorCode}
              </span>
            )}
          </div>
          {isLongErrorMessage && (
            <p className="text-xs text-red-800 break-words">{baseErrorMessage}</p>
          )}
          {rejectionSupportUrl && (
            <a
              href={rejectionSupportUrl}
              target="_blank"
              rel="noreferrer"
              className="text-xs text-blue-700 underline block font-medium"
            >
              View Technical Solution
            </a>
          )}
          {errorExplanation && (
            <div className="pt-2 border-t border-red-200 text-xs text-red-800">
              <p><strong>Cause:</strong> {errorExplanation.meaning}</p>
              <p className="mt-1"><strong>Recommendation:</strong> {errorExplanation.action}</p>
            </div>
          )}
        </div>
      )}

      <div className="flex flex-col gap-2">
        <button
          onClick={() => setShowAuditModal(true)}
          className="w-full py-3 text-sm font-bold border border-orange-200 rounded-lg bg-orange-50 text-orange-700 hover:bg-orange-100 transition shadow-sm"
        >
          🔍 View Expanded Audit Trail
        </button>

        <details className="text-xs group mt-2">
          <summary className="cursor-pointer text-gray-400 hover:text-gray-600 list-none flex items-center justify-center gap-1">
            Technical Metadata (JSON)
          </summary>
          <pre className="mt-2 p-2 bg-gray-900 text-green-400 rounded max-h-48 overflow-auto font-mono text-[10px]">
            {JSON.stringify(log.rawDocument || log, null, 2)}
          </pre>
        </details>
      </div>

      {/* AUDIT MODAL */}
      {showAuditModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/85 p-4 backdrop-blur-md">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-7xl h-[92vh] flex flex-col overflow-hidden">
            <div className="p-6 border-b flex justify-between items-center bg-gray-50">
              <div>
                <h3 className="text-2xl font-black text-gray-900 tracking-tight uppercase flex items-center gap-3">
                  Audit Journey
                  <span
                    className={`text-sm px-3 py-1 rounded-full font-semibold border capitalize ${
                      isReceived
                        ? 'bg-purple-50 text-purple-700 border-purple-200'
                        : 'bg-blue-50 text-blue-700 border-blue-200'
                    }`}
                  >
                    {log.direction || 'sent'}
                  </span>
                </h3>
                <p className="text-sm text-orange-600 font-mono font-bold mt-1">ID: {queueId}</p>
              </div>
              <button
                onClick={() => setShowAuditModal(false)}
                className="px-8 py-2 bg-gray-900 text-white rounded-lg hover:bg-black font-bold transition shadow-lg"
              >
                CLOSE
              </button>
            </div>

            <div className="flex-1 overflow-auto p-6 space-y-6 bg-slate-50">
              {/* For sent mail this is FES lines; for received mail this is MX lines (normalised) */}
              {auditFesLines.length > 0 && (
                <div className="bg-white border border-orange-200 rounded-xl overflow-hidden shadow-sm">
                  <div className="bg-orange-600 px-5 py-2 text-white font-bold text-xs uppercase tracking-widest">
                    {isReceived ? 'Reception Server (MX)' : 'Front-End Server (FES)'}
                  </div>
                  <div className="p-4 bg-white overflow-x-auto">
                    <pre className="font-mono text-[12px] text-gray-800 leading-relaxed min-w-max">
                      {auditFesLines.join('\n')}
                    </pre>
                  </div>
                </div>
              )}

              {/* Downstream / mapped lines (sent mails only; absent for received) */}
              {auditMappedLines.length > 0 && (
                <div className="bg-white border border-blue-200 rounded-xl overflow-hidden shadow-sm">
                  <div className="bg-blue-600 px-5 py-2 text-white font-bold text-xs uppercase tracking-widest">
                    Internal Mapped Servers
                  </div>
                  <div className="p-4 bg-white overflow-x-auto">
                    <pre className="font-mono text-[12px] text-gray-800 leading-relaxed min-w-max">
                      {auditMappedLines.join('\n')}
                    </pre>
                  </div>
                </div>
              )}

              {auditFesLines.length === 0 && auditMappedLines.length === 0 && (
                <div className="text-gray-400 text-sm text-center py-10">
                  No audit lines available for this log entry.
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}