import { afterEach, describe, expect, it, vi } from 'vitest'
import { getTranscript, queryVideo, uploadVideo } from '@/lib/api.ts'

afterEach(() => {
  vi.restoreAllMocks()
  vi.useRealTimers()
})

describe('uploadVideo', () => {
  it('returns the fileKey as videoId on a successful direct upload', async () => {
    // Small file → directUpload path (POST /upload then PUT to S3)
    const file = new File(['video-bytes'], 'lecture.mp4', { type: 'video/mp4' })

    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(new Response(
        JSON.stringify({ uploadUrl: 'https://s3.example.com/presigned', fileKey: 'vid_123' }),
        { status: 200 },
      ))
      .mockResolvedValueOnce(new Response(null, { status: 200 })),
    )

    const result = await uploadVideo(file, 'anonymous')
    expect(result).toEqual({ videoId: 'vid_123' })
  })

  it('throws when the upload init request fails', async () => {
    const file = new File(['video-bytes'], 'lecture.mp4', { type: 'video/mp4' })

    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(
      new Response(null, { status: 500 }),
    ))

    await expect(uploadVideo(file, 'anonymous')).rejects.toThrow('Upload init failed: 500')
  })
})

describe('queryVideo', () => {
  it('returns segments from the API response', async () => {
    const segments = [
      { start: 12, end: 28 },
      { start: 46, end: 64 },
      { start: 88, end: 102 },
    ]

    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(
      new Response(JSON.stringify({ segments }), { status: 200 }),
    ))

    const result = await queryVideo('vid_123', 'neural networks')
    expect(result).toEqual({ segments })
  })

  it('throws when the query request fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(
      new Response(null, { status: 400 }),
    ))

    await expect(queryVideo('vid_123', 'neural networks')).rejects.toThrow('Query failed: 400')
  })
})

describe('getTranscript', () => {
  it('returns the mock transcript', async () => {
    vi.useFakeTimers()

    const transcriptPromise = getTranscript('vid_123')
    await vi.runAllTimersAsync()

    await expect(transcriptPromise).resolves.toMatchObject({
      transcript: expect.arrayContaining([
        expect.objectContaining({ start: 10, end: 21, speaker: 'Speaker' }),
      ]),
    })
  })
})