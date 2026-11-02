// Sample customers shown in the marketing pages' example widgets.
// Temporary: the names are invented and the photos are AI-generated people who don't exist.

export interface SampleCustomer {
  name: string
  photo: string
  plan: string
}

export const SAMPLE_CUSTOMERS: SampleCustomer[] = [
  // The first one matches demo customer #16220 shown in the product screenshots.
  { name: 'Fatima Patel', photo: '/customers/fatima-patel.webp', plan: 'Standard plan' },
  { name: 'James Carter', photo: '/customers/james-carter.webp', plan: 'Premium plan' },
  { name: 'Sarah Mitchell', photo: '/customers/sarah-mitchell.webp', plan: 'Basic plan' },
  { name: 'Tom Becker', photo: '/customers/tom-becker.webp', plan: 'Standard plan' },
  { name: 'Elena Garcia', photo: '/customers/elena-garcia.webp', plan: 'Premium plan' },
  { name: 'Anna Kowalski', photo: '/customers/anna-kowalski.webp', plan: 'Standard plan' },
]

export const FEATURED_CUSTOMER = SAMPLE_CUSTOMERS[0]

export type AlertTone = 'risk' | 'saved' | 'offer'

/** Events cycled through by the hero's live feed. */
export const LIVE_ALERTS: { customer: SampleCustomer; tone: AlertTone; title: string; detail: string }[] = [
  { customer: SAMPLE_CUSTOMERS[0], tone: 'risk', title: '72% churn risk', detail: 'Usage down 38% · asked about fees' },
  { customer: SAMPLE_CUSTOMERS[1], tone: 'offer', title: 'Retention offer sent', detail: 'Expected profit $214' },
  { customer: SAMPLE_CUSTOMERS[2], tone: 'saved', title: 'Customer kept', detail: 'Accepted 3 months at 15% off' },
  { customer: SAMPLE_CUSTOMERS[3], tone: 'risk', title: '64% churn risk', detail: 'Two late payments this quarter' },
  { customer: SAMPLE_CUSTOMERS[4], tone: 'saved', title: 'Risk dropped to 18%', detail: 'Usage back up after support call' },
  { customer: SAMPLE_CUSTOMERS[5], tone: 'offer', title: 'Retention offer sent', detail: 'Expected profit $176' },
]
