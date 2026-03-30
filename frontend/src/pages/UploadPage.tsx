import { useState } from 'react'
import type { FormEvent } from 'react'
import { uploadVideo } from '@/lib/api.ts'
import { Button } from '@/components/ui/button.tsx'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.tsx'
import { Label } from '@/components/ui/label.tsx'
import { ArrowLeft, FileVideo, Upload } from 'lucide-react'

type UploadPageProps = {
  userId: string
  onUploadComplete: (videoId: string, file: File) => void
  onBack: () => void
}

export function UploadPage({ userId, onUploadComplete, onBack }: UploadPageProps) {
  const [file, setFile] = useState<File | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [progress, setProgress] = useState(0)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!file) return

    setIsUploading(true)
    setProgress(0)

    try {
      const { videoId } = await uploadVideo(file, userId, setProgress)
      onUploadComplete(videoId, file)
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <div className="max-w-lg mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" onClick={onBack} className="-ml-2">
          <ArrowLeft className="h-4 w-4 mr-1" />
          Back
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Upload a lecture</CardTitle>
          <CardDescription>Select an MP4 or MOV file up to 5 GB.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="video-upload">Video file</Label>
              <label
                htmlFor="video-upload"
                className={`flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed p-8 cursor-pointer transition-colors ${
                  file ? 'border-primary/50 bg-primary/5' : 'border-muted-foreground/25 hover:border-muted-foreground/50'
                }`}
              >
                {file ? (
                  <>
                    <FileVideo className="h-8 w-8 text-primary" />
                    <div className="text-center">
                      <p className="font-medium text-sm">{file.name}</p>
                      <p className="text-xs text-muted-foreground mt-1">
                        {(file.size / (1024 * 1024)).toFixed(1)} MB
                      </p>
                    </div>
                    <span className="text-xs text-primary font-medium">Click to change</span>
                  </>
                ) : (
                  <>
                    <Upload className="h-8 w-8 text-muted-foreground" />
                    <div className="text-center">
                      <p className="font-medium text-sm">Click to select a file</p>
                      <p className="text-xs text-muted-foreground mt-1">MP4 or MOV, up to 5 GB</p>
                    </div>
                  </>
                )}
                <input
                  id="video-upload"
                  type="file"
                  accept="video/mp4,video/quicktime"
                  className="sr-only"
                  onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                />
              </label>
            </div>

            {isUploading && (
              <div className="space-y-1.5">
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>Uploading…</span>
                  <span>{Math.round(progress)}%</span>
                </div>
                <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
                  <div
                    className="h-full bg-primary rounded-full transition-all duration-300"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </div>
            )}

            <Button type="submit" className="w-full" disabled={!file || isUploading}>
              {isUploading ? 'Uploading…' : 'Upload and continue'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
