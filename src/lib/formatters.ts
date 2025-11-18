/**
 * Utility functions for formatting financial data
 */

/**
 * Format currency with thousand separators and proper decimal places
 * @param value - The numeric value to format
 * @param decimals - Number of decimal places (default: 2)
 * @param currency - Currency symbol (default: '$')
 * @returns Formatted currency string
 */
export function formatCurrency(
  value: number | string | undefined | null,
  decimals: number = 2,
  currency: string = '$'
): string {
  if (value === undefined || value === null || value === '') return `${currency}0.00`;
  
  const numValue = typeof value === 'number' ? value : parseFloat(value);
  
  if (isNaN(numValue)) return `${currency}0.00`;
  
  return `${currency}${numValue.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`;
}

/**
 * Format percentage with proper decimal places
 * @param value - The numeric value to format (as decimal or percentage)
 * @param decimals - Number of decimal places (default: 2)
 * @param isDecimal - Whether value is in decimal format (0.05 = 5%)
 * @returns Formatted percentage string
 */
export function formatPercentage(
  value: number | string | undefined | null,
  decimals: number = 2,
  isDecimal: boolean = false
): string {
  if (value === undefined || value === null || value === '') return '0.00%';
  
  const numValue = typeof value === 'number' ? value : parseFloat(value);
  
  if (isNaN(numValue)) return '0.00%';
  
  const percentValue = isDecimal ? numValue * 100 : numValue;
  
  return `${percentValue.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}%`;
}

/**
 * Format profit/loss with sign and color indication
 * @param value - The P&L value
 * @param decimals - Number of decimal places (default: 2)
 * @returns Object with formatted value and color class
 */
export function formatProfitLoss(
  value: number | string | undefined | null,
  decimals: number = 2
): { formatted: string; colorClass: string; sign: string } {
  if (value === undefined || value === null || value === '') {
    return { formatted: '$0.00', colorClass: 'text-muted-foreground', sign: '' };
  }
  
  const numValue = typeof value === 'number' ? value : parseFloat(value);
  
  if (isNaN(numValue)) {
    return { formatted: '$0.00', colorClass: 'text-muted-foreground', sign: '' };
  }
  
  const sign = numValue > 0 ? '+' : numValue < 0 ? '-' : '';
  const colorClass = numValue >= 0 ? 'text-accent' : 'text-destructive';
  
  // Format with absolute value and prepend the correct sign
  const formattedValue = numValue.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
  
  const formatted = `${sign}$${Math.abs(numValue).toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`;
  
  return { formatted, colorClass, sign };
}

/**
 * Format large numbers with abbreviated suffixes (K, M, B)
 * @param value - The numeric value to format
 * @param decimals - Number of decimal places (default: 1)
 * @returns Formatted abbreviated string
 */
export function formatCompactNumber(
  value: number | string | undefined | null,
  decimals: number = 1
): string {
  if (value === undefined || value === null || value === '') return '0';
  
  const numValue = typeof value === 'number' ? value : parseFloat(value);
  
  if (isNaN(numValue)) return '0';
  
  const absValue = Math.abs(numValue);
  const sign = numValue < 0 ? '-' : '';
  
  if (absValue >= 1e9) {
    return `${sign}${(absValue / 1e9).toFixed(decimals)}B`;
  } else if (absValue >= 1e6) {
    return `${sign}${(absValue / 1e6).toFixed(decimals)}M`;
  } else if (absValue >= 1e3) {
    return `${sign}${(absValue / 1e3).toFixed(decimals)}K`;
  }
  
  return `${sign}${absValue.toFixed(decimals)}`;
}

/**
 * Format change with sign and percentage
 * @param currentValue - Current value
 * @param previousValue - Previous value
 * @param showPercentage - Whether to show percentage change
 * @returns Object with formatted change and percentage
 */
export function formatChange(
  currentValue: number | string | undefined | null,
  previousValue: number | string | undefined | null,
  showPercentage: boolean = true
): { change: string; percentage: string; colorClass: string } {
  const current = typeof currentValue === 'number' ? currentValue : parseFloat(currentValue || '0');
  const previous = typeof previousValue === 'number' ? previousValue : parseFloat(previousValue || '0');
  
  if (isNaN(current) || isNaN(previous)) {
    return { change: '$0.00', percentage: '—', colorClass: 'text-muted-foreground' };
  }
  
  const changeValue = current - previous;
  
  // Handle division by zero for percentage
  const percentChange = previous !== 0 ? (changeValue / previous) * 100 : null;
  
  const sign = changeValue > 0 ? '+' : changeValue < 0 ? '-' : '';
  const colorClass = changeValue >= 0 ? 'text-accent' : 'text-destructive';
  
  // Format change value with correct sign
  const change = `${sign}$${Math.abs(changeValue).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
  
  // Handle percentage display
  let percentage = '';
  if (showPercentage) {
    if (percentChange === null) {
      percentage = previous === 0 && current !== 0 ? '∞' : '—';
    } else {
      percentage = `${sign}${Math.abs(percentChange).toFixed(2)}%`;
    }
  }
  
  return { change, percentage, colorClass };
}

/**
 * Format price with appropriate decimal places based on value
 * @param value - Price value
 * @returns Formatted price string
 */
export function formatPrice(value: number | string | undefined | null): string {
  if (value === undefined || value === null || value === '') return '$0.00';
  
  const numValue = typeof value === 'number' ? value : parseFloat(value);
  
  if (isNaN(numValue)) return '$0.00';
  
  // Use more decimals for very small prices (crypto)
  if (numValue < 0.01) {
    return formatCurrency(numValue, 6);
  } else if (numValue < 1) {
    return formatCurrency(numValue, 4);
  } else {
    return formatCurrency(numValue, 2);
  }
}

/**
 * Format number with thousand separators
 * @param value - Numeric value
 * @param decimals - Number of decimal places (default: 0)
 * @returns Formatted number string
 */
export function formatNumber(
  value: number | string | undefined | null,
  decimals: number = 0
): string {
  if (value === undefined || value === null || value === '') return '0';
  
  const numValue = typeof value === 'number' ? value : parseFloat(value);
  
  if (isNaN(numValue)) return '0';
  
  return numValue.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}
