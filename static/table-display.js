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

  /** Compact status label for floor grid cards (API values unchanged in data attrs). */
  function displayTableStatus(status) {
    const key = String(status ?? '').trim().toLowerCase();
    if (key === 'available') return 'Free';
    if (key === 'occupied') return 'Occupied';
    if (!key) return '';
    return key.charAt(0).toUpperCase() + key.slice(1);
  }

  /** Typography for status on light card backgrounds (Cashier, Table Dashboard). */
  const tableStatusTypographyClass =
    'text-[10px] font-normal leading-tight tracking-normal normal-case text-slate-600';

  /** Typography for status on saturated card backgrounds (Waiter grid). */
  const tableStatusTypographyClassOnDark =
    'text-[10px] font-normal leading-tight tracking-normal normal-case text-white/85';

  global.tableDisplay = {
    stripTableNamePrefix,
    displayTableName,
    displayTableStatus,
    tableStatusTypographyClass,
    tableStatusTypographyClassOnDark,
  };
})(typeof window !== 'undefined' ? window : globalThis);
