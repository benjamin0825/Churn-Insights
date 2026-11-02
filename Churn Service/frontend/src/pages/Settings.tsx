import { useMutation } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Button, Card, ErrorBox, Field, Input, Notice, PageHeader, Select } from '../components/ui'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { saveTheme, storedTheme, type Theme } from '../lib/theme'
import type { Organization } from '../lib/types'

export default function Settings() {
  const { user, refresh } = useAuth()
  const org = user!.organization
  const [values, setValues] = useState({
    offer_cost: org.offer_cost,
    retention_success_rate: org.retention_success_rate * 100,
    months_of_value: org.months_of_value,
  })
  const [theme, setTheme] = useState<Theme>(storedTheme)
  const changeTheme = (next: Theme) => {
    setTheme(next)
    saveTheme(next)
  }

  const save = useMutation({
    mutationFn: () => api<Organization>('/api/organization/economics', {
      method: 'PUT',
      body: { ...values, retention_success_rate: values.retention_success_rate / 100 },
    }),
    onSuccess: () => refresh(),
  })

  function submit(e: FormEvent) {
    e.preventDefault()
    save.mutate()
  }

  return (
    <>
      <PageHeader title="Settings" />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Retention economics">
          <form onSubmit={submit} className="space-y-4">
            <p className="text-sm text-ink-2">Defaults for new campaigns. They decide which customers are worth an offer.</p>
            <div className="grid grid-cols-3 gap-3">
              <Field label="Offer cost ($)">
                <Input type="number" min={0} step="0.5" value={values.offer_cost} onChange={(e) => setValues({ ...values, offer_cost: Number(e.target.value) })} />
              </Field>
              <Field label="Success rate (%)">
                <Input type="number" min={0} max={100} value={values.retention_success_rate} onChange={(e) => setValues({ ...values, retention_success_rate: Number(e.target.value) })} />
              </Field>
              <Field label="Months of value">
                <Input type="number" min={1} max={120} value={values.months_of_value} onChange={(e) => setValues({ ...values, months_of_value: Number(e.target.value) })} />
              </Field>
            </div>
            <Button type="submit" loading={save.isPending} disabled={user?.role !== 'owner'}>Save</Button>
            {save.isSuccess && <Notice>Saved.</Notice>}
            {save.error && <ErrorBox error={save.error} />}
          </form>
        </Card>
        <Card title="Account">
          <dl className="space-y-2 text-sm">
            {[['Name', user!.name], ['Email', user!.email], ['Role', user!.role], ['Organization', org.name]].map(([k, v]) => (
              <div key={k} className="flex justify-between gap-4"><dt className="text-ink-2">{k}</dt><dd className="font-medium">{v}</dd></div>
            ))}
          </dl>
          <div className="mt-5 border-t border-hairline pt-4">
            <Field label="Theme">
              <Select value={theme} onChange={(e) => changeTheme(e.target.value as Theme)} className="w-48">
                <option value="system">Match system</option><option value="light">Light</option><option value="dark">Dark</option>
              </Select>
            </Field>
          </div>
        </Card>
      </div>
    </>
  )
}
