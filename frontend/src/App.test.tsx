import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { Segment } from '@/lib/types'
import App from '@/App'

const uploadedFile = new File(['video-bytes'], 'lecture.mp4', { type: 'video/mp4' })
const queriedSegments: Segment[] = [{ start: 12, end: 28 }]

vi.mock('@/pages/UploadPage', () => ({
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

vi.mock('@/pages/QueryPage', () => ({
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

vi.mock('@/pages/PlayerPage', () => ({
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

describe('App', () => {
  it('moves through upload, query, and player states and can reset', async () => {
    const user = userEvent.setup()

    render(<App />)

    expect(screen.getByRole('button', { name: 'Complete upload' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Complete upload' }))
    expect(screen.getByRole('button', { name: 'Complete query' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Complete query' }))

    expect(screen.getByText('vid_app')).toBeInTheDocument()
    expect(screen.getByText('lecture.mp4')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Back to upload' }))

    expect(screen.getByRole('button', { name: 'Complete upload' })).toBeInTheDocument()
  })
})
