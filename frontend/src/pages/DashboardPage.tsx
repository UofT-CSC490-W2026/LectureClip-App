import { useEffect, useState } from 'react'
import { listVideos } from '@/lib/api.ts'
import type { Video } from '@/lib/types.ts'
import { Button } from '@/components/ui/button.tsx'
import { Card, CardContent } from '@/components/ui/card.tsx'
import { Upload, Play, Clock } from 'lucide-react'

type DashboardPageProps = {
  userId: string
  onSelectVideo: (video: Video) => void
  onUploadNew: () => void
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

export function DashboardPage({ userId, onSelectVideo, onUploadNew }: DashboardPageProps) {
  const [videos, setVideos] = useState<Video[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listVideos(userId)
      .then(({ videos }) => setVideos(videos))
      .catch(() => setError('Failed to load your videos.'))
      .finally(() => setLoading(false))
  }, [userId])

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Your library</h2>
          <p className="text-muted-foreground mt-1">Select a lecture to query, or upload a new one.</p>
        </div>
        <Button onClick={onUploadNew} className="shrink-0">
          <Upload className="h-4 w-4 mr-2" />
          Upload video
        </Button>
      </div>

      {loading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="animate-pulse">
              <CardContent className="p-4 h-20" />
            </Card>
          ))}
        </div>
      )}

      {error && (
        <Card className="border-destructive/50 bg-destructive/5">
          <CardContent className="p-4 text-sm text-destructive">{error}</CardContent>
        </Card>
      )}

      {!loading && !error && videos.length === 0 && (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center gap-4 py-16">
            <div className="rounded-full bg-muted p-4">
              <Upload className="h-8 w-8 text-muted-foreground" />
            </div>
            <div className="text-center">
              <p className="font-medium">No lectures yet</p>
              <p className="text-sm text-muted-foreground mt-1">Upload your first video to get started.</p>
            </div>
            <Button onClick={onUploadNew}>Upload a video</Button>
          </CardContent>
        </Card>
      )}

      {videos.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {videos.map((video) => (
            <Card
              key={video.lectureId}
              className="cursor-pointer transition-colors hover:border-primary/50 hover:bg-accent/30"
              onClick={() => onSelectVideo(video)}
            >
              <CardContent className="p-4 flex items-center gap-4">
                <div className="rounded-lg bg-primary/10 p-3 shrink-0">
                  <Play className="h-5 w-5 text-primary fill-primary/30" />
                </div>
                <div className="min-w-0">
                  <p className="font-medium truncate">{video.title}</p>
                  <div className="flex items-center gap-1 mt-1 text-xs text-muted-foreground">
                    <Clock className="h-3 w-3" />
                    <span>{formatDate(video.ingestedAt)}</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
