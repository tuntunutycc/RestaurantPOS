/**
 * Dine-in table label formatting for POS grids and headers.
 * Strips a leading "Table " prefix for compact display; does not affect takeaway labels.
 */
(function initTableDisplay(global) {
  const TABLE_PREFIX_RE = /^table\s+/i;

  function stripTableNamePrefix(name) {
    const raw = String(name ?? '').trim();
    if (!raw) return '';
    const stripped = raw.replace(TABLE_PREFIX_RE, '').trim();
    return stripped || raw;
  }

  /**
   * @param {string|{name?: string, name_or_number?: string, id?: number}|null|undefined} tableOrName
   * @param {number|string|null} [fallbackId]
   */
  function displayTableName(tableOrName, fallbackId) {
    if (tableOrName == null) {
      return fallbackId != null && fallbackId !== '' ? `#${fallbackId}` : '';
    }
    if (typeof tableOrName === 'object') {
      const raw = tableOrName.name ?? tableOrName.name_or_number ?? '';
      if (raw) return stripTableNamePrefix(raw);
      if (tableOrName.id != null) return `#${tableOrName.id}`;
      return '';
    }
    const text = String(tableOrName).trim();
    if (!text) {
      return fallbackId != null && fallbackId !== '' ? `#${fallbackId}` : '';
    }
    return stripTableNamePrefix(text);
  }

  global.tableDisplay = {
    stripTableNamePrefix,
    displayTableName,
  };
})(typeof window !== 'undefined' ? window : globalThis);
