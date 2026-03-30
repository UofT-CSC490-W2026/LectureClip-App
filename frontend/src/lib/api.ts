import type { ChatSegment, Segment, TranscriptSegment, Video } from '@/lib/types.ts'

// Set via a build-time env variable (Vite exposes VITE_* vars to the bundle).
// Example .env.local:  VITE_API_BASE_URL=https://abc123.execute-api.ca-central-1.amazonaws.com/dev
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

const DIRECT_UPLOAD_THRESHOLD = 10 * 1024 * 1024 // 10 MB
const MAX_FILE_SIZE = 5 * 1024 * 1024 * 1024 // 5 GB
const ALLOWED_FORMATS = ['mp4', 'mov']
const CONTENT_TYPES: Record<string, string> = {
  mp4: 'video/mp4',
  mov: 'video/mov',
}

function getContentType(file: File): string {
  const ext = file.name.split('.').pop()?.toLowerCase() ?? ''
  return CONTENT_TYPES[ext] ?? 'video/mp4'
}

function validateFile(file: File): void {
  if (file.size === 0) throw new Error('File is empty')
  if (file.size > MAX_FILE_SIZE) throw new Error(`File exceeds maximum size of 5 GB`)
  const ext = file.name.split('.').pop()?.toLowerCase() ?? ''
  if (!ALLOWED_FORMATS.includes(ext))
    throw new Error(`File format '${ext}' is not allowed. Allowed: ${ALLOWED_FORMATS.join(', ')}`)
}

async function directUpload(file: File, userId: string, onProgress?: (pct: number) => void): Promise<string> {
  const contentType = getContentType(file)

  const initRes = await fetch(`${API_BASE}/upload`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename: file.name, fileSize: file.size, contentType, userId }),
  })
  if (!initRes.ok) throw new Error(`Upload init failed: ${initRes.status}`)
  const { uploadUrl, fileKey } = await initRes.json() as { uploadUrl: string; fileKey: string }

  const s3Res = await fetch(uploadUrl, {
    method: 'PUT',
    headers: { 'Content-Type': contentType },
    body: file,
  })
  if (!s3Res.ok) throw new Error(`S3 upload failed: ${s3Res.status}`)

  onProgress?.(100)
  return fileKey
}

async function multipartUpload(file: File, userId: string, onProgress?: (pct: number) => void): Promise<string> {
  const contentType = getContentType(file)

  const initRes = await fetch(`${API_BASE}/multipart/init`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename: file.name, fileSize: file.size, contentType, userId }),
  })
  if (!initRes.ok) throw new Error(`Multipart init failed: ${initRes.status}`)
  const { uploadId, fileKey, presignedUrls, partSize } = await initRes.json() as {
    uploadId: string
    fileKey: string
    presignedUrls: { partNumber: number; uploadUrl: string }[]
    partSize: number
  }

  const CONCURRENCY = 4
  const uploadedParts: { PartNumber: number; ETag: string }[] = []
  let completed = 0

  async function uploadPart(partNumber: number, uploadUrl: string) {
    const start = (partNumber - 1) * partSize
    const chunk = file.slice(start, start + partSize)
    const res = await fetch(uploadUrl, {
      method: 'PUT',
      headers: { 'Content-Type': contentType },
      body: chunk,
    })
    if (!res.ok) throw new Error(`Part ${partNumber} upload failed: ${res.status}`)
    const etag = res.headers.get('ETag')?.replace(/"/g, '') ?? ''
    uploadedParts.push({ PartNumber: partNumber, ETag: etag })
    completed++
    onProgress?.((completed / presignedUrls.length) * 100)
  }

  // Upload in batches of CONCURRENCY to avoid overwhelming the connection
  for (let i = 0; i < presignedUrls.length; i += CONCURRENCY) {
    const batch = presignedUrls.slice(i, i + CONCURRENCY)
    await Promise.all(batch.map(({ partNumber, uploadUrl }) => uploadPart(partNumber, uploadUrl)))
  }

  const completeRes = await fetch(`${API_BASE}/multipart/complete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ uploadId, fileKey, parts: uploadedParts.sort((a, b) => a.PartNumber - b.PartNumber) }),
  })
  if (!completeRes.ok) throw new Error(`Multipart complete failed: ${completeRes.status}`)

  return fileKey
}

const mockTranscript: TranscriptSegment[] = [
  {
    start: 0,
    end: 10,
    speaker: 'Speaker',
    text: 'Today we are going to look at how models learn patterns from examples.',
  },
  {
    start: 10,
    end: 21,
    speaker: 'Speaker',
    text: 'When we talk about neural networks, the key idea is learning layered representations.',
  },
  {
    start: 21,
    end: 34,
    speaker: 'Speaker',
    text: 'Each layer transforms the input a little further so the model can capture more abstract features.',
  },
  {
    start: 34,
    end: 46,
    speaker: 'Speaker',
    text: 'That is why we spend time thinking carefully about the structure of the network.',
  },
  {
    start: 46,
    end: 58,
    speaker: 'Speaker',
    text: 'Backpropagation gives us a way to measure which parameters should change after each example.',
  },
  {
    start: 58,
    end: 71,
    speaker: 'Speaker',
    text: 'Once gradients are available, optimization methods like gradient descent update the weights.',
  },
  {
    start: 71,
    end: 88,
    speaker: 'Speaker',
    text: 'In practice, we tune batch size, learning rate, and regularization together rather than separately.',
  },
  {
    start: 88,
    end: 96,
    speaker: 'Speaker',
    text: 'Evaluation matters because a lower training loss does not always mean better generalization.',
  },
  {
    start: 96,
    end: 108,
    speaker: 'Speaker',
    text: 'You want to compare validation metrics and inspect where the model still makes mistakes.',
  },
]

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

export async function uploadVideo(
  file: File,
  userId: string,
  onProgress?: (pct: number) => void,
): Promise<{ videoId: string }> {
  validateFile(file)
  const fileKey =
    file.size > DIRECT_UPLOAD_THRESHOLD
      ? await multipartUpload(file, userId, onProgress)
      : await directUpload(file, userId, onProgress)
  return { videoId: fileKey }
}

export async function listVideos(userId: string): Promise<{ videos: Video[] }> {
  const res = await fetch(`${API_BASE}/lectures?userId=${encodeURIComponent(userId)}`)
  if (!res.ok) throw new Error(`Failed to load videos: ${res.status}`)
  const data = await res.json() as { lectures: Video[] }
  return { videos: data.lectures }
}

export async function registerUser(email: string): Promise<void> {
  const res = await fetch(`${API_BASE}/users/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  })
  if (!res.ok) throw new Error(`Failed to register user: ${res.status}`)
}

export async function queryVideo(
  videoId: string,
  query: string,
): Promise<{ segments: Segment[] }> {
  const res = await fetch(`${API_BASE}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ videoId, query, k: 5 }),
  })
  if (!res.ok) {
    throw new Error(`Query failed: ${res.status}`)
  }
  return res.json() as Promise<{ segments: Segment[] }>
}

export async function chatVideo(
  videoId: string,
  query: string,
  sessionId?: string,
): Promise<{ answer: string; sessionId: string; segments: ChatSegment[] }> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ videoId, query, sessionId, k: 5 }),
  })
  if (!res.ok) {
    throw new Error(`Chat failed: ${res.status}`)
  }
  return res.json() as Promise<{ answer: string; sessionId: string; segments: ChatSegment[] }>
}

export async function getTranscript(videoId: string): Promise<{ transcript: TranscriptSegment[] }> {
  void videoId
  await sleep(400)
  return { transcript: mockTranscript }
}
