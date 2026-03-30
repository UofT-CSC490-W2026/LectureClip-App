import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react'
import type { Segment } from '@/lib/types.ts'
import { Button } from '@/components/ui/button.tsx'
import { Badge } from '@/components/ui/badge.tsx'
import { cn } from '@/lib/utils.ts'

type VideoPlayerProps = {
  src: string
  segments: Segment[]
  onPlaybackTimeUpdate?: (seconds: number) => void
}

export type VideoPlayerHandle = {
  pause: () => void
  seekTo: (time: number) => void
}

function formatTime(seconds: number) {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  return [h, m, s].map((v) => String(v).padStart(2, '0')).join(':')
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
    pause() { videoRef.current?.pause() },
    seekTo(time: number) {
      const video = videoRef.current
      if (!video) return
      updatePlaybackMode('free')
      programmaticSeekTargetRef.current = time
      video.currentTime = time
      void video.play()
    },
  }))

  useEffect(() => {
    updateCurrentSegmentIndex(segments.length > 0 ? 0 : null)
    updatePlaybackMode('segments')
    programmaticSeekTargetRef.current = null
    onPlaybackTimeUpdate?.(0)
  }, [onPlaybackTimeUpdate, src, segments])

  function getSegmentIndexForTime(time: number) {
    const index = segments.findIndex((s) => time >= s.start && time < s.end)
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
    const target = programmaticSeekTargetRef.current
    if (target !== null && Math.abs(video.currentTime - target) < 0.25) {
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
      if (nextIndex >= segments.length) { video.pause(); return }
      startSegment(nextIndex)
      return
    }

    const activeIndex = getSegmentIndexForTime(video.currentTime)
    if (activeIndex !== currentSegmentIndexRef.current) updateCurrentSegmentIndex(activeIndex)
  }

  return (
    <div className="space-y-3">
      <video
        ref={videoRef}
        src={src}
        controls
        autoPlay
        className="w-full rounded-xl bg-black aspect-video"
        onLoadedMetadata={handleLoadedMetadata}
        onSeeking={handleSeeking}
        onTimeUpdate={handleTimeUpdate}
      />

      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">
          {currentSegmentIndex === null
            ? 'Outside highlighted segments'
            : `Segment ${currentSegmentIndex + 1} of ${segments.length}`}
        </span>
      </div>

      <div className="space-y-1.5">
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Segments</p>
        <div className="space-y-1">
          {segments.map((segment, index) => (
            <Button
              key={`${segment.start}-${segment.end}`}
              variant={index === currentSegmentIndex ? 'secondary' : 'ghost'}
              size="sm"
              className={cn(
                'w-full justify-between h-auto py-2',
                index === currentSegmentIndex && 'ring-1 ring-primary/30',
              )}
              onClick={() => startSegment(index)}
            >
              <span className="font-medium">Segment {index + 1}</span>
              <Badge variant="outline" className="ml-2 font-mono text-xs">
                {formatTime(segment.start)} – {formatTime(segment.end)}
              </Badge>
            </Button>
          ))}
        </div>
      </div>
    </div>
  )
})
