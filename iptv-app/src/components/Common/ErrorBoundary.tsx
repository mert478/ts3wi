import { Component, type ReactNode } from 'react'

export default class ErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
  constructor(props: any) {
    super(props)
    this.state = { hasError: false }
  }
  static getDerivedStateFromError() { return { hasError: true } }
  componentDidCatch(err: any) { console.error(err) }
  render() {
    if (this.state.hasError) return <div className="p-4 text-red-300">Bir hata oluştu.</div>
    return this.props.children
  }
}