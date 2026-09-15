import { useCallback, useEffect, useState } from 'react'
import * as api from './api'
import StatusBar from './components/StatusBar'
import UserTable from './components/UserTable'
import UserForm from './components/UserForm'
import ConfigPage from './components/ConfigPage'
import ShareModal from './components/ShareModal'

/**
 * Root component: owns all shared state (users, status, config metadata)
 * and coordinates refreshes after every mutation.
 *
 * Why the state lives here: UserTable, UserForm, and StatusBar all need the
 * same data; lifting it to the common parent avoids duplicate fetches.
 */
export default function App() {
  const [tab, setTab] = useState('users')
  const [inbounds, setInbounds] = useState([])
  const [outbounds, setOutbounds] = useState([])
  const [users, setUsers] = useState(null) // null = still loading
  const [usersError, setUsersError] = useState(null)
  const [status, setStatus] = useState(null)
  // undefined = form closed, null = create mode, object = edit mode
  const [formTarget, setFormTarget] = useState(undefined)
  const [shareTarget, setShareTarget] = useState(undefined)
  const [notice, setNotice] = useState(null)

  useEffect(() => {
    api.fetchInbounds().then(({ data }) => data && setInbounds(data))
    api.fetchOutbounds().then(({ data }) => data && setOutbounds(data))
  }, [])

  const refresh = useCallback(async () => {
    const [u, s] = await Promise.all([api.fetchUsers(), api.fetchStatus()])
    setUsers(u.data)
    setUsersError(u.error)
    if (s.data) setStatus(s.data)
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const onSaved = () => {
    setFormTarget(undefined)
    refresh()
  }

  const onDelete = async (username) => {
    if (!window.confirm(`Delete user "${username}"?`)) return
    const { error } = await api.deleteUser(username)
    if (error) setNotice(`Delete failed: ${error}`)
    else { setNotice(null); refresh() }
  }

  return (
    <div className="max-w-5xl mx-auto p-4 sm:p-6 space-y-5">
      <StatusBar status={status} />
      <nav className="flex gap-2">
        <TabButton label="Users" active={tab === 'users'} onClick={() => setTab('users')} />
        <TabButton label="Config" active={tab === 'config'} onClick={() => setTab('config')} />
      </nav>
      {notice && (
        <p className="bg-[#ffecea] border border-[#ff453a]/20 text-[#ff3b30] rounded-xl px-4 py-2.5 text-sm font-medium">
          {notice}
        </p>
      )}
      {tab === 'users' ? (
        <UserTable
          users={users}
          error={usersError}
          onAdd={() => setFormTarget(null)}
          onEdit={setFormTarget}
          onShare={setShareTarget}
          onDelete={onDelete}
        />
      ) : (
        <ConfigPage />
      )}
      {formTarget !== undefined && (
        <UserForm
          target={formTarget}
          inbounds={inbounds}
          outbounds={outbounds}
          onClose={() => setFormTarget(undefined)}
          onSaved={onSaved}
        />
      )}
      {shareTarget !== undefined && (
        <ShareModal
          user={shareTarget}
          onClose={() => setShareTarget(undefined)}
        />
      )}
    </div>
  )
}

/** A single tab switcher button with active-state styling. */
function TabButton({ label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`px-5 py-2 rounded-full text-sm font-medium transition-colors ${
        active
          ? 'bg-apple-blue text-white shadow-sm'
          : 'bg-apple-card text-apple-muted hover:bg-apple-gray-surface hover:text-apple-text'
      }`}
    >
      {label}
    </button>
  )
}
