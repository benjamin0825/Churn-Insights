// Questions and answers for the FAQ page. Answers describe what the product does today.

export interface FaqItem {
  q: string
  a: string
  /** Shown in the short FAQ on the home page. */
  featured?: boolean
}

export interface FaqTopic {
  id: string
  title: string
  items: FaqItem[]
}

export const FAQ_TOPICS: FaqTopic[] = [
  {
    id: 'getting-started',
    title: 'Getting started',
    items: [
      {
        q: 'What is Churn Insights?',
        a: 'Churn Insights by WSL Technologies is a churn prediction service for subscription businesses. It tracks your subscription metrics, predicts which customers are likely to cancel in the next 8 weeks, explains why for each customer, and plans retention campaigns that are worth more than they cost.',
        featured: true,
      },
      {
        q: 'Who is it for?',
        a: 'Subscription businesses that want to keep more customers: customer success, finance, marketing and data teams. It works best when you have weekly usage, billing and support data for your customers. Today the upload format is designed around subscription services such as broadband, telecom and streaming.',
      },
      {
        q: 'How do I get started?',
        a: 'Create a free workspace, then either click "Load demo data" or upload your own four CSV files. A model is trained in the background and the dashboard fills in by itself when it is done.',
      },
      {
        q: 'Can I try it without my own data?',
        a: 'Yes. After you create a workspace, click "Load demo data" and a realistic subscription business is generated, trained and scored for you in about a minute. Every screen works with the demo data, so you can explore before uploading anything.',
        featured: true,
      },
      {
        q: 'How long does setup take?',
        a: 'With demo data, about a minute. With your own data it depends on how many customers and weeks of history you have, and on the training mode you pick: quick, standard or thorough. Quick is fastest; thorough tries more model settings and takes longer.',
      },
    ],
  },
  {
    id: 'data',
    title: 'Your data',
    items: [
      {
        q: 'What data do I need?',
        a: 'Four CSV files: customers (plan, contract, region and so on), weekly usage (sessions, minutes, data), invoices (amount, discount, late payments) and support tickets (category, text, resolution time, satisfaction). Each file has a downloadable template that shows the exact columns.',
        featured: true,
      },
      {
        q: 'How much history do I need?',
        a: 'At least 52 weeks. A year of history lets the model learn seasonal patterns and see enough customers leave to learn from.',
      },
      {
        q: 'Which file formats and sizes are supported?',
        a: 'CSV files of up to 300 MB each. Dates can be in any common format, and yes/no columns accept true/false, yes/no or 1/0.',
      },
      {
        q: 'What happens if my files have mistakes?',
        a: 'Every upload is checked before anything is saved. If something is wrong, such as a missing column, a bad date or a value out of range, you get a readable list of problems to fix, and your current data stays as it was.',
      },
      {
        q: 'Can I update my data later?',
        a: 'Yes. Upload new files at any time. The newest upload becomes your active dataset, and you can retrain the model on it straight away.',
      },
    ],
  },
  {
    id: 'predictions',
    title: 'Predictions & models',
    items: [
      {
        q: 'How far ahead does it predict?',
        a: 'Eight weeks. Every active customer gets a calibrated probability of leaving in that window. Calibrated means a 30% score really behaves like 30%, so the probabilities add up to an honest estimate of expected churners and revenue at risk.',
        featured: true,
      },
      {
        q: 'How accurate are the predictions?',
        a: 'It depends on your data. Every model version comes with a full report measured on data it never saw during training, including ROC AUC, precision and lift, so you can judge the model yourself on the Models page.',
      },
      {
        q: 'How does it explain a prediction?',
        a: 'Each customer gets the eight strongest reasons behind their score, calculated with SHAP explanations: for example falling usage, a month-to-month contract or recent complaints. Reasons show whether they push risk up or down.',
      },
      {
        q: 'What are the risk tiers?',
        a: 'Customers are grouped into high, medium and low risk based on their churn probability, so your team can focus on the high-risk list first.',
      },
      {
        q: 'What happens if a new model is worse than the current one?',
        a: 'It stays out of production. A newly trained model only replaces the current one if it performs better on the same test. You can also promote any version or roll back by hand.',
      },
      {
        q: 'What is drift monitoring?',
        a: 'Customer behaviour changes over time. Drift monitoring compares recent data with the data the model learned from, feature by feature and region by region, using PSI and KS tests. When things have shifted, it warns you that it may be time to retrain.',
      },
    ],
  },
  {
    id: 'campaigns',
    title: 'Retention campaigns',
    items: [
      {
        q: 'How does it decide who gets a retention offer?',
        a: 'Each customer is ranked by expected profit: churn probability × offer success rate × customer value − offer cost. Customers are only worth an offer when that number is positive, so you never spend more than you expect to save.',
        featured: true,
      },
      {
        q: 'Can I set a budget?',
        a: 'Yes. Set the offer cost, how often offers work, months of customer value, an optional budget and maximum number of customers, a minimum probability and which risk tiers to include. Cost, revenue saved, profit, ROI and a profit curve update as you adjust.',
      },
      {
        q: 'Does Churn Insights send the offers?',
        a: 'No. It decides who should get an offer and why. Save the campaign and export the target list as CSV to use in your email, CRM or customer success tools.',
      },
    ],
  },
  {
    id: 'security',
    title: 'Security & privacy',
    items: [
      {
        q: 'Is my data kept separate from other companies?',
        a: 'Yes. Every company has its own workspace, and every query and file is isolated to it. Members of one workspace can never see another workspace’s data.',
        featured: true,
      },
      {
        q: 'How are accounts protected?',
        a: 'Passwords are never stored as text; they are hashed with bcrypt. Signing in gives you a signed session token that expires after 12 hours.',
      },
      {
        q: 'Who at WSL can see my data?',
        a: 'WSL administrators can see account information such as workspace names, plans, members and job status, so they can help with support. The admin panel does not show your customer records.',
      },
      {
        q: 'Can I delete my data?',
        a: 'Yes. Contact us and we will delete your workspace, which permanently removes your uploaded data, models, scores and campaigns.',
      },
    ],
  },
  {
    id: 'account',
    title: 'Plans & account',
    items: [
      {
        q: 'Is there a free plan?',
        a: 'Yes. The Starter plan is free. See the Pricing page for what each plan includes.',
      },
      {
        q: 'Do I need a credit card to start?',
        a: 'No. You can create a workspace and use the demo data without entering any payment details.',
      },
      {
        q: 'Can I change plans later?',
        a: 'Yes. You can move between plans at any time, and your data, models and campaigns stay where they are.',
      },
      {
        q: 'Can I invite teammates?',
        a: 'Not yet. Today each workspace is created by its owner. Inviting teammates with their own logins is on our roadmap.',
      },
      {
        q: 'I forgot my password. What can I do?',
        a: 'Contact us and an administrator will reset it for you with a new temporary password. Self-service password reset by email is on our roadmap.',
      },
      {
        q: 'Is there an API?',
        a: 'Yes. Everything in the app is available through a REST API, with interactive documentation at /api/docs.',
      },
    ],
  },
  {
    id: 'careers',
    title: 'Careers',
    items: [
      {
        q: 'Is WSL Technologies hiring?',
        a: 'See our Jobs page for open positions. Each role has its own page with the details and an application form.',
      },
      {
        q: 'How do I apply?',
        a: 'Open the role on the Jobs page and fill in the form with your details, links and CV (PDF or Word, up to 5 MB). We read every application and reply by email.',
      },
    ],
  },
]

export const FAQ_COUNT = FAQ_TOPICS.reduce((n, t) => n + t.items.length, 0)
export const FEATURED_FAQ = FAQ_TOPICS.flatMap((t) => t.items.filter((i) => i.featured))

/** URL-friendly id for linking to one question. */
export const faqId = (q: string) => q.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 60)
