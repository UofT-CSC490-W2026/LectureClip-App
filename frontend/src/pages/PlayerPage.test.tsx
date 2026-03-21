import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { getTranscript, queryVideo } from '@/lib/api'
import { PlayerPage } from '@/pages/PlayerPage'

const pauseSpy = vi.fn()

vi.mock('@/lib/api', () => ({
  getTranscript: vi.fn(),
  queryVideo: vi.fn(),
}))

vi.mock('@/components/VideoPlayer', async () => {
  const React = await import('react')

  return {
    VideoPlayer: React.forwardRef(function MockVideoPlayer(
      props: {
        src: string
        segments: { start: number; end: number }[]
        onPlaybackTimeUpdate?: (seconds: number) => void
      },
      ref: React.ForwardedRef<{ pause: () => void }>,
    ) {
      React.useImperativeHandle(ref, () => ({
        pause: pauseSpy,
      }))

      return (
        <div>
          <p>{props.src}</p>
          <p>Segment count: {props.segments.length}</p>
          <button type="button" onClick={() => props.onPlaybackTimeUpdate?.(47)}>
            Advance playback
          </button>
        </div>
      )
    }),
  }
})

describe('PlayerPage', () => {
  it('loads transcript data, highlights the active transcript segment, and revokes the object URL', async () => {
    vi.mocked(getTranscript).mockResolvedValue({
      transcript: [
        { start: 0, end: 10, speaker: 'Speaker', text: 'Intro' },
        { start: 46, end: 58, speaker: 'Speaker', text: 'Backpropagation section' },
      ],
    })

    const file = new File(['video-bytes'], 'lecture.mp4', { type: 'video/mp4' })
    const { unmount } = render(
      <PlayerPage
        videoId="vid_player"
        file={file}
        segments={[
          { start: 12, end: 28 },
          { start: 46, end: 64 },
        ]}
        onQueryComplete={vi.fn()}
        onBackToUpload={vi.fn()}
      />,
    )

    expect(screen.getByText('Loading transcript...')).toBeInTheDocument()
    expect(getTranscript).toHaveBeenCalledWith('vid_player')
    expect(URL.createObjectURL).toHaveBeenCalledWith(file)

    const transcriptEntry = await screen.findByText('Backpropagation section')

    await userEvent.setup().click(screen.getByRole('button', { name: 'Advance playback' }))

    await waitFor(() => {
      expect(transcriptEntry.closest('li')).toHaveClass('active')
    })

    expect(screen.getByText('00:00:47')).toBeInTheDocument()
    expect(HTMLElement.prototype.scrollIntoView).toHaveBeenCalled()

    unmount()

    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock-video')
  })

  it('submits a trimmed follow-up query and can pause the player before returning to upload', async () => {
    const user = userEvent.setup()
    const onQueryComplete = vi.fn()
    const onBackToUpload = vi.fn()
    const nextSegments = [{ start: 88, end: 102 }]

    vi.mocked(getTranscript).mockResolvedValue({ transcript: [] })
    vi.mocked(queryVideo).mockResolvedValue({ segments: nextSegments })

    render(
      <PlayerPage
        videoId="vid_player"
        file={new File(['video-bytes'], 'lecture.mp4', { type: 'video/mp4' })}
        segments={[{ start: 12, end: 28 }]}
        onQueryComplete={onQueryComplete}
        onBackToUpload={onBackToUpload}
      />,
    )

    await screen.findByText('No transcript available for this video yet.')

    const updateButton = screen.getByRole('button', { name: 'Update query' })
    expect(updateButton).toBeDisabled()

    await user.type(screen.getByLabelText('Try a different query'), '  gradient descent  ')
    expect(updateButton).toBeEnabled()

    await user.click(updateButton)

    await waitFor(() => {
      expect(queryVideo).toHaveBeenCalledWith('vid_player', 'gradient descent')
    })

    expect(onQueryComplete).toHaveBeenCalledWith(nextSegments)

    await user.click(screen.getByRole('button', { name: 'Upload a different video' }))

    expect(pauseSpy).toHaveBeenCalled()
    expect(onBackToUpload).toHaveBeenCalled()
  })
})
