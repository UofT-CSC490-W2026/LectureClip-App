import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { VideoPlayer } from '../components/VideoPlayer.tsx'
import type { VideoPlayerHandle } from '../components/VideoPlayer.tsx'
import { getTranscript, queryVideo } from '../lib/api.ts'
import type { Segment, TranscriptSegment, Video } from '../lib/types.ts'

type PlayerPageProps = {
  videoId: string
  file: File
  segments: Segment[]
  onQueryComplete: (segments: Segment[]) => void
  onBackToUpload: () => void
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

function getTranscriptIndexForTime(transcript: TranscriptSegment[], time: number) {
  const index = transcript.findIndex((segment) => time >= segment.start && time < segment.end)
  return index >= 0 ? index : null
}

export function PlayerPage({
  videoId,
  file,
  segments,
  onQueryComplete,
  onBackToUpload,
}: PlayerPageProps) {
  const [video, setVideo] = useState<Video | null>(null)
  const videoPlayerRef = useRef<VideoPlayerHandle | null>(null)
  const transcriptItemRefs = useRef<Array<HTMLElement | null>>([])
  const [query, setQuery] = useState('')
  const [isSearching, setIsSearching] = useState(false)
  const [transcript, setTranscript] = useState<TranscriptSegment[]>([])
  const [isTranscriptLoading, setIsTranscriptLoading] = useState(true)
  const [currentTime, setCurrentTime] = useState(0)

  useEffect(() => {
    const url = URL.createObjectURL(file)
    setVideo({ id: videoId, url })
    setCurrentTime(0)

    return () => {
      URL.revokeObjectURL(url)
    }
  }, [file, videoId])

  useEffect(() => {
    let isCancelled = false

    async function loadTranscript() {
      setIsTranscriptLoading(true)

      try {
        const { transcript: nextTranscript } = await getTranscript(videoId)
        if (!isCancelled) {
          setTranscript(nextTranscript)
        }
      } finally {
        if (!isCancelled) {
          setIsTranscriptLoading(false)
        }
      }
    }

    void loadTranscript()

    return () => {
      isCancelled = true
    }
  }, [videoId])

  const activeTranscriptIndex = getTranscriptIndexForTime(transcript, currentTime)

  useEffect(() => {
    if (activeTranscriptIndex === null) return

    transcriptItemRefs.current[activeTranscriptIndex]?.scrollIntoView({
      block: 'nearest',
      behavior: 'smooth',
    })
  }, [activeTranscriptIndex])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!query.trim()) return

    setIsSearching(true)

    try {
      const { segments: nextSegments } = await queryVideo(videoId, query.trim())
      onQueryComplete(nextSegments)
    } finally {
      setIsSearching(false)
    }
  }

  function handleBackToUpload() {
    videoPlayerRef.current?.pause()
    onBackToUpload()
  }

  return (
    <section className="page-content">
      <h2>Relevant lecture moments</h2>
      <p>Playing only the segments that match your query.</p>

      <form className="page-content" onSubmit={handleSubmit}>
        <div className="field-group">
          <label htmlFor="player-query">Try a different query</label>
          <input
            id="player-query"
            type="text"
            placeholder="What did the speaker say about neural networks?"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>

        <div className="button-row">
          <button className="primary-button" type="submit" disabled={!query.trim() || isSearching}>
            {isSearching ? 'Searching...' : 'Update query'}
          </button>
          <button className="secondary-button" type="button" onClick={handleBackToUpload}>
            Upload a different video
          </button>
        </div>
      </form>

      <div className="player-layout">
        <div className="player-main">
          {video && (
            <VideoPlayer
              ref={videoPlayerRef}
              src={video.url}
              segments={segments}
              onPlaybackTimeUpdate={setCurrentTime}
            />
          )}
        </div>

        <aside className="transcript-sidebar" aria-label="Transcript">
          <div className="transcript-sidebar-header">
            <div>
              <h3>Transcript</h3>
              <p>Follows the current playback position.</p>
            </div>
            <span className="transcript-current-time">{formatTime(currentTime)}</span>
          </div>

          {isTranscriptLoading ? (
            <p className="transcript-status">Loading transcript...</p>
          ) : transcript.length === 0 ? (
            <p className="transcript-status">No transcript available for this video yet.</p>
          ) : (
            <ol className="transcript-list">
              {transcript.map((segment, index) => {
                const isActive = index === activeTranscriptIndex

                return (
                  <li
                    key={`${segment.start}-${segment.end}-${index}`}
                    ref={(element) => {
                      transcriptItemRefs.current[index] = element
                    }}
                    className={isActive ? 'active' : ''}
                  >
                    <article className="transcript-item">
                      <div className="transcript-item-meta">
                        <span>{formatTime(segment.start)}</span>
                        {segment.speaker ? <span>{segment.speaker}</span> : null}
                      </div>
                      <p>{segment.text}</p>
                    </article>
                  </li>
                )
              })}
            </ol>
          )}
        </aside>
      </div>
    </section>
  )
}
