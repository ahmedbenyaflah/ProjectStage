/**
 * Shared config. Change MAX_TIME_RANGE_HOURS here to control the allowed
 * search time range in both the form validation and labels.
 *
 * ES_BASE controls the Elasticsearch URL used by the elastic frontend.
 */
export const MAX_TIME_RANGE_HOURS = 24;

export const ES_BASE =
  process.env.REACT_APP_ES_URL || 'http://localhost:9200';

