import React, { useEffect, useMemo, useState } from 'react';
import DatePicker from 'react-datepicker';
import { encode as risonEncode } from 'rison-node';
import BrandMark from './BrandMark';
import { KIBANA_DASHBOARD_N3_BASE_URL } from '../config';
import 'react-datepicker/dist/react-datepicker.css';

function toIso(date) {
  if (!date) return null;
  const d = date instanceof Date ? date : new Date(date);
  // Kibana expects ISO strings for absolute time range
  return d.toISOString();
}

function buildIframeSrc({ baseUrl, time, refreshInterval }) {
  // Important: avoid double-encoding `_g`.
  // `URLSearchParams` will URL-encode the value when serializing; if we pre-encode here,
  // the `%` characters get encoded again and Kibana will fail to restore state.
  const risonGlobal = risonEncode({ time, refreshInterval });

  // Kibana's query string lives after the hash route (`#/view/...?...`)
  const [beforeQuery, queryString = ''] = String(baseUrl).split('?');
  const params = new URLSearchParams(queryString);
  params.set('_g', risonGlobal);

  return `${beforeQuery}?${params.toString()}`;
}

function KibanaEmbedStatic({ src }) {
  return (
    <div className="w-full h-full min-h-0 flex flex-col bg-white overflow-hidden">
      <iframe title="Kibana dashboard" src={src} className="w-full flex-1 min-h-0 border-0" />
    </div>
  );
}

function KibanaDashboardWithToolbar() {
  const [timeMode, setTimeMode] = useState('last30d'); // last7d | last30d | last90d | custom
  const [customRange, setCustomRange] = useState([null, null]);
  const [customFrom, customTo] = customRange;
  const [liveMode, setLiveMode] = useState(false);
  const [iframeSrc, setIframeSrc] = useState(KIBANA_DASHBOARD_N3_BASE_URL);

  const quickRanges = useMemo(
    () => [
      { id: 'last7d', label: 'Last 7 Days', from: 'now-7d', to: 'now' },
      { id: 'last30d', label: 'Last 30 Days', from: 'now-30d', to: 'now' },
      { id: 'last90d', label: 'Last 90 Days', from: 'now-90d', to: 'now' },
    ],
    []
  );

  const time = useMemo(() => {
    if (timeMode === 'custom') {
      const fromIso = toIso(customFrom);
      const toIsoStr = toIso(customTo);
      // If user picked only one side, keep Kibana's current behavior stable by falling back to relative
      if (!fromIso || !toIsoStr) return { from: 'now-30d', to: 'now' };
      return { from: fromIso, to: toIsoStr };
    }
    const preset = quickRanges.find((r) => r.id === timeMode) || quickRanges[1]; // default Last 30 Days
    return { from: preset.from, to: preset.to };
  }, [timeMode, customFrom, customTo, quickRanges]);

  const refreshInterval = useMemo(() => {
    // Kibana Rison booleans: pause:!f for active, pause:!t for paused
    return { pause: !liveMode, value: 1000 };
  }, [liveMode]);

  useEffect(() => {
    const next = buildIframeSrc({
      baseUrl: KIBANA_DASHBOARD_N3_BASE_URL,
      time,
      refreshInterval,
    });
    setIframeSrc(next);
  }, [time, refreshInterval]);

  const baseBtn =
    'px-3 py-2 rounded-lg text-sm font-semibold border transition-colors focus:outline-none focus:ring-2 focus:ring-orange-500';
  const activeBtn = 'bg-orange-600 border-orange-600 text-white hover:bg-orange-700';
  const inactiveBtn = 'bg-white border-gray-200 text-gray-700 hover:bg-gray-50';

  return (
    <div className="w-full flex flex-col bg-white h-full min-h-0 overflow-hidden">
      <div className="h-16 w-full bg-white border-b border-gray-200 px-4 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 flex-wrap min-w-0">
          <BrandMark className="h-8 w-8 shrink-0" />
          <div className="flex items-center gap-2">
            {quickRanges.map((r) => (
              <button
                key={r.id}
                type="button"
                onClick={() => setTimeMode(r.id)}
                className={`${baseBtn} ${timeMode === r.id ? activeBtn : inactiveBtn}`}
              >
                {r.label}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setTimeMode('custom')}
              className={`${baseBtn} ${timeMode === 'custom' ? activeBtn : inactiveBtn}`}
              title="Pick a custom date range"
            >
              Custom
            </button>
            <div className="relative">
              <DatePicker
                selectsRange
                startDate={customFrom}
                endDate={customTo}
                onChange={(range) => {
                  setCustomRange(range);
                  setTimeMode('custom');
                }}
                isClearable
                placeholderText="Select date range"
                className="h-9 w-[240px] px-3 rounded-lg bg-white border border-gray-200 text-gray-900 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500"
                calendarClassName="!bg-white !text-gray-900"
                popperPlacement="bottom-start"
              />
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-700 font-medium">Live Mode</span>
            <button
              type="button"
              onClick={() => setLiveMode((v) => !v)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full border transition-colors ${
                liveMode ? 'bg-orange-600 border-orange-600' : 'bg-gray-200 border-gray-200'
              }`}
              aria-pressed={liveMode}
              aria-label="Toggle live mode refresh"
            >
              <span
                className={`inline-block h-5 w-5 transform rounded-full bg-white transition-transform ${
                  liveMode ? 'translate-x-5' : 'translate-x-1'
                }`}
              />
            </button>
          </div>
        </div>
      </div>

      <iframe
        title="Kibana Dashboard"
        src={iframeSrc}
        className="w-full flex-1 min-h-0"
        style={{ border: 'none' }}
      />
    </div>
  );
}

/**
 * N1/N2: pass `embedOnlySrc` for a static full-viewport embed. N3: omit for toolbar + N3 dashboard URL.
 */
export default function KibanaDashboard({ embedOnlySrc = null }) {
  if (embedOnlySrc) {
    return <KibanaEmbedStatic src={embedOnlySrc} />;
  }
  return <KibanaDashboardWithToolbar />;
}
