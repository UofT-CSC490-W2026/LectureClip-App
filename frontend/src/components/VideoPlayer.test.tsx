import { createRef } from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { VideoPlayer } from '@/components/VideoPlayer'
import type { VideoPlayerHandle } from '@/components/VideoPlayer'

const segments = [
  { start: 5, end: 10 },
  { start: 20, end: 30 },
]

describe('VideoPlayer', () => {
  it('exposes an imperative pause handle', () => {
    const ref = createRef<VideoPlayerHandle>()

    render(<VideoPlayer ref={ref} src="blob:mock-video" segments={segments} />)

    ref.current?.pause()

    expect(HTMLMediaElement.prototype.pause).toHaveBeenCalled()
  })

  it('reports the current time without forcing segment playback when no segments are provided', () => {
    const onPlaybackTimeUpdate = vi.fn()

    render(<VideoPlayer src="blob:mock-video" segments={[]} onPlaybackTimeUpdate={onPlaybackTimeUpdate} />)

    const video = document.querySelector('video') as HTMLVideoElement
    video.currentTime = 7

    fireEvent.loadedMetadata(video)

    expect(onPlaybackTimeUpdate).toHaveBeenCalledWith(7)
    expect(
      screen.getByText('Current position is outside the highlighted segments.'),
    ).toBeInTheDocument()
  })

  it('starts playback from the first segment when metadata loads', () => {
    const onPlaybackTimeUpdate = vi.fn()

    render(<VideoPlayer src="blob:mock-video" segments={segments} onPlaybackTimeUpdate={onPlaybackTimeUpdate} />)

    const video = document.querySelector('video')
    expect(video).not.toBeNull()

    fireEvent.loadedMetadata(video as HTMLVideoElement)

    expect((video as HTMLVideoElement).currentTime).toBe(5)
    expect(HTMLMediaElement.prototype.play).toHaveBeenCalled()
    expect(onPlaybackTimeUpdate).toHaveBeenCalledWith(5)
    expect(screen.getByText('Segment 1 of 2')).toBeInTheDocument()
  })

  it('ignores the seeking event triggered by a programmatic segment jump', () => {
    const onPlaybackTimeUpdate = vi.fn()

    render(<VideoPlayer src="blob:mock-video" segments={segments} onPlaybackTimeUpdate={onPlaybackTimeUpdate} />)

    const video = document.querySelector('video') as HTMLVideoElement

    fireEvent.loadedMetadata(video)
    fireEvent.seeking(video)

    expect(onPlaybackTimeUpdate).toHaveBeenLastCalledWith(5)
    expect(screen.getByText('Segment 1 of 2')).toBeInTheDocument()
  })

  it('jumps to the chosen segment when a segment button is clicked', async () => {
    const user = userEvent.setup()

    render(<VideoPlayer src="blob:mock-video" segments={segments} />)

    const video = document.querySelector('video')
    expect(video).not.toBeNull()

    await user.click(screen.getByRole('button', { name: /Segment 2/i }))

    expect((video as HTMLVideoElement).currentTime).toBe(20)
    expect(screen.getByText('Segment 2 of 2')).toBeInTheDocument()
  })

  it('advances to the next segment when the current one ends', () => {
    render(<VideoPlayer src="blob:mock-video" segments={segments} />)

    const video = document.querySelector('video') as HTMLVideoElement

    fireEvent.loadedMetadata(video)
    video.currentTime = 10
    fireEvent.timeUpdate(video)

    expect(video.currentTime).toBe(20)
    expect(screen.getByText('Segment 2 of 2')).toBeInTheDocument()
  })

  it('keeps playing the current segment before its end time', () => {
    render(<VideoPlayer src="blob:mock-video" segments={segments} />)

    const video = document.querySelector('video') as HTMLVideoElement

    fireEvent.loadedMetadata(video)
    video.currentTime = 7
    fireEvent.timeUpdate(video)

    expect(video.currentTime).toBe(7)
    expect(screen.getByText('Segment 1 of 2')).toBeInTheDocument()
  })

  it('pauses once the final highlighted segment finishes', () => {
    render(<VideoPlayer src="blob:mock-video" segments={segments} />)

    const video = document.querySelector('video') as HTMLVideoElement

    fireEvent.loadedMetadata(video)
    video.currentTime = 10
    fireEvent.timeUpdate(video)
    video.currentTime = 30
    fireEvent.timeUpdate(video)

    expect(HTMLMediaElement.prototype.pause).toHaveBeenCalled()
  })

  it('switches to free playback mode when the user seeks outside the highlighted segments', () => {
    const onPlaybackTimeUpdate = vi.fn()

    render(<VideoPlayer src="blob:mock-video" segments={segments} onPlaybackTimeUpdate={onPlaybackTimeUpdate} />)

    const video = document.querySelector('video') as HTMLVideoElement

    fireEvent.loadedMetadata(video)
    video.currentTime = 40
    fireEvent.seeking(video)

    expect(onPlaybackTimeUpdate).toHaveBeenCalledWith(40)
    expect(
      screen.getByText('Current position is outside the highlighted segments.'),
    ).toBeInTheDocument()
  })

  it('tracks the active segment during free playback time updates', () => {
    render(<VideoPlayer src="blob:mock-video" segments={segments} />)

    const video = document.querySelector('video') as HTMLVideoElement

    fireEvent.loadedMetadata(video)
    video.currentTime = 40
    fireEvent.seeking(video)

    Object.defineProperty(video, 'seeking', {
      configurable: true,
      value: true,
    })
    video.currentTime = 6
    fireEvent.timeUpdate(video)

    expect(screen.getByText('Segment 1 of 2')).toBeInTheDocument()

    Object.defineProperty(video, 'seeking', {
      configurable: true,
      value: false,
    })
    video.currentTime = 21
    fireEvent.timeUpdate(video)

    expect(screen.getByText('Segment 2 of 2')).toBeInTheDocument()
  })

  it('does not change the highlighted segment when free playback stays in the same range', () => {
    render(<VideoPlayer src="blob:mock-video" segments={segments} />)

    const video = document.querySelector('video') as HTMLVideoElement

    fireEvent.loadedMetadata(video)
    video.currentTime = 40
    fireEvent.seeking(video)

    Object.defineProperty(video, 'seeking', {
      configurable: true,
      value: false,
    })
    video.currentTime = 41
    fireEvent.timeUpdate(video)

    expect(
      screen.getByText('Current position is outside the highlighted segments.'),
    ).toBeInTheDocument()
  })
})
