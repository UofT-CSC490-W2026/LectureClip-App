import { useState, type FormEvent } from 'react'
import { uploadVideo } from '../lib/api'

type UploadPageProps = {
  onUploadComplete: (videoId: string, file: File) => void
}

export function UploadPage({ onUploadComplete }: UploadPageProps) {
  const [file, setFile] = useState<File | null>(null)
  const [isUploading, setIsUploading] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!file) return

    setIsUploading(true)

    try {
      const { videoId } = await uploadVideo(file)
      onUploadComplete(videoId, file)
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <section className="page-content">
      <h2>Upload a lecture video</h2>
      <p>Select a local video file to start the flow.</p>

      <form className="page-content" onSubmit={handleSubmit}>
        <div className="field-group">
          <label htmlFor="video-upload">Video file</label>
          <input
            id="video-upload"
            type="file"
            accept="video/*"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </div>

        <button className="primary-button" type="submit" disabled={!file || isUploading}>
          {isUploading ? 'Uploading...' : 'Upload video'}
        </button>
      </form>
    </section>
  )
}
