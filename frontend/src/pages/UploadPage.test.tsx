import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { uploadVideo } from '@/lib/api.ts'
import { UploadPage } from '@/pages/UploadPage.tsx'

vi.mock('@/lib/api.ts', () => ({
  uploadVideo: vi.fn(),
}))

describe('UploadPage', () => {
  it('does not upload when the form is submitted without a file', () => {
    render(<UploadPage userId="anonymous" onUploadComplete={vi.fn()} onBack={vi.fn()} />)

    fireEvent.submit(screen.getByRole('button', { name: 'Upload and continue' }).closest('form') as HTMLFormElement)

    expect(uploadVideo).not.toHaveBeenCalled()
  })

  it('clears the selected file when the file picker is emptied', async () => {
    const user = userEvent.setup()
    const file = new File(['video-bytes'], 'lecture.mp4', { type: 'video/mp4' })

    render(<UploadPage userId="anonymous" onUploadComplete={vi.fn()} onBack={vi.fn()} />)

    const input = screen.getByLabelText('Video file')
    const submitButton = screen.getByRole('button', { name: 'Upload and continue' })

    await user.upload(input, file)
    expect(submitButton).toBeEnabled()

    fireEvent.change(input, { target: { files: [] } })

    expect(submitButton).toBeDisabled()
  })

  it('uploads the selected file and reports completion', async () => {
    const user = userEvent.setup()
    const onUploadComplete = vi.fn()
    const file = new File(['video-bytes'], 'lecture.mp4', { type: 'video/mp4' })
    let resolveUpload: ((value: { videoId: string }) => void) | undefined

    vi.mocked(uploadVideo).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveUpload = resolve
        }),
    )

    render(<UploadPage userId="anonymous" onUploadComplete={onUploadComplete} onBack={vi.fn()} />)

    const submitButton = screen.getByRole('button', { name: 'Upload and continue' })
    expect(submitButton).toBeDisabled()

    await user.upload(screen.getByLabelText('Video file'), file)
    expect(submitButton).toBeEnabled()

    await user.click(submitButton)

    expect(uploadVideo).toHaveBeenCalledWith(file, 'anonymous', expect.any(Function))
    expect(screen.getByRole('button', { name: 'Uploading…' })).toBeDisabled()

    resolveUpload?.({ videoId: 'vid_upload' })

    await waitFor(() => {
      expect(onUploadComplete).toHaveBeenCalledWith('vid_upload', file)
    })

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Upload and continue' })).toBeEnabled()
    })
  })
})
