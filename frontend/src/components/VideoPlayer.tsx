import { useEffect, useRef, useState } from 'react'
import type { Segment } from '../lib/types'

type VideoPlayerProps = {
  src: string
  segments: Segment[]
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

export function VideoPlayer({ src, segments }: VideoPlayerProps) {
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

  useEffect(() => {
    updateCurrentSegmentIndex(segments.length > 0 ? 0 : null)
    updatePlaybackMode('segments')
    programmaticSeekTargetRef.current = null
  }, [src, segments])

  function getSegmentIndexForTime(time: number) {
    return segments.findIndex((segment) => time >= segment.start && time < segment.end)
  }

  function startSegment(index: number) {
    const video = videoRef.current
    const segment = segments[index]

    if (!video || !segment) return

    updatePlaybackMode('segments')
    updateCurrentSegmentIndex(index)
    programmaticSeekTargetRef.current = segment.start
    video.currentTime = segment.start
    void video.play()
  }

  function handleLoadedMetadata() {
    if (segments.length === 0) return
    startSegment(0)
  }

  function handleSeeking() {
    const video = videoRef.current

    if (!video) return

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

    const activeSegmentIndex = getSegmentIndexForTime(video.currentTime)
    if (activeSegmentIndex !== currentSegmentIndexRef.current) {
      updateCurrentSegmentIndex(activeSegmentIndex)
    }

    if (playbackModeRef.current !== 'segments' || currentSegmentIndexRef.current === null) return

    const segment = segments[currentSegmentIndexRef.current]
    if (!segment || video.currentTime < segment.end) return

    const nextIndex = currentSegmentIndexRef.current + 1

    if (nextIndex >= segments.length) {
      video.pause()
      video.currentTime = segment.end
      return
    }

    startSegment(nextIndex)
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
}
