/**
 * Shared config. Change MAX_TIME_RANGE_HOURS here to control the allowed
 * search time range in both the form validation and labels.
 *
 * ES_BASE controls the Elasticsearch URL used by the elastic frontend.
 */
export const MAX_TIME_RANGE_HOURS = 24;

export const ES_BASE =
  process.env.REACT_APP_ES_URL || 'http://localhost:9200';

/** Kibana embed for N3 (toolbar + time controls in KibanaDashboard.jsx). */
export const KIBANA_DASHBOARD_N3_BASE_URL =
  process.env.REACT_APP_KIBANA_DASHBOARD_N3_URL ||
  "http://localhost:5601/app/dashboards#/view/4d52dc89-2cc6-4b59-946a-c29f8247bb6b?embed=true&_g=(refreshInterval%3A(pause%3A!f%2Cvalue%3A60000)%2Ctime%3A(from%3A'2026-01-26T20%3A50%3A27.657Z'%2Cto%3A'2026-01-28T04%3A55%3A40.611Z'))";

/** Static embed for N1 / N2 (no DNSBL); override with REACT_APP_KIBANA_DASHBOARD_N12_URL. */
export const KIBANA_DASHBOARD_N12_EMBED_URL =
  process.env.REACT_APP_KIBANA_DASHBOARD_N12_URL ||
  "http://localhost:5601/app/dashboards#/view/38625801-0667-406e-8119-c3d35488577d?embed=true&_g=(refreshInterval%3A(pause%3A!f%2Cvalue%3A900000)%2Ctime%3A(from%3A'2026-01-26T05%3A30%3A58.064Z'%2Cto%3A'2026-01-30T18%3A34%3A50.322Z'))";

