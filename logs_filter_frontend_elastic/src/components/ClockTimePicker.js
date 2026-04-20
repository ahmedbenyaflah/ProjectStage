import React, { useState, useRef, useEffect } from 'react';

const SIZE = 200;
const CENTER = SIZE / 2;
const HOUR_RADIUS = 72;
const MINUTE_RADIUS = 72;

/** angle in degrees: 0 = top, 90 = right */
function position(angleDeg, radius) {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return {
    x: CENTER + radius * Math.cos(rad),
    y: CENTER + radius * Math.sin(rad),
  };
}

export default function ClockTimePicker({ value = '', onChange, label = 'Time', id, required, triggerClassName = '', wrapperClassName = '' }) {
  const [open, setOpen] = useState(false);
  const [hour, setHour] = useState(() => {
    if (!value) return null;
    const parts = value.trim().split(':');
    const h = parseInt(parts[0], 10);
    return Number.isNaN(h) ? null : h % 24;
  });
  const [minute, setMinute] = useState(() => {
    if (!value) return null;
    const parts = value.trim().split(':');
    if (parts.length < 2 || String(parts[1]).trim() === '') return 0;
    const m = parseInt(parts[1], 10);
    return Number.isNaN(m) ? 0 : Math.min(59, Math.floor(m / 5) * 5);
  });
  const [mode, setMode] = useState(hour != null ? 'minute' : 'hour');
  const [isEditing, setIsEditing] = useState(false);
  const containerRef = useRef(null);

  useEffect(() => {
    if (value) {
      const parts = value.trim().split(':');
      const h = parseInt(parts[0], 10);
      const m = (parts.length >= 2 && String(parts[1]).trim() !== '') ? parseInt(parts[1].split('.')[0], 10) : 0;
      if (!Number.isNaN(h)) setHour(h % 24);
      setMinute(Number.isNaN(m) ? 0 : Math.min(59, Math.floor(m / 5) * 5));
      if (!isEditing && (parts.length > 2 || value.includes('.'))) {
        setInputValue(value);
      }
    } else {
      setHour(null);
      setMinute(null);
      setMode('hour');
    }
  }, [value, isEditing]);

  useEffect(() => {
    if (!open) return;
    const onDocClick = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, [open]);

  const commit = (h, m, s = null, ms = null) => {
    const hh = (h ?? hour ?? 0);
    const mm = (m ?? minute ?? 0);
    let str = `${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}`;
    if (s !== null || ms !== null) {
      const ss = s !== null ? s : 0;
      str += `:${String(ss).padStart(2, '0')}`;
      if (ms !== null && ms !== '') {
        str += `.${String(ms).padEnd(3, '0').substring(0, 3)}`;
      }
    }
    onChange(str);
  };

  const handleHourClick = (h) => {
    setHour(h);
    const m = minute ?? 0;
    setMinute(m);
    commit(h, m);
    setMode('minute');
  };

  const handleMinuteClick = (m) => {
    setMinute(m);
    commit(hour, m);
    setOpen(false);
  };

  const displayStr = value && value.includes(':') && (value.split(':').length > 2 || value.includes('.'))
    ? value
    : (hour != null && minute != null
      ? `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`
      : '--:--');

  const hours = Array.from({ length: 24 }, (_, i) => i);
  const minutes = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55];

  const [inputValue, setInputValue] = useState(() => {
    if (value && value.trim() !== '') {
      return value;
    }
    const h = hour != null ? hour : null;
    const m = minute != null ? minute : null;
    return h != null && m != null
      ? `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
      : '--:--';
  });

  useEffect(() => {
    if (!isEditing) {
      if (value && value.includes(':') && (value.split(':').length > 2 || value.includes('.'))) {
        setInputValue(value);
      } else if (value && value.trim() !== '') {
        setInputValue(value);
      } else {
        setInputValue(displayStr);
      }
    }
  }, [displayStr, isEditing, value]);

  const handleInputChange = (e) => {
    const val = e.target.value;
    setInputValue(val);
    if (!isEditing) {
      setIsEditing(true);
    }
  };

  const validateAndCommit = (val) => {
    const timeMatch = val.match(/^(\d{1,2})(?::(\d{1,2}))?(?::(\d{1,2}))?(?:\.(\d{1,3}))?$/);
    if (timeMatch) {
      const h = parseInt(timeMatch[1], 10);
      const m = timeMatch[2] ? parseInt(timeMatch[2], 10) : 0;
      const s = timeMatch[3] !== undefined ? parseInt(timeMatch[3], 10) : null;
      const ms = timeMatch[4] !== undefined ? timeMatch[4] : null;

      if (Number.isNaN(h) || h < 0 || h >= 24) {
        setInputValue(displayStr);
        return false;
      }
      if (Number.isNaN(m) || m < 0 || m >= 60) {
        setInputValue(displayStr);
        return false;
      }
      if (s !== null && (Number.isNaN(s) || s < 0 || s >= 60)) {
        setInputValue(displayStr);
        return false;
      }

      let formatted = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
      if (s !== null || ms !== null) {
        const ss = s !== null ? s : 0;
        formatted += `:${String(ss).padStart(2, '0')}`;
        if (ms !== null && ms !== '') {
          formatted += `.${ms.padEnd(3, '0').substring(0, 3)}`;
        }
      }

      setInputValue(formatted);
      setHour(h);
      setMinute(m);
      commit(h, m, s, ms);
      return true;
    }
    setInputValue(displayStr);
    return false;
  };

  const handleInputBlur = () => {
    validateAndCommit(inputValue);
    setIsEditing(false);
  };

  const handleInputKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      if (validateAndCommit(inputValue)) {
        e.target.blur();
      }
    } else if (e.key === 'Escape') {
      setInputValue(displayStr);
      e.target.blur();
    }
  };

  const handleInputFocus = () => {
    setIsEditing(true);
  };

  return (
    <div className={`relative ${wrapperClassName || 'inline-block'}`.trim()} ref={containerRef}>
      <label className="flex flex-col text-sm text-gray-700 w-full min-w-0">
        <span className="mb-1">{label}{required && <span className="text-red-600"> *</span>}</span>
        <div className="flex items-center gap-1.5">
          <input
            type="text"
            id={id}
            value={inputValue}
            onChange={handleInputChange}
            onBlur={handleInputBlur}
            onFocus={handleInputFocus}
            onKeyDown={handleInputKeyDown}
            placeholder="HH:MM:SS.mmm"
            className={`flex-1 px-3 rounded-xl border-2 border-gray-200 bg-white focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-orange-500 text-gray-900 text-base font-semibold tabular-nums text-center ${triggerClassName}`}
            style={{ minHeight: '2.5rem' }}
          />
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            className="flex items-center justify-center px-2 rounded-xl border-2 border-gray-200 bg-white hover:border-orange-400 hover:bg-orange-50/50 transition-colors focus:outline-none focus:ring-2 focus:ring-orange-500 focus:ring-offset-1"
            style={{ minHeight: '2.5rem', minWidth: '2.5rem' }}
            title="Open clock picker"
          >
            <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </button>
        </div>
      </label>

      {open && (
      <div className="absolute left-0 top-full mt-2 z-20 p-4 rounded-2xl bg-white border border-gray-200 shadow-xl shadow-gray-200/50">
        <div className="flex flex-col items-center">
          <div className="flex gap-1 mb-3">
            <button
              type="button"
              onClick={() => setMode('hour')}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${mode === 'hour' ? 'bg-orange-500 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
            >
              Hour
            </button>
            <button
              type="button"
              onClick={() => setMode('minute')}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${mode === 'minute' ? 'bg-orange-500 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
            >
              Minute
            </button>
          </div>

          <svg width={SIZE} height={SIZE} className="select-none" viewBox={`0 0 ${SIZE} ${SIZE}`}>
            <circle cx={CENTER} cy={CENTER} r={HOUR_RADIUS + 16} fill="#fafafa" stroke="#e5e7eb" strokeWidth="1" />
            <circle cx={CENTER} cy={CENTER} r={HOUR_RADIUS + 8} fill="white" stroke="#e5e7eb" strokeWidth="1" />

            {mode === 'hour' && hours.map((h) => {
              const { x, y } = position((h / 24) * 360, HOUR_RADIUS);
              const active = hour === h;
              return (
                <g key={h} onClick={() => handleHourClick(h)} className="cursor-pointer">
                  <circle
                    cx={x}
                    cy={y}
                    r={active ? 14 : 10}
                    fill={active ? '#FF7900' : 'white'}
                    stroke={active ? '#FF7900' : '#d1d5db'}
                    strokeWidth={active ? 2 : 1.5}
                  />
                  <text
                    x={x}
                    y={y + 1}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    className="text-[11px] font-semibold select-none fill-gray-700"
                    fill={active ? 'white' : '#374151'}
                  >
                    {h}
                  </text>
                </g>
              );
            })}

            {mode === 'minute' && minutes.map((m, i) => {
              const angle = (i / 12) * 360;
              const { x, y } = position(angle, MINUTE_RADIUS);
              const active = minute === m;
              return (
                <g key={m} onClick={() => handleMinuteClick(m)} className="cursor-pointer">
                  <circle
                    cx={x}
                    cy={y}
                    r={active ? 14 : 10}
                    fill={active ? '#FF7900' : 'white'}
                    stroke={active ? '#FF7900' : '#d1d5db'}
                    strokeWidth={active ? 2 : 1.5}
                  />
                  <text
                    x={x}
                    y={y + 1}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    className="text-[11px] font-semibold select-none fill-gray-700"
                    fill={active ? 'white' : '#374151'}
                  >
                    {String(m).padStart(2, '0')}
                  </text>
                </g>
              );
            })}

            <circle cx={CENTER} cy={CENTER} r={4} fill="#e5e7eb" />
          </svg>
        </div>
      </div>
      )}
    </div>
  );
}

