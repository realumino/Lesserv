import { useState } from 'react'
import * as api from '../api'

/**
 * Modal form for creating or editing a user.
 *
 * Why one component for both: the fields are identical; the only differences
 * are the initial values, the read-only username on edit, and POST vs PUT.
 * `target` is null for create, or the existing user object for edit.
 */
export default function UserForm({ target, inbounds, outbounds, onClose, onSaved }) {
  const isEdit = Boolean(target)
  const [form, setForm] = useState(() => initialForm(target))
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const set = (field, value) => setForm((f) => ({ ...f, [field]: value }))
  const toggle = (field, tag) =>
    setForm((f) => ({
      ...f,
      [field]: f[field].includes(tag)
        ? f[field].filter((t) => t !== tag)
        : [...f[field], tag],
    }))

  const submit = async (e) => {
    e.preventDefault()
    const clientError = validateClientSide(form)
    if (clientError) { setError(clientError); return }
    setBusy(true)
    setError(null)
    const payload = buildPayload(form, isEdit)
    const { error } = isEdit
      ? await api.updateUser(target.username, payload)
      : await api.createUser(payload)
    setBusy(false)
    if (error) setError(error)
    else onSaved()
  }

  return (
    <div
      className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4 z-10"
      onClick={onClose}
    >
      <form
        onSubmit={submit}
        onClick={(e) => e.stopPropagation()}
        className="bg-apple-card rounded-2xl p-6 w-full max-w-lg space-y-5 shadow-xl border border-apple-border"
      >
        <h2 className="text-lg font-bold text-apple-text">{isEdit ? `Edit ${target.username}` : 'Add User'}</h2>
        {error && (
          <p className="bg-[#ffecea] border border-[#ff453a]/20 text-apple-red rounded-xl px-4 py-2 text-sm">{error}</p>
        )}
        <Field label="Username">
          {isEdit ? (
            <p className="font-mono text-apple-text py-1.5">{target.username}</p>
          ) : (
            <input
              className={inputCls}
              value={form.username}
              onChange={(e) => set('username', e.target.value)}
              placeholder="no '@', no spaces, max 32 chars"
            />
          )}
        </Field>
        <Field label="Status">
          <select
            className={inputCls}
            value={form.status}
            onChange={(e) => set('status', e.target.value)}
          >
            <option value="active">active</option>
            <option value="disabled">disabled</option>
          </select>
        </Field>
        <Field label="Expiry">
          <label className="flex items-center gap-2 text-sm text-apple-text mb-1">
            <input
              type="checkbox"
              checked={form.hasExpire}
              onChange={(e) => set('hasExpire', e.target.checked)}
              className="accent-apple-blue w-4 h-4"
            />
            User expires at a date
          </label>
          {form.hasExpire && (
            <input
              type="datetime-local"
              className={inputCls}
              value={form.expireLocal}
              onChange={(e) => set('expireLocal', e.target.value)}
            />
          )}
        </Field>
        <CheckboxGrid
          label="Allowed Inbounds"
          options={inbounds}
          checked={form.allowed_inbounds}
          onToggle={(tag) => toggle('allowed_inbounds', tag)}
        />
        <CheckboxGrid
          label="Allowed Outbounds"
          options={outbounds}
          checked={form.allowed_outbounds}
          onToggle={(tag) => toggle('allowed_outbounds', tag)}
        />
        <Field label="Note">
          <textarea
            className={`${inputCls} resize-y`}
            rows={2}
            value={form.note}
            onChange={(e) => set('note', e.target.value)}
          />
        </Field>
        <div className="flex justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="px-5 py-2 rounded-full text-sm font-medium bg-apple-gray-surface text-apple-text hover:bg-apple-border transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={busy}
            className="px-5 py-2 rounded-full text-sm bg-apple-blue hover:bg-apple-blue-hover disabled:opacity-50 text-white font-medium transition-colors shadow-sm"
          >
            {busy ? 'Saving…' : isEdit ? 'Save Changes' : 'Create User'}
          </button>
        </div>
      </form>
    </div>
  )
}

const inputCls =
  'w-full bg-apple-card border border-apple-border rounded-xl px-3 py-2 text-sm text-apple-text placeholder-apple-gray focus:outline-none focus:border-apple-blue focus:ring-2 focus:ring-apple-blue/10 transition-all'

/** Labeled field wrapper for consistent spacing. */
function Field({ label, children }) {
  return (
    <div>
      <label className="block text-xs font-semibold text-apple-muted uppercase tracking-wide mb-1.5">{label}</label>
      {children}
    </div>
  )
}

/** Grid of checkboxes for inbound/outbound tag selection. */
function CheckboxGrid({ label, options, checked, onToggle }) {
  return (
    <Field label={label}>
      {options.length === 0 ? (
        <p className="text-xs text-apple-muted">None available (template not loaded?)</p>
      ) : (
        <div className="grid grid-cols-2 gap-2">
          {options.map((opt) => (
            <label
              key={opt.tag}
              className="flex items-center gap-2 text-sm bg-apple-card border border-apple-border rounded-xl px-3 py-2 cursor-pointer hover:border-apple-blue/40 transition-colors"
            >
              <input
                type="checkbox"
                checked={checked.includes(opt.tag)}
                onChange={() => onToggle(opt.tag)}
                className="accent-apple-blue w-4 h-4"
              />
              <span className="font-mono text-apple-text">{opt.tag}</span>
              {opt.network && (
                <span className="text-xs text-apple-muted ml-auto">
                  {opt.network}
                  {opt.security ? ` + ${opt.security}` : ''}
                </span>
              )}
            </label>
          ))}
        </div>
      )}
    </Field>
  )
}

/** Initial form state from an existing user (edit) or defaults (create). */
function initialForm(user) {
  const expires = Boolean(user && user.expire > 0)
  return {
    username: user?.username ?? '',
    status: user?.status ?? 'active',
    hasExpire: expires,
    expireLocal: expires ? toLocalInput(user.expire) : '',
    allowed_inbounds: user?.allowed_inbounds ?? [],
    allowed_outbounds: user?.allowed_outbounds ?? [],
    note: user?.note ?? '',
  }
}

/** Convert form state into the JSON body for POST/PUT. */
function buildPayload(form, isEdit) {
  const payload = {
    status: form.status,
    expire: form.hasExpire ? fromLocalInput(form.expireLocal) : null,
    allowed_inbounds: form.allowed_inbounds,
    allowed_outbounds: form.allowed_outbounds,
    note: form.note || null,
  }
  if (!isEdit) payload.username = form.username.trim()
  return payload
}

/** Quick UX validation; the backend re-validates everything anyway. */
function validateClientSide(form) {
  if (form.hasExpire && !form.expireLocal) return 'Pick an expiry date or uncheck the box.'
  return null
}

/** unix ts -> "YYYY-MM-DDTHH:MM" in local time (datetime-local input format). */
function toLocalInput(ts) {
  const d = new Date(ts * 1000)
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset())
  return d.toISOString().slice(0, 16)
}

/** "YYYY-MM-DDTHH:MM" local input value -> unix ts. */
function fromLocalInput(str) {
  return Math.floor(new Date(str).getTime() / 1000)
}
