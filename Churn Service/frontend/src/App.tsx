import { lazy, Suspense, type ReactNode } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router'
import AdminLayout from './components/AdminLayout'
import Layout from './components/Layout'
import SiteLayout from './components/SiteLayout'
import { Spinner } from './components/ui'
import { useAuth } from './lib/auth'
import AuthPage from './pages/AuthPage'

// Pages load on demand, so the public site and sign-in screen don't download the charting library.
const Home = lazy(() => import('./pages/site/Home'))
const Pricing = lazy(() => import('./pages/site/Pricing'))
const Jobs = lazy(() => import('./pages/site/Jobs'))
const About = lazy(() => import('./pages/site/About'))
const Faq = lazy(() => import('./pages/site/Faq'))
const JobDetail = lazy(() => import('./pages/site/JobDetail'))
const Overview = lazy(() => import('./pages/Overview'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Customers = lazy(() => import('./pages/Customers'))
const CustomerDetail = lazy(() => import('./pages/CustomerDetail'))
const Campaigns = lazy(() => import('./pages/Campaigns'))
const Models = lazy(() => import('./pages/Models'))
const Monitoring = lazy(() => import('./pages/Monitoring'))
const Data = lazy(() => import('./pages/Data'))
const Settings = lazy(() => import('./pages/Settings'))
const AdminOverview = lazy(() => import('./pages/admin/Overview'))
const AdminWorkspaces = lazy(() => import('./pages/admin/Workspaces'))
const AdminWorkspaceDetail = lazy(() => import('./pages/admin/WorkspaceDetail'))
const AdminUsers = lazy(() => import('./pages/admin/Users'))
const AdminJobs = lazy(() => import('./pages/admin/Jobs'))
const AdminPlans = lazy(() => import('./pages/admin/Plans'))
const AdminHiring = lazy(() => import('./pages/admin/Hiring'))
const AdminAbout = lazy(() => import('./pages/admin/AboutAdmin'))
const AdminHiringPosting = lazy(() => import('./pages/admin/HiringPosting'))

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <div className="p-8"><Spinner /></div>
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />
  return children
}

/** Site operators only. The API enforces this too; this just keeps everyone else out of the screens. */
function RequireAdmin({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  if (!user?.is_admin) return <Navigate to="/app" replace />
  return children
}

function page(element: ReactNode) {
  return <Suspense fallback={<Spinner />}>{element}</Suspense>
}

export default function App() {
  return (
    <Routes>
      <Route element={<SiteLayout />}>
        <Route index element={page(<Home />)} />
        <Route path="pricing" element={page(<Pricing />)} />
        <Route path="jobs" element={page(<Jobs />)} />
        <Route path="about" element={page(<About />)} />
        <Route path="faq" element={page(<Faq />)} />
        <Route path="jobs/:slug" element={page(<JobDetail />)} />
      </Route>
      <Route path="/login" element={<AuthPage mode="login" />} />
      <Route path="/register" element={<AuthPage mode="register" />} />
      <Route path="/app" element={<RequireAuth><Layout /></RequireAuth>}>
        <Route index element={page(<Overview />)} />
        <Route path="risk" element={page(<Dashboard />)} />
        <Route path="customers" element={page(<Customers />)} />
        <Route path="customers/:id" element={page(<CustomerDetail />)} />
        <Route path="campaigns" element={page(<Campaigns />)} />
        <Route path="models" element={page(<Models />)} />
        <Route path="monitoring" element={page(<Monitoring />)} />
        <Route path="data" element={page(<Data />)} />
        <Route path="settings" element={page(<Settings />)} />
      </Route>
      <Route path="/admin" element={<RequireAuth><RequireAdmin><AdminLayout /></RequireAdmin></RequireAuth>}>
        <Route index element={page(<AdminOverview />)} />
        <Route path="workspaces" element={page(<AdminWorkspaces />)} />
        <Route path="workspaces/:id" element={page(<AdminWorkspaceDetail />)} />
        <Route path="users" element={page(<AdminUsers />)} />
        <Route path="jobs" element={page(<AdminJobs />)} />
        <Route path="plans" element={page(<AdminPlans />)} />
        <Route path="hiring" element={page(<AdminHiring />)} />
        <Route path="about" element={page(<AdminAbout />)} />
        <Route path="hiring/:id" element={page(<AdminHiringPosting />)} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
