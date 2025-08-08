import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { storage } from '../../services/storage'

export default function AuthGuard() {
  const location = useLocation()
  const creds = storage.getCredentials()
  if (!creds) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }
  return <Outlet />
}