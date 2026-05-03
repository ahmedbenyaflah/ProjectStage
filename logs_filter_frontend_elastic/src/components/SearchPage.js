import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import SearchForm from './SearchForm';
import ResultsList from './ResultsList';
import DetailsPanel from './DetailsPanel';
import Navbar from './Navbar';
import { useAuth } from '../context/AuthContext';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

/** Display time-of-day from ES `date` field (local `yyyy-MM-dd HH:mm:ss.SSS` or ISO). */
function journeyTimeOfDay(ts) {
  if (ts == null || ts === '') return '';
  const s = String(ts);
  const sp = s.indexOf(' ');
  if (sp > 0) {
    const rest = s.slice(sp + 1).trim();
    const dot = rest.indexOf('.');
    if (dot > 0) return rest.slice(0, dot + 4);
    return rest;
  }
  if (s.includes('T')) {
    const rest = (s.split('T')[1] || '').replace(/Z$/i, '');
    const dot = rest.indexOf('.');
    if (dot > 0) return rest.slice(0, dot + 4);
    return rest.slice(0, 8);
  }
  return s;
}

function normalizeDate(dateStr) {
  if (!dateStr || !dateStr.trim()) return '';
  const s = dateStr.trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;
  const m = s.match(/^(\d{1,2})[/-](\d{1,2})(?:[/-](\d{4}))?$/);
  if (m) {
    const [, d, mon, y] = m;
    const year = y || '2026';
    return `${year}-${String(parseInt(mon, 10)).padStart(2, '0')}-${String(parseInt(d, 10)).padStart(2, '0')}`;
  }
  return s;
}

/** KAS threat level as integer (count of X); supports legacy string or kas_level_score. */
function normalizeKasperskyLevelXCount(item) {
  const k = item.kaspersky_level;
  if (typeof k === 'number' && !Number.isNaN(k)) return Math.max(0, Math.floor(k));
  if (typeof k === 'string' && k.trim()) return (k.match(/X/g) || []).length;
  const ks = item.kas_level_score;
  if (typeof ks === 'number' && !Number.isNaN(ks)) return Math.max(0, Math.floor(ks));
  return 0;
}

/**
 * Normalise a raw ES document from either parser into a consistent shape
 * for ResultsList and DetailsPanel.
 *
 * sent_parser fields      → direction:"sent",  audit.fes_lines, audit.mapped_lines,
 *                           kaspersky_level,   error_details.full_message
 * reception_parser fields → direction:"received", audit.fes_lines (MX trail, same key as sent),
 *                           kaspersky_level (integer: count of X in KAS level),
 *                           kas_method, kav_status,
 *                           error_details.message / error_details.full_error_line
 */
function mapItem(item, idx, currentPage, dateNorm) {
  const qidValue = item.qid || item.queue_id || '';

  // --- Status ---
  let displayStatus = 'Pending';
  const s = (item.status || '').toLowerCase();
  if (s === 'success') displayStatus = 'Success';
  else if (s === 'failed') displayStatus = 'Rejected';
  else if (s === 'discarded') displayStatus = 'Discarded';

  // --- Direction ---
  // Backend always sets "direction" in the document ("sent" | "received").
  const direction = item.direction || 'sent';

  // --- Audit lines ---
  // Backend normalises mx_lines → fes_lines for received mails.
  const fesLines = item.audit?.fes_lines || [];
  const mappedLines = item.audit?.mapped_lines || [];

  // Infer error line from audit for display
  const inferredErrorLine = Array.isArray(fesLines)
    ? (fesLines.find((l) => typeof l === 'string' && /\b(failed:|rejected)\b/i.test(l)) || '')
    : '';

  // --- Error details ---
  // sent_parser  → error_details: { code, full_message }
  // reception_parser → error_details: { code, message, full_error_line }
  const ed = item.error_details || null;
  const errorCode = ed?.code || '';
  const errorMessage =
    ed?.full_message ||    // sent_parser
    ed?.message ||          // reception_parser
    '';
  const errorFullLine =
    ed?.full_message ||
    ed?.full_error_line ||
    inferredErrorLine ||
    '';

  // --- Kaspersky ---
  const kasperskyLevel = normalizeKasperskyLevelXCount(item);

  return {
    id: qidValue || `idx-${currentPage}-${idx}`,
    sender: item.sender || '',
    recipient: Array.isArray(item.recipients)
      ? item.recipients[0]
      : (item.recipient || ''),
    recipients: item.recipients || [],
    direction,
    date: item.date || dateNorm,
    status: displayStatus,
    delayMinutes: item.duration_seconds ? Math.round(item.duration_seconds / 60) : 0,
    serverPath: item.serverPath || [],
    queue_id: qidValue,
    delivery_id: item.deliveryId || '',

    // Audit
    auditFesLines: fesLines,
    auditMappedLines: mappedLines,

    // Timing
    durationSeconds: item.duration_seconds || 0,
    server: item.relayIp || '',
    startTime: journeyTimeOfDay(item.start_time),
    endTime: journeyTimeOfDay(item.end_time),
    spansCalendarDays: Boolean(item.spans_calendar_days),
    journeyEndCalendarDate: item.journey_end_calendar_date || '',
    auditMetrics: item.audit_metrics || null,

    // Kaspersky
    kasperskySpam: item.kaspersky_spam_status || 'KAS_STATUS_NOT_SPAM',
    kasperskyVirus: item.kaspersky_virus_status || 'CLEAN',
    kasperskyLevel,
    // Reception-only extras (harmless if absent for sent mails)
    kasMethod: item.kas_method || '',
    kavStatus: item.kav_status || '',

    // Error / rejection
    error_details: ed,
    errorCode,
    errorMessage,
    errorLine: errorFullLine,

    rawDocument: item,
  };
}

