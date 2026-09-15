import { useEffect, useState } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import * as api from '../api'

/**
 * Modal showing VLESS share links for a single user.
 *
 * Why this fetches its own data: share links are a read-only view; App
 * does not need to own this state. This mirrors ConfigPage's approach.
 */
export default function ShareModal({ user, onClose }) {
  const [links, setLinks] = useState([])
  const [warnings, setWarnings] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [copied, setCopied] = useState(null)
  const [qrFor, setQrFor] = useState(null)

  useEffect(() => {
    let cancelled = false
    api.fetchUserLinks(user.username).then(({ data, error }) => {
      if (cancelled) return
      if (error) {
        setError(error)
      } else {
        setLinks(data.links || [])
        setWarnings(data.warnings || [])
      }
      setLoading(false)
    })
    return () => { cancelled = true }
  }, [user.username])

  const copy = async (text, key) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(key)
      setTimeout(() => setCopied(null), 1500)
    } catch {
      setCopied('failed')
      setTimeout(() => setCopied(null), 1500)
    }
  }

  const copyAll = () => {
    if (!links.length) return
    copy(links.map((l) => l.uri).join('\n'), 'all')
  }

  return (
    <div
      className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4 z-20"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-apple-card rounded-2xl p-6 w-full max-w-2xl max-h-[85vh] overflow-y-auto shadow-xl border border-apple-border space-y-5"
      >
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-apple-text">
            Share links for <span className="font-mono">{user.username}</span>
          </h2>
          <button
            onClick={onClose}
            className="text-apple-muted hover:text-apple-text text-sm font-medium"
          >
            Close
          </button>
        </div>

        {loading && <p className="text-apple-muted text-sm">Loading links…</p>}
        {error && (
          <p className="bg-[#ffecea] border border-[#ff453a]/20 text-apple-red rounded-xl px-4 py-2 text-sm">
            {error}
          </p>
        )}
        {warnings.length > 0 && (
          <div className="bg-[#fff9e6] border border-[#ffcc00]/30 rounded-xl px-4 py-2 space-y-1">
            {warnings.map((warning, idx) => (
              <p key={idx} className="text-amber-700 text-sm">
                {warning}
              </p>
            ))}
          </div>
        )}

        {!loading && !error && links.length === 0 && (
          <p className="text-apple-muted text-sm">No shareable links.</p>
        )}

        {links.length > 0 && (
          <>
            <div className="space-y-3">
              {links.map((link) => {
                const linkKey = `${link.inbound}-${link.outbound}`
                return (
                <div
                  key={linkKey}
                  className="border border-apple-border rounded-xl p-3 space-y-2"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-apple-muted uppercase tracking-wide">
                      {link.inbound} → {link.outbound}
                    </span>
                    <span className="text-xs font-mono text-apple-muted">
                      {link.email}
                    </span>
                  </div>
                  <div className="bg-apple-gray-surface rounded-lg px-3 py-2 break-all text-xs font-mono text-apple-text">
                    {link.uri}
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => copy(link.uri, linkKey)}
                      className="bg-apple-blue hover:bg-apple-blue-hover text-white px-4 py-1.5 rounded-full text-sm font-medium transition-colors"
                    >
                      {copied === linkKey ? 'Copied!' : 'Copy'}
                    </button>
                    <button
                      onClick={() => setQrFor(qrFor === link.uri ? null : link.uri)}
                      className="bg-apple-gray-surface hover:bg-apple-border text-apple-text px-4 py-1.5 rounded-full text-sm font-medium transition-colors"
                    >
                      {qrFor === link.uri ? 'Hide QR' : 'QR'}
                    </button>
                  </div>
                  {qrFor === link.uri && (
                    <div className="flex justify-center pt-2">
                      <QRCodeSVG value={link.uri} size={176} marginSize={2} />
                    </div>
                  )}
                </div>
              )})}
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={copyAll}
                className="bg-apple-blue hover:bg-apple-blue-hover text-white px-5 py-2 rounded-full text-sm font-medium transition-colors shadow-sm"
              >
                {copied === 'all' ? 'Copied!' : 'Copy all'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
