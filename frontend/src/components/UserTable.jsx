/**
 * The user list: fetches nothing itself — App passes users + callbacks down.
 *
 * Why a dumb component: data ownership stays in App, so a refresh after
 * create/edit/delete automatically re-renders this table.
 */
export default function UserTable({ users, error, onAdd, onEdit, onShare, onDelete }) {
  if (error) {
    return <p className="text-apple-red text-sm">Failed to load users: {error}</p>
  }
  if (users === null) {
    return <p className="text-apple-muted text-sm">Loading users…</p>
  }
  return (
    <div className="space-y-4">
      <button
        onClick={onAdd}
        className="bg-apple-blue hover:bg-apple-blue-hover text-white px-5 py-2 rounded-full text-sm font-medium transition-colors shadow-sm"
      >
        + Add User
      </button>
      {users.length === 0 ? (
        <p className="text-apple-muted text-sm">No users yet.</p>
      ) : (
        <div className="bg-apple-card rounded-2xl shadow-sm border border-apple-border overflow-hidden">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="text-left text-apple-muted border-b border-apple-border bg-apple-gray-surface">
                <Th>Username</Th>
                <Th>Status</Th>
                <Th>Expire</Th>
                <Th>Inbounds</Th>
                <Th>Outbounds</Th>
                <Th>Note</Th>
                <Th>Actions</Th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.username} className="border-b border-apple-border last:border-b-0">
                  <Td className="font-mono text-apple-text">{u.username}</Td>
                  <Td>
                    <StatusBadge status={u.status} />
                  </Td>
                  <Td className="text-apple-muted">{fmtExpire(u.expire)}</Td>
                  <Td className="text-apple-muted">{u.allowed_inbounds.join(', ') || '—'}</Td>
                  <Td className="text-apple-muted">{u.allowed_outbounds.join(', ') || '—'}</Td>
                  <Td className="max-w-40 truncate text-apple-muted" title={u.note || ''}>
                    {u.note || '—'}
                  </Td>
                  <Td>
                    <button
                      onClick={() => onEdit(u)}
                      className="text-apple-blue hover:text-apple-blue-hover font-medium mr-4 transition-colors"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => onShare(u)}
                      className="text-apple-green hover:opacity-80 font-medium mr-4 transition-opacity"
                    >
                      Share
                    </button>
                    <button
                      onClick={() => onDelete(u.username)}
                      className="text-apple-red hover:text-[#d93025] font-medium transition-colors"
                    >
                      Delete
                    </button>
                  </Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

/** Consistent cell padding for header and body cells. */
function Th({ children }) {
  return <th className="py-3 pr-4 pl-4 font-medium text-xs uppercase tracking-wide">{children}</th>
}
function Td({ children, className = '', ...rest }) {
  return (
    <td className={`py-3 pr-4 pl-4 ${className}`} {...rest}>
      {children}
    </td>
  )
}

/** Green "active" / gray "disabled" pill. */
function StatusBadge({ status }) {
  const cls =
    status === 'active'
      ? 'bg-[#e9f9ee] text-apple-green'
      : 'bg-apple-gray-surface text-apple-muted'
  return (
    <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${cls}`}>
      {status}
    </span>
  )
}

/** Human-readable expiry: null = unset, 0 = never, otherwise a date. */
function fmtExpire(expire) {
  if (expire == null) return '—'
  if (expire === 0) return 'never'
  return new Date(expire * 1000).toLocaleDateString()
}
