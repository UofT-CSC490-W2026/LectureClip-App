import { useEffect, useState } from 'react'
import { VideoPlayer } from '../components/VideoPlayer'
import type { Segment, Video } from '../lib/types'

type PlayerPageProps = {
  videoId: string
  file: File
  segments: Segment[]
}

export function PlayerPage({ videoId, file, segments }: PlayerPageProps) {
  const [video, setVideo] = useState<Video | null>(null)

  useEffect(() => {
    const url = URL.createObjectURL(file)
    setVideo({ id: videoId, url })

    return () => {
      URL.revokeObjectURL(url)
    }
  }, [file, videoId])

  return (
    <section className="page-content">
      <h2>Relevant lecture moments</h2>
      <p>Playing only the segments that match your query.</p>
      {video && <VideoPlayer src={video.url} segments={segments} />}
    </section>
  )
}
