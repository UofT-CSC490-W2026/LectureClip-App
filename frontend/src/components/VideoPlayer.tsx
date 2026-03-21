import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react'
import type { Segment } from '../lib/types.ts'

type VideoPlayerProps = {
  src: string
  segments: Segment[]
  onPlaybackTimeUpdate?: (seconds: number) => void
}

export type VideoPlayerHandle = {
  pause: () => void
}

function formatTime(seconds: number) {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const remainingSeconds = Math.floor(seconds % 60)
  return [
    hours.toString().padStart(2, '0'),
    minutes.toString().padStart(2, '0'),
    remainingSeconds.toString().padStart(2, '0'),
  ].join(':')
}

export const VideoPlayer = forwardRef<VideoPlayerHandle, VideoPlayerProps>(function VideoPlayer(
  { src, segments, onPlaybackTimeUpdate },
  ref,
) {
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const programmaticSeekTargetRef = useRef<number | null>(null)
  const currentSegmentIndexRef = useRef<number | null>(segments.length > 0 ? 0 : null)
  const playbackModeRef = useRef<'segments' | 'free'>('segments')
  const [currentSegmentIndex, setCurrentSegmentIndex] = useState<number | null>(
    segments.length > 0 ? 0 : null,
  )
  const [, setPlaybackMode] = useState<'segments' | 'free'>('segments')

  function updateCurrentSegmentIndex(index: number | null) {
    currentSegmentIndexRef.current = index
    setCurrentSegmentIndex(index)
  }

  function updatePlaybackMode(mode: 'segments' | 'free') {
    playbackModeRef.current = mode
    setPlaybackMode(mode)
  }

  function reportPlaybackTime(seconds: number) {
    onPlaybackTimeUpdate?.(seconds)
  }

  useImperativeHandle(ref, () => ({
    pause() {
      videoRef.current?.pause()
    },
  }))

  useEffect(() => {
    updateCurrentSegmentIndex(segments.length > 0 ? 0 : null)
    updatePlaybackMode('segments')
    programmaticSeekTargetRef.current = null
    onPlaybackTimeUpdate?.(0)
  }, [onPlaybackTimeUpdate, src, segments])

  function getSegmentIndexForTime(time: number) {
    const index = segments.findIndex((segment) => time >= segment.start && time < segment.end)
    return index >= 0 ? index : null
  }

  function startSegment(index: number) {
    const video = videoRef.current
    const segment = segments[index]

    if (!video || !segment) return

    updatePlaybackMode('segments')
    updateCurrentSegmentIndex(index)
    programmaticSeekTargetRef.current = segment.start
    video.currentTime = segment.start
    reportPlaybackTime(segment.start)
    void video.play()
  }

  function handleLoadedMetadata() {
    if (segments.length === 0) {
      reportPlaybackTime(videoRef.current?.currentTime ?? 0)
      return
    }

    startSegment(0)
  }

  function handleSeeking() {
    const video = videoRef.current

    if (!video) return

    reportPlaybackTime(video.currentTime)

    const programmaticSeekTarget = programmaticSeekTargetRef.current

    if (
      programmaticSeekTarget !== null &&
      Math.abs(video.currentTime - programmaticSeekTarget) < 0.25
    ) {
      programmaticSeekTargetRef.current = null
      return
    }

    programmaticSeekTargetRef.current = null
    updatePlaybackMode('free')
    updateCurrentSegmentIndex(getSegmentIndexForTime(video.currentTime))
  }

  function handleTimeUpdate() {
    const video = videoRef.current
    if (!video) return

    reportPlaybackTime(video.currentTime)

    if (video.seeking && programmaticSeekTargetRef.current === null) {
      updatePlaybackMode('free')
      updateCurrentSegmentIndex(getSegmentIndexForTime(video.currentTime))
      return
    }

    if (playbackModeRef.current === 'segments' && currentSegmentIndexRef.current !== null) {
      const segment = segments[currentSegmentIndexRef.current]
      if (!segment || video.currentTime < segment.end) return

      const nextIndex = currentSegmentIndexRef.current + 1

      if (nextIndex >= segments.length) {
        video.pause()
        return
      }

      startSegment(nextIndex)
      return
    }

    const activeSegmentIndex = getSegmentIndexForTime(video.currentTime)
    if (activeSegmentIndex !== currentSegmentIndexRef.current) {
      updateCurrentSegmentIndex(activeSegmentIndex)
    }
  }

  return (
    <div className="video-player">
      <video
        ref={videoRef}
        src={src}
        controls
        autoPlay
        onLoadedMetadata={handleLoadedMetadata}
        onSeeking={handleSeeking}
        onTimeUpdate={handleTimeUpdate}
      />

      <p className="segment-meta">
        {currentSegmentIndex === null
          ? 'Current position is outside the highlighted segments.'
          : `Segment ${currentSegmentIndex + 1} of ${segments.length}`}
      </p>

      <div>
        <h3>Segments</h3>
        <ul className="segment-list">
          {segments.map((segment, index) => (
            <li
              key={`${segment.start}-${segment.end}`}
              className={index === currentSegmentIndex ? 'active' : ''}
            >
              <button type="button" className="segment-button" onClick={() => startSegment(index)}>
                <span>Segment {index + 1}</span>
                <span>
                  {formatTime(segment.start)} - {formatTime(segment.end)}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
})
