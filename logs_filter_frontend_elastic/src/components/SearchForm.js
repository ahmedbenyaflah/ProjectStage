import React, { useState } from 'react';
import { MAX_TIME_RANGE_HOURS } from '../config';
import ClockTimePicker from './ClockTimePicker';

export default function SearchForm({ onSearch, onClear }) {
  const [sender, setSender] = useState('');
  const [recipient, setRecipient] = useState('');
  const [qid, setQid] = useState('');
  const [status, setStatus] = useState('all');
  const [minDuration, setMinDuration] = useState('');
  const [maxDuration, setMaxDuration] = useState('');
  const [date, setDate] = useState('');
  const [startTime, setStartTime] = useState('');
  const [endTime, setEndTime] = useState('');
  const [direction, setDirection] = useState('both'); // 'sent' | 'received' | 'both'
  const [error, setError] = useState('');
  const MAX_TIME_RANGE_MINUTES = MAX_TIME_RANGE_HOURS * 60;
  const parseTimeToMinutes = (t) => {
    if (!t || !t.trim()) return null;
    const withoutMs = t.trim().split('.')[0];
    const raw = withoutMs.split(':');
    const h = parseInt(raw[0], 10);
    const m = raw.length >= 2 && raw[1].trim() !== '' ? parseInt(raw[1], 10) : 0;
    const s = raw.length >= 3 && raw[2].trim() !== '' ? parseInt(raw[2], 10) : 0;
    if (Number.isNaN(h) || h < 0 || h > 23) return null;
    const mn = Number.isNaN(m) ? 0 : Math.max(0, Math.min(59, m));
    const sec = Number.isNaN(s) ? 0 : Math.max(0, Math.min(59, s));
    // We only care about minute resolution for the validation logic;
    // seconds are validated but not used in the range comparison.
    void sec;
    return h * 60 + mn;
  };
  const toHHMMSS = (t) => {
    if (!t || !t.trim()) return '';
    const withoutMs = t.trim().split('.')[0];
    const parts = withoutMs.split(':');
    const h = (parts[0] ?? '00').toString().padStart(2, '0');
    const m = (parts.length >= 2 && String(parts[1]).trim() !== '' ? parts[1] : '00').toString().padStart(2, '0');
    const s = (parts.length >= 3 && String(parts[2]).trim() !== '' ? parts[2] : '00').toString().padStart(2, '0');
    return `${h}:${m}:${s}`;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setError('');
    const hasSenderOrRecipient = sender.trim() || recipient.trim();
    const hasQid = qid.trim();
    const hasStatus = status !== 'all';
    const hasDurationRange = minDuration.trim() || maxDuration.trim();

    if (!hasSenderOrRecipient && !hasQid && !hasStatus && !hasDurationRange) {
      setError('Enter at least one filter (sender, recipient, QID, status, or duration)');
      return;
    }
    if (!date.trim()) {
      setError('Please select a date');
      return;
    }
    if (!startTime.trim()) {
      setError('Please select start time');
      return;
    }
    const startMin = parseTimeToMinutes(startTime);
    if (startMin == null) {
      setError('Invalid start time');
      return;
    }
    const endOmitted = !endTime.trim();
    const endNorm = toHHMMSS(endTime);
    const endIsMidnightStart = !endOmitted && endNorm === '00:00:00';
    let endMin = endOmitted || endIsMidnightStart ? 24 * 60 - 1 : parseTimeToMinutes(endTime);
    if (!endOmitted && !endIsMidnightStart && endMin == null) {
      setError('Invalid end time');
      return;
    }
    // If end clock is earlier than start (e.g. 23:50 → 02:00), treat end as next calendar day.
    const overnight =
      !endOmitted && !endIsMidnightStart && endMin != null && endMin < startMin;
    const endMinForSpan = overnight ? endMin + 24 * 60 : endMin;
    if (!overnight && startMin > endMinForSpan) {
      setError('Start time must be before end time (or use an earlier end clock to cross midnight)');
      return;
    }
    const diffMin = endMinForSpan - startMin;
    if (diffMin > MAX_TIME_RANGE_MINUTES) {
      setError(`Time range cannot exceed ${MAX_TIME_RANGE_HOURS} hours. Yours is ${Math.floor(diffMin / 60)}h ${diffMin % 60}m.`);
      return;
    }
    onSearch({
      sender: sender.trim(),
      recipient: recipient.trim(),
      qid: qid.trim(),
      status,
      minDuration: minDuration.trim(),
      maxDuration: maxDuration.trim(),
      date: date.trim(),
      startTime: toHHMMSS(startTime),
      endTime: endOmitted ? '' : toHHMMSS(endTime),
      direction,
    });
  };

  const handleClear = () => {
    setSender('');
    setRecipient('');
    setQid('');
    setStatus('all');
    setMinDuration('');
    setMaxDuration('');
    setDate('');
    setStartTime('');
    setEndTime('');
    setDirection('both');
    setError('');
    onClear();
  };

  const toggleDirection = (value) => {
    setDirection((prev) => (prev === value ? 'both' : value));
  };

  const inputClass = 'mt-1 h-[2.5rem] min-h-[2.5rem] px-3 rounded-xl border-2 border-gray-200 bg-white focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-orange-500 text-gray-900 text-base leading-none box-border';

  return (
    <form className="block" onSubmit={handleSubmit}>
      <div className="flex gap-3 mb-2">
        <label className="flex-1 flex flex-col text-sm text-gray-700">
          Sender
          <input 
            className={inputClass}
            value={sender} 
            onChange={(e) => setSender(e.target.value)} 
            placeholder="sender@example.com" 
          />
        </label>
        <label className="flex-1 flex flex-col text-sm text-gray-700">
          Recipient
          <input 
            className={inputClass}
            value={recipient} 
            onChange={(e) => setRecipient(e.target.value)} 
            placeholder="recipient@example.com" 
          />
        </label>
      </div>

      <div className="flex gap-3 mb-2">
        <label className="flex-1 flex flex-col text-sm text-gray-700">
          Queue ID
          <input
            className={inputClass}
            value={qid}
            onChange={(e) => setQid(e.target.value)}
            placeholder="1846344642"
          />
        </label>
        <label className="flex-1 flex flex-col text-sm text-gray-700">
          Status
          <select
            className={inputClass}
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="all">All</option>
            <option value="Success">Success</option>
            <option value="Partial Success">Partial Success</option>
            <option value="Failed">Failed</option>
            <option value="Discarded">Discarded</option>
            <option value="Pending">Pending</option>
          </select>
        </label>
      </div>

      <div className="flex gap-3 mb-2">
        <label className="flex-1 flex flex-col text-sm text-gray-700">
          Min duration (seconds)
          <input
            className={inputClass}
            type="number"
            min="0"
            step="0.001"
            value={minDuration}
            onChange={(e) => setMinDuration(e.target.value)}
            placeholder="e.g. 0"
          />
        </label>
        <label className="flex-1 flex flex-col text-sm text-gray-700">
          Max duration (seconds)
          <input
            className={inputClass}
            type="number"
            min="0"
            step="0.001"
            value={maxDuration}
            onChange={(e) => setMaxDuration(e.target.value)}
            placeholder="e.g. 3600"
          />
        </label>
      </div>

      <div className="flex gap-3 mb-2 items-end">
        <label className="flex-1 flex flex-col text-sm text-gray-700 min-w-0">
          <span className="mb-1">Date <span className="text-red-600">*</span></span>
          <input 
            type="date" 
            className={inputClass}
            value={date} 
            onChange={(e) => setDate(e.target.value)} 
          />
        </label>
        <ClockTimePicker
          label="Start time"
          value={startTime}
          onChange={setStartTime}
          id="start-time"
          required
          triggerClassName="h-[2.5rem] min-h-[2.5rem] flex-1 min-w-0 w-full"
          wrapperClassName="flex-1 min-w-0"
        />
        <ClockTimePicker
          label={`End time`}
          value={endTime}
          onChange={setEndTime}
          id="end-time"
          required={false}
          triggerClassName="h-[2.5rem] min-h-[2.5rem] flex-1 min-w-0 w-full"
          wrapperClassName="flex-1 min-w-0"
        />
      </div>
      <div className="flex items-center gap-3 mb-2">
        <div className="text-sm text-gray-700 mr-2">Direction</div>
        <label className="inline-flex gap-1.5 items-center">
          <input 
            type="checkbox" 
            checked={direction === 'sent'} 
            onChange={() => toggleDirection('sent')} 
            className="cursor-pointer"
          /> 
          Sent
        </label>
        <label className="inline-flex gap-1.5 items-center">
          <input 
            type="checkbox" 
            checked={direction === 'received'} 
            onChange={() => toggleDirection('received')} 
            className="cursor-pointer"
          /> 
          Received
        </label>
      </div>

      {error && <div className="text-red-700 text-sm mt-1.5">{error}</div>}

      <div className="flex gap-2 mt-2">
        <button type="submit" className="px-3 py-2 rounded-lg border border-orange-600 bg-orange-600 text-white cursor-pointer hover:bg-orange-700">
          Search
        </button>
        <button type="button" className="px-3 py-2 rounded-lg border border-gray-300 bg-white cursor-pointer hover:bg-gray-50" onClick={handleClear}>
          Clear
        </button>
      </div>
    </form>
  );
}

