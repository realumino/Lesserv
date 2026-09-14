import { useEffect, useState } from 'react'
import * as api from '../api'

/**
 * Config tab: view the template and the generated config side by side,
 * and replace the template with new JSON.
 *
 * Why show both: the generated config (what Xray actually reads) is the
 * panel's own output — comparing it against the template makes a skipped
 * or failed sync visible at a glance.
 */
export default function ConfigPage() {
  const [template, setTemplate] = useState(undefined) // undefined = loading
  const [generated, setGenerated] = useState(undefined)
  const [text, setText] = useState('')
  const [msg, setMsg] = useState(null) // { ok: bool, text: string }
  const [busy, setBusy] = useState(false)

  const load = () => {
    api.fetchConfig().then(({ data, error }) => setTemplate(error ? null : data))
    api.fetchGeneratedConfig().then(({ data, error }) =>
      setGenerated(error ? null : data)
    )
  }

  useEffect(load, [])

  const save = async () => {
    let parsed
    try {
      parsed = JSON.parse(text)
    } catch {
      setMsg({ ok: false, text: 'Invalid JSON — check the syntax.' })
      return
    }
    setBusy(true)
    setMsg(null)
    const { error } = await api.postConfig(parsed)
    setBusy(false)
    if (error) {
      setMsg({ ok: false, text: `Save failed: ${error}` })
    } else {
      setMsg({ ok: true, text: 'Template saved; Xray config regenerated and restarted.' })
      setText('')
      load()
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <button
          onClick={load}
          className="text-xs text-blue-400 hover:text-blue-300"
        >
          Refresh
        </button>
      </div>
      <div className="grid md:grid-cols-2 gap-4">
        <JsonPanel
          title="Template"
          subtitle="the file you provide"
          value={template}
          empty="No template loaded yet."
        />
        <JsonPanel
          title="Config in use"
          subtitle={subtitleFor(generated)}
          value={generated === null ? null : generated?.config}
          empty="Not generated yet — no template loaded or last sync failed."
        />
      </div>
      <section>
        <h2 className="text-sm font-medium text-gray-400 mb-2">
          Replace template (paste full JSON)
        </h2>
        <textarea
          className="w-full h-48 bg-gray-950 border border-gray-800 rounded p-3 text-xs font-mono focus:outline-none focus:border-blue-500"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder='{"inbounds": [...], "outbounds": [...], ...}'
          spellCheck={false}
        />
        <div className="flex items-center gap-3 mt-2">
          <button
            onClick={save}
            disabled={busy || !text.trim()}
            className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white px-4 py-1.5 rounded text-sm font-medium"
          >
            {busy ? 'Saving…' : 'Save & Resync'}
          </button>
          {msg && (
            <p className={`text-sm ${msg.ok ? 'text-green-400' : 'text-red-400'}`}>
              {msg.text}
            </p>
          )}
        </div>
      </section>
    </div>
  )
}

/** One read-only JSON pane: loading, empty, or pretty-printed content. */
function JsonPanel({ title, subtitle, value, empty }) {
  return (
    <section>
      <h2 className="text-sm font-medium text-gray-400 mb-2">
        {title}
        {subtitle && (
          <span className="text-xs text-gray-600 font-normal ml-2">{subtitle}</span>
        )}
      </h2>
      {value === undefined ? (
        <p className="text-gray-400 text-sm">Loading…</p>
      ) : value === null ? (
        <p className="text-gray-500 text-sm">{empty}</p>
      ) : (
        <pre className="bg-gray-950 border border-gray-800 rounded p-3 text-xs overflow-auto max-h-72">
          {JSON.stringify(value, null, 2)}
        </pre>
      )}
    </section>
  )
}

/** Subtitle for the generated pane: its last-write time once known. */
function subtitleFor(generated) {
  if (generated?.generated_at) {
    return `regenerated ${new Date(generated.generated_at * 1000).toLocaleString()}`
  }
  return 'what Xray reads'
}