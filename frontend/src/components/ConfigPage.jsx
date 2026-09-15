import { useEffect, useState } from 'react'
import * as api from '../api'

/**
 * Config tab: view the user-provided config and the runtime config side by
 * side, replace the config with new JSON, and manage the panel-generated
 * REALITY keys.
 *
 * Why show both: the runtime config (what Xray actually reads) is the
 * panel's own output — comparing it against the user config makes a
 * skipped or failed sync visible at a glance. The REALITY section lives
 * here because keys only exist in the context of a loaded config.
 */
export default function ConfigPage() {
  const [config, setConfig] = useState(undefined) // undefined = loading
  const [runtime, setRuntime] = useState(undefined)
  const [text, setText] = useState('')
  const [msg, setMsg] = useState(null) // { ok: bool, text: string }
  const [busy, setBusy] = useState(false)
  const [keys, setKeys] = useState(undefined)
  const [keyMsg, setKeyMsg] = useState(null)
  const [rotating, setRotating] = useState(null) // tag | 'all' | null

  const load = () => {
    api.fetchConfig().then(({ data, error }) => setConfig(error ? null : data))
    api.fetchRuntimeConfig().then(({ data, error }) =>
      setRuntime(error ? null : data)
    )
    api.fetchRealityKeys().then(({ data, error }) =>
      setKeys(error ? null : (data?.keys ?? []))
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
      setMsg({ ok: true, text: 'Config saved; runtime config regenerated and restarted.' })
      setText('')
      load()
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex justify-end">
        <button
          onClick={load}
          className="text-sm text-apple-blue hover:text-apple-blue-hover font-medium transition-colors"
        >
          Refresh
        </button>
      </div>
      <RealityKeysSection keys={keys} rotating={rotating} msg={keyMsg}
        onRotated={(ok, text) => {
          setKeyMsg({ ok, text })
          load()  // runtime config now carries the new key
        }}
        onRotating={setRotating}
      />
      <div className="grid md:grid-cols-2 gap-5">
        <JsonPanel
          title="Config"
          subtitle="the file you provide"
          value={config}
          empty="No config loaded yet."
        />
        <JsonPanel
          title="Runtime config"
          subtitle={subtitleFor(runtime)}
          value={runtime === null ? null : runtime?.config}
          empty="Not generated yet — no config loaded or last sync failed."
        />
      </div>
      <section className="bg-apple-card rounded-2xl p-5 shadow-sm border border-apple-border">
        <h2 className="text-sm font-semibold text-apple-muted uppercase tracking-wide mb-3">
          Replace config (paste full JSON)
        </h2>
        <textarea
          className="w-full h-48 bg-apple-bg border border-apple-border rounded-xl p-3 text-xs font-mono text-apple-text placeholder-apple-gray focus:outline-none focus:border-apple-blue focus:ring-2 focus:ring-apple-blue/10 transition-all resize-none"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder='{"inbounds": [...], "outbounds": [...], ...}'
          spellCheck={false}
        />
        <div className="flex items-center gap-3 mt-4">
          <button
            onClick={save}
            disabled={busy || !text.trim()}
            className="bg-apple-blue hover:bg-apple-blue-hover disabled:opacity-50 text-white px-5 py-2 rounded-full text-sm font-medium transition-colors shadow-sm"
          >
            {busy ? 'Saving…' : 'Save & Resync'}
          </button>
          {msg && (
            <p className={`text-sm ${msg.ok ? 'text-apple-green' : 'text-apple-red'}`}>
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
    <section className="bg-apple-card rounded-2xl p-5 shadow-sm border border-apple-border">
      <h2 className="text-sm font-semibold text-apple-muted uppercase tracking-wide mb-3">
        {title}
        {subtitle && (
          <span className="text-xs text-apple-muted/70 font-normal ml-2 normal-case">{subtitle}</span>
        )}
      </h2>
      {value === undefined ? (
        <p className="text-apple-muted text-sm">Loading…</p>
      ) : value === null ? (
        <p className="text-apple-muted text-sm">{empty}</p>
      ) : (
        <pre className="bg-apple-bg border border-apple-border rounded-xl p-3 text-xs overflow-auto max-h-72 text-apple-text">
          {JSON.stringify(value, null, 2)}
        </pre>
      )}
    </section>
  )
}

/** Subtitle for the runtime pane: its last-write time once known. */
function subtitleFor(runtime) {
  if (runtime?.generated_at) {
    return `regenerated ${new Date(runtime.generated_at * 1000).toLocaleString()}`
  }
  return 'what Xray reads'
}

/**
 * Panel-managed REALITY keys: one row per REALITY inbound showing its
 * derived public key and a Rotate action.
 *
 * Why inside ConfigPage: rotating must also refresh the runtime config
 * pane (it now carries the new private key), and the keys only exist in
 * the context of a loaded config — same lifecycle, same tab.
 */
function RealityKeysSection({ keys, rotating, msg, onRotated, onRotating }) {
  const rotate = async (target) => {
    const name = target === 'all' ? 'ALL REALITY inbounds' : `"${target}"`
    if (!window.confirm(
      `Rotate the REALITY key for ${name}? ` +
      'Clients using old links stop working until they re-import, and Xray restarts.'
    )) return
    onRotating(target)
    const { data, error } = target === 'all'
      ? await api.rotateAllRealityKeys()
      : await api.rotateRealityKey(target)
    onRotating(null)
    if (error) {
      onRotated(false, `Rotate failed: ${error}`)
    } else {
      const what = target === 'all' ? `${data.rotated.length} inbound(s)` : `"${data.inbound}"`
      onRotated(true, `Key rotated for ${what}; runtime config regenerated and Xray restarted.`)
    }
  }

  return (
    <section className="bg-apple-card rounded-2xl p-5 shadow-sm border border-apple-border">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-apple-muted uppercase tracking-wide">
          REALITY keys
          <span className="text-xs text-apple-muted/70 font-normal ml-2 normal-case">
            generated by the panel — the config's own privateKey is ignored
          </span>
        </h2>
        {keys?.length > 1 && (
          <button
            onClick={() => rotate('all')}
            disabled={rotating !== null}
            className="bg-apple-red/90 hover:bg-apple-red disabled:opacity-50 text-white px-4 py-1.5 rounded-full text-sm font-medium transition-colors shadow-sm"
          >
            {rotating === 'all' ? 'Rotating…' : 'Rotate all'}
          </button>
        )}
      </div>
      {msg && (
        <p className={`mb-3 text-sm ${msg.ok ? 'text-apple-green' : 'text-apple-red'}`}>
          {msg.text}
        </p>
      )}
      {keys === undefined ? (
        <p className="text-apple-muted text-sm">Loading…</p>
      ) : keys === null ? (
        <p className="text-apple-muted text-sm">No config loaded — nothing to rotate.</p>
      ) : keys.length === 0 ? (
        <p className="text-apple-muted text-sm">No REALITY inbounds in the config.</p>
      ) : (
        <div className="space-y-3">
          {keys.map((key) => (
            <RealityKeyRow key={key.inbound} row={key} rotating={rotating}
              onRotate={() => rotate(key.inbound)}
            />
          ))}
        </div>
      )}
    </section>
  )
}

/** One REALITY inbound row: tag, public key (copyable), key date, Rotate. */
function RealityKeyRow({ row, rotating, onRotate }) {
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(row.public_key)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      setCopied(false)
    }
  }

  return (
    <div className="border border-apple-border rounded-xl p-3 flex flex-wrap items-center gap-3">
      <span className="text-xs font-semibold text-apple-muted uppercase tracking-wide min-w-24">
        {row.inbound}
      </span>
      {row.public_key ? (
        <>
          <code className="bg-apple-gray-surface rounded-lg px-3 py-1.5 text-xs font-mono text-apple-text break-all flex-1 min-w-48">
            pbk: {row.public_key}
          </code>
          <button
            onClick={copy}
            className="bg-apple-gray-surface hover:bg-apple-border text-apple-text px-4 py-1.5 rounded-full text-sm font-medium transition-colors"
          >
            {copied ? 'Copied!' : 'Copy'}
          </button>
        </>
      ) : (
        <span className="text-sm text-apple-muted flex-1">
          Key pending — generated on the next sync.
        </span>
      )}
      <span className="text-xs text-apple-muted">
        {row.created_at ? `key from ${new Date(row.created_at * 1000).toLocaleString()}` : ''}
      </span>
      <button
        onClick={onRotate}
        disabled={rotating !== null}
        className="bg-apple-red/90 hover:bg-apple-red disabled:opacity-50 text-white px-4 py-1.5 rounded-full text-sm font-medium transition-colors shadow-sm"
      >
        {rotating === row.inbound ? 'Rotating…' : 'Rotate'}
      </button>
    </div>
  )
}
