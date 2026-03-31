import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { Segment } from '@/lib/types.ts'
import { getSession, signOut } from '@/lib/auth.ts'
import App from '@/App.tsx'

const uploadedFile = new File(['video-bytes'], 'lecture.mp4', { type: 'video/mp4' })
const queriedSegments: Segment[] = [
  { segmentId: 'seg-1', start: 12, end: 28, idx: 0, text: 'Neural networks', similarity: 0.9 },
]

vi.mock('@/lib/auth.ts', () => ({
  getSession: vi.fn(),
  signOut: vi.fn(),
}))

vi.mock('@/lib/api.ts', () => ({
  registerUser: vi.fn().mockResolvedValue(undefined),
  listVideos: vi.fn().mockResolvedValue({ videos: [] }),
}))

vi.mock('@/pages/DashboardPage.tsx', () => ({
  DashboardPage: ({
    onUploadNew,
    onSelectVideo,
  }: {
    onUploadNew: () => void
    onSelectVideo: (video: { lectureId: string; videoId: string; title: string; ingestedAt: string; playbackUrl: string | null }) => void
  }) => (
    <>
      <button type="button" onClick={onUploadNew}>Go to upload</button>
      <button
        type="button"
        onClick={() => onSelectVideo({ lectureId: 'lec-1', videoId: 'vid_existing', title: 'Existing', ingestedAt: '', playbackUrl: null })}
      >
        Select video
      </button>
    </>
  ),
}))

vi.mock('@/pages/UploadPage.tsx', () => ({
  UploadPage: ({
    onUploadComplete,
  }: {
    onUploadComplete: (videoId: string, file: File) => void
  }) => (
    <button type="button" onClick={() => onUploadComplete('vid_app', uploadedFile)}>
      Complete upload
    </button>
  ),
}))

vi.mock('@/pages/ProcessingPage.tsx', () => ({
  ProcessingPage: ({
    onProcessingComplete,
  }: {
    onProcessingComplete: (video: { lectureId: string; videoId: string; title: string; ingestedAt: string; playbackUrl: string | null }) => void
  }) => (
    <button
      type="button"
      onClick={() => onProcessingComplete({ lectureId: 'lec-1', videoId: 'vid_app', title: 'lecture.mp4', ingestedAt: '', playbackUrl: null })}
    >
      Complete processing
    </button>
  ),
}))

vi.mock('@/pages/QueryPage.tsx', () => ({
  QueryPage: ({
    onQueryComplete,
  }: {
    onQueryComplete: (segments: Segment[]) => void
  }) => (
    <button type="button" onClick={() => onQueryComplete(queriedSegments)}>
      Complete query
    </button>
  ),
}))

vi.mock('@/pages/PlayerPage.tsx', () => ({
  PlayerPage: ({
    videoId,
    file,
    onBackToUpload,
  }: {
    videoId: string
    file: File
    onBackToUpload: () => void
  }) => (
    <section>
      <p>{videoId}</p>
      <p>{file.name}</p>
      <button type="button" onClick={onBackToUpload}>
        Back to upload
      </button>
    </section>
  ),
}))

vi.mock('@/pages/AuthPage.tsx', () => ({
  AuthPage: ({ onSignIn }: { onSignIn: (session: { email: string; idToken: string }) => void }) => (
    <button type="button" onClick={() => onSignIn({ email: 'test@example.com', idToken: 'tok' })}>
      Sign in
    </button>
  ),
}))

describe('App', () => {
  it('shows the loading spinner while the session is resolving', () => {
    vi.mocked(getSession).mockImplementation(() => new Promise(() => {}))
    render(<App />)
    expect(screen.getByText('Loading…')).toBeInTheDocument()
  })

  it('shows the AuthPage when there is no session', async () => {
    vi.mocked(getSession).mockResolvedValue(null)
    render(<App />)
    expect(await screen.findByRole('button', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('transitions to the dashboard after signing in via AuthPage', async () => {
    const user = userEvent.setup()
    vi.mocked(getSession).mockResolvedValue(null)
    render(<App />)
    await user.click(await screen.findByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('button', { name: 'Go to upload' })).toBeInTheDocument()
  })

  it('calls signOut and returns to the AuthPage when the Sign out button is clicked', async () => {
    const user = userEvent.setup()
    vi.mocked(getSession).mockResolvedValue({ email: 'test@example.com', idToken: 'tok' })
    render(<App />)
    await screen.findByRole('button', { name: 'Go to upload' })
    await user.click(screen.getByRole('button', { name: 'Sign out' }))
    expect(signOut).toHaveBeenCalled()
    expect(await screen.findByRole('button', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('navigates from dashboard to query when an existing video is selected', async () => {
    const user = userEvent.setup()
    vi.mocked(getSession).mockResolvedValue({ email: 'test@example.com', idToken: 'tok' })
    render(<App />)

    const selectVideo = await screen.findByRole('button', { name: 'Select video' })
    await user.click(selectVideo)

    expect(screen.getByRole('button', { name: 'Complete query' })).toBeInTheDocument()
  })

  it('moves through upload, processing, query, and player states and can reset', async () => {
    const user = userEvent.setup()
    vi.mocked(getSession).mockResolvedValue({ email: 'test@example.com', idToken: 'tok' })

    render(<App />)

    // Wait for auth to resolve and the dashboard to render
    await screen.findByRole('button', { name: 'Go to upload' })

    await user.click(screen.getByRole('button', { name: 'Go to upload' }))
    expect(screen.getByRole('button', { name: 'Complete upload' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Complete upload' }))
    expect(screen.getByRole('button', { name: 'Complete processing' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Complete processing' }))
    expect(screen.getByRole('button', { name: 'Complete query' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Complete query' }))

    expect(screen.getByText('vid_app')).toBeInTheDocument()
    expect(screen.getByText('lecture.mp4')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Back to upload' }))

    expect(screen.getByRole('button', { name: 'Go to upload' })).toBeInTheDocument()
  })
})
