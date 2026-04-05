import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatNumber(n: number | null | undefined): string {
  if (n == null) return '—'
  return new Intl.NumberFormat().format(n)
}

export function formatDate(d: string | null | undefined): string {
  if (!d) return '—'
  return new Date(d).toLocaleDateString('en-SG', { year: 'numeric', month: 'short', day: 'numeric' })
}

export function hansardUrl(sittingDate: string): string {
  // Convert YYYY-MM-DD → https://sprs.parl.gov.sg/search/#/fullreport?sittingdate=DD-MM-YYYY
  const [year, month, day] = sittingDate.split('-')
  return `https://sprs.parl.gov.sg/search/#/fullreport?sittingdate=${day}-${month}-${year}`
}

export function sectionTypeLabel(code: string): string {
  const labels: Record<string, string> = {
    OS: 'Oral Speech',
    OA: 'Oral Answer',
    WA: 'Written Answer',
    WANA: 'Written Answer (Not Answered)',
    BP: 'Bill Proceedings',
    BI: 'Bill Introduction',
    WS: 'Written Statement',
  }
  return labels[code] ?? code
}
