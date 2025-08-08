import { createElement } from 'react'
import { createRoutesFromElements, Route } from 'react-router-dom'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Movies from './pages/Movies'
import Series from './pages/Series'
import LiveTV from './pages/LiveTV'
import Settings from './pages/Settings'
import AppLayout from './components/Layout/AppLayout'
import AuthGuard from './components/Auth/AuthGuard'

export const routes = createRoutesFromElements(
  <>
    <Route path="/login" element={createElement(Login)} />
    <Route element={createElement(AuthGuard)}>
      <Route element={createElement(AppLayout)}>
        <Route index element={createElement(Dashboard)} />
        <Route path="movies" element={createElement(Movies)} />
        <Route path="series" element={createElement(Series)} />
        <Route path="livetv" element={createElement(LiveTV)} />
        <Route path="settings" element={createElement(Settings)} />
      </Route>
    </Route>
  </>
)