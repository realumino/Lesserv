import { useEffect, useState } from 'react'
import * as api from '../api'

/**
 * Config tab: view the current Xray template and replace it with new JSON.
 *
 * Why it exists: a fresh install gets its first template this way instead of
 * dropping a file into config/. The panel never validates the template's
 * structure — only that the body is valid JSON.
 */
export default function ConfigPage() {
  const [current, setCurrent] = useState(undefined) // undefined = loading
  const [text, setText] = useState('')
  const [msg, setMsg] = useState(null) // { ok: bool, text: string }
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.fetchConfig().then(({ data, error }) => {
      setCurrent(error ? null : data)
    })
  }, [])

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
      setCurrent(parsed)
      setText('')
    }
  }

  return (
    <div className="space-y-4">
      <section>
        <h2 className="text-sm font-medium text-gray-400 mb-2">Current template</h2>
        {current === undefined ? (
          <p className="text-gray-400 text-sm">Loading…</p>
        ) : current === null ? (
          <p className="text-gray-500 text-sm">No template loaded yet.</p>
        ) : (
          <pre className="bg-gray-950 border border-gray-800 rounded p-3 text-xs overflow-auto max-h-72">
            {JSON.stringify(current, null, 2)}
          </pre>
        )}
      </section>
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