export default function SearchPage() {
  const [results, setResults] = useState([]);
  const [selectedLog, setSelectedLog] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [total, setTotal] = useState(0);
  const [lastFilters, setLastFilters] = useState(null);
  const { logout, token } = useAuth();
  const navigate = useNavigate();

  const runSearch = useCallback(async (filters, pageOverride) => {
    const currentPage = pageOverride || 1;
    setLoading(true);
    setError(null);
    setSelectedLog(null);

    const dateNorm = normalizeDate(filters.date);
    if (!dateNorm) {
      setError('Please select a valid date');
      setLoading(false);
      return;
    }

    try {
      const params = new URLSearchParams();
      params.append('date', dateNorm);
      if (filters.sender?.trim()) params.append('sender', filters.sender.trim());
      if (filters.recipient?.trim()) params.append('recipient', filters.recipient.trim());
      if (filters.qid?.trim()) params.append('qid', filters.qid.trim());

      if (filters.status && filters.status !== 'all') {
        params.append('status', filters.status);
      }

      // direction: 'sent' | 'received' | 'both' (omit for both)
      if (filters.direction && filters.direction !== 'both') {
        params.append('direction', filters.direction);
      }

      if (filters.minDuration?.trim()) params.append('min_duration', filters.minDuration.trim());
      if (filters.maxDuration?.trim()) params.append('max_duration', filters.maxDuration.trim());

      if (filters.startTime?.trim()) params.append('start_time', filters.startTime.trim());
      if (filters.endTime?.trim()) params.append('end_time', filters.endTime.trim());

      params.append('page', String(currentPage));
      params.append('size', String(pageSize));

      const res = await fetch(`${API_BASE}/api/search?${params.toString()}`, {
        method: 'GET',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });

      if (res.status === 401) {
        logout();
        navigate('/login');
        return;
      }

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Search failed');

      const mapped = (data.results || []).map((item, idx) =>
        mapItem(item, idx, currentPage, dateNorm)
      );

      setResults(mapped);
      setTotal(data.total || 0);
      setPage(currentPage);
      setLastFilters(filters);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [token, pageSize, logout, navigate]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="min-h-screen bg-gradient-to-b from-orange-50/50 to-white w-full">
      <Navbar />
      <div className="p-4 max-w-[1600px] mx-auto">
        <section className="bg-white border border-orange-100 p-6 rounded-xl shadow-sm mb-6">
          <SearchForm onSearch={(f) => runSearch(f, 1)} onClear={() => setResults([])} />
          {loading && (
            <div className="mt-4 text-orange-600 font-medium animate-pulse">Searching logs...</div>
          )}
          {error && (
            <div className="mt-4 p-3 bg-red-50 border border-red-100 text-red-600 text-sm rounded-lg">
              {error}
            </div>
          )}
        </section>
        <main className="grid grid-cols-1 lg:grid-cols-[1fr_400px] gap-6">
          <div className="flex flex-col">
            <div className="flex justify-between items-center mb-4 px-1">
              <span className="text-sm text-gray-500">
                Found <b>{total.toLocaleString()}</b> results | Page {page} of {totalPages}
              </span>
              {total > pageSize && (
                <div className="flex gap-2">
                  <button
                    disabled={page <= 1 || loading}
                    onClick={() => runSearch(lastFilters, page - 1)}
                    className="px-4 py-1.5 border border-gray-200 bg-white rounded-lg text-sm disabled:opacity-40"
                  >
                    Previous
                  </button>
                  <button
                    disabled={page >= totalPages || loading}
                    onClick={() => runSearch(lastFilters, page + 1)}
                    className="px-4 py-1.5 border border-gray-200 bg-white rounded-lg text-sm disabled:opacity-40"
                  >
                    Next
                  </button>
                </div>
              )}
            </div>
            <ResultsList items={results} onSelect={setSelectedLog} selectedId={selectedLog?.id} />
          </div>
          <DetailsPanel log={selectedLog} />
        </main>
      </div>
    </div>
  );
}