/**
 * POS currency display. Amounts are rounded to cents (2 dp) in the backend;
 * the UI may hide trailing ".00" for whole amounts (common for Kyat display).
 */
const CURRENCY_CODE = 'MMK';
const CURRENCY_SYMBOL = 'Ks';

function _roundMoney(value) {
  const n = Number(value);
  const safe = Number.isFinite(n) ? n : 0;
  return Math.round(safe * 100) / 100;
}

/**
 * @param {number|string} value
 * @param {{ hideTrailingZeros?: boolean }} [options]  Default: hide ".00" and trailing zero in tenths when possible.
 * @returns {string} e.g. "1,500 Ks" or "1,500.50 Ks"
 */
function formatMoney(value, options = {}) {
  const hideTrailingZeros = options.hideTrailingZeros !== false;
  const rounded = _roundMoney(value);
  let minimumFractionDigits = 0;
  let maximumFractionDigits = 2;
  if (!hideTrailingZeros) {
    minimumFractionDigits = 2;
    maximumFractionDigits = 2;
  } else {
    const frac100 = Math.round(Math.abs(rounded) * 100) % 100;
    if (frac100 === 0) {
      minimumFractionDigits = 0;
      maximumFractionDigits = 0;
    } else if (frac100 % 10 === 0) {
      minimumFractionDigits = 1;
      maximumFractionDigits = 2;
    } else {
      minimumFractionDigits = 2;
      maximumFractionDigits = 2;
    }
  }
  const numStr = rounded.toLocaleString('en-US', {
    minimumFractionDigits,
    maximumFractionDigits,
  });
  return `${numStr} ${CURRENCY_SYMBOL}`;
}

/** Positive amount formatted with a leading minus (e.g. discounts). */
function formatMoneyNegative(value, options = {}) {
  const rounded = _roundMoney(value);
  if (rounded === 0) return formatMoney(0, options);
  return `-${formatMoney(Math.abs(rounded), options)}`;
}

if (typeof window !== 'undefined') {
  window.CURRENCY_CODE = CURRENCY_CODE;
  window.CURRENCY_SYMBOL = CURRENCY_SYMBOL;
  window.formatMoney = formatMoney;
  window.formatMoneyNegative = formatMoneyNegative;
}
