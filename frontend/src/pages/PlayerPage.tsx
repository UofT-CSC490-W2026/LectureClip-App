import { useEffect, useRef, useState, type FormEvent } from 'react'
import { VideoPlayer, type VideoPlayerHandle } from '../components/VideoPlayer'
import { queryVideo } from '../lib/api'
import type { Segment, Video } from '../lib/types'

type PlayerPageProps = {
  videoId: string
  file: File
  segments: Segment[]
  onQueryComplete: (segments: Segment[]) => void
  onBackToUpload: () => void
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
  const [query, setQuery] = useState('')
  const [isSearching, setIsSearching] = useState(false)

  useEffect(() => {
    const url = URL.createObjectURL(file)
    setVideo({ id: videoId, url })

    return () => {
      URL.revokeObjectURL(url)
    }
  }, [file, videoId])

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
            {isSearching ? 'Searching...' : 'Update segments'}
          </button>
          <button className="secondary-button" type="button" onClick={handleBackToUpload}>
            Upload a different video
          </button>
        </div>
      </form>

      {video && <VideoPlayer ref={videoPlayerRef} src={video.url} segments={segments} />}
    </section>
  )
}
