const integer = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 0 });
const decimal = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 1 });

export const fmtInt = (n) => (n == null ? "–" : integer.format(n));
export const fmtNum = (n) => (n == null ? "–" : decimal.format(n));
export const fmtPct = (n) => (n == null ? "–" : `${decimal.format(n)}%`);
export const fmtMoney = (n) => (n == null ? "–" : `£${integer.format(n)}`);
