import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import ReactMarkdown from 'react-markdown'
import { VideoPlayer } from '@/components/VideoPlayer.tsx'
import type { VideoPlayerHandle } from '@/components/VideoPlayer.tsx'
import { chatVideo, getTranscript, queryVideo } from '@/lib/api.ts'
import type { ChatMessage, ChatSegment, Segment, TranscriptSegment } from '@/lib/types.ts'
import { Button } from '@/components/ui/button.tsx'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card.tsx'
import { Input } from '@/components/ui/input.tsx'
import { Badge } from '@/components/ui/badge.tsx'
import { ScrollArea } from '@/components/ui/scroll-area.tsx'
import { Separator } from '@/components/ui/separator.tsx'
import { ArrowLeft, RotateCcw, Send } from 'lucide-react'
import { cn } from '@/lib/utils.ts'

type PlayerPageProps = {
  videoId: string
  file: File | null
  videoUrl?: string
  segments: Segment[]
  onQueryComplete: (segments: Segment[]) => void
  onBackToUpload: () => void
}

function formatTime(seconds: number) {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  return [h, m, s].map((v) => String(v).padStart(2, '0')).join(':')
}

function getTranscriptIndexForTime(transcript: TranscriptSegment[], time: number) {
  const index = transcript.findIndex((s) => time >= s.start && time < s.end)
  return index >= 0 ? index : null
}

export function PlayerPage({
  videoId,
  file,
  videoUrl,
  segments,
  onQueryComplete,
  onBackToUpload,
}: PlayerPageProps) {
  const [video, setVideo] = useState<{ id: string; url: string } | null>(null)
  const videoPlayerRef = useRef<VideoPlayerHandle | null>(null)
  const transcriptItemRefs = useRef<Array<HTMLElement | null>>([])
  const [query, setQuery] = useState('')
  const [isSearching, setIsSearching] = useState(false)
  const [transcript, setTranscript] = useState<TranscriptSegment[]>([])
  const [isTranscriptLoading, setIsTranscriptLoading] = useState(true)
  const [currentTime, setCurrentTime] = useState(0)
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
  const [chatInput, setChatInput] = useState('')
  const [isChatLoading, setIsChatLoading] = useState(false)
  const [chatSessionId, setChatSessionId] = useState<string | undefined>(undefined)
  const chatEndRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (file) {
      const url = URL.createObjectURL(file)
      setVideo({ id: videoId, url })
      setCurrentTime(0)
      return () => { URL.revokeObjectURL(url) }
    } else if (videoUrl) {
      setVideo({ id: videoId, url: videoUrl })
      setCurrentTime(0)
    }
  }, [file, videoUrl, videoId])

  useEffect(() => {
    let cancelled = false
    setIsTranscriptLoading(true)
    getTranscript(videoId)
      .then(({ transcript: t }) => { if (!cancelled) setTranscript(t) })
      .finally(() => { if (!cancelled) setIsTranscriptLoading(false) })
    return () => { cancelled = true }
  }, [videoId])

  const activeTranscriptIndex = getTranscriptIndexForTime(transcript, currentTime)

  useEffect(() => {
    if (activeTranscriptIndex === null) return
    transcriptItemRefs.current[activeTranscriptIndex]?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [activeTranscriptIndex])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatMessages])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!query.trim()) return
    setIsSearching(true)
    try {
      const { segments: next } = await queryVideo(videoId, query.trim())
      onQueryComplete(next)
    } finally {
      setIsSearching(false)
    }
  }

  async function handleChatSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const text = chatInput.trim()
    if (!text || isChatLoading) return
    setChatMessages((prev) => [...prev, { role: 'user', content: text }])
    setChatInput('')
    setIsChatLoading(true)
    try {
      const { answer, sessionId, segments: segs } = await chatVideo(videoId, text, chatSessionId)
      setChatSessionId(sessionId)
      setChatMessages((prev) => [...prev, { role: 'assistant', content: answer, segments: segs }])
    } catch {
      setChatMessages((prev) => [...prev, { role: 'assistant', content: 'Something went wrong. Please try again.' }])
    } finally {
      setIsChatLoading(false)
    }
  }

  function preprocessChatContent(content: string) {
    return content.replace(/\[Segment (\d+)\]/g, '[Segment $1](#segment-$1)')
  }

  const filename = videoId.split('/').pop() ?? videoId

  return (
    <div className="space-y-6">
      {/* Top bar */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={onBackToUpload} className="-ml-2">
            <ArrowLeft className="h-4 w-4 mr-1" />
            Dashboard
          </Button>
          <Separator orientation="vertical" className="h-5" />
          <p className="text-sm text-muted-foreground truncate max-w-xs">{filename}</p>
        </div>
        <form onSubmit={handleSubmit} className="flex items-center gap-2">
          <Input
            type="text"
            placeholder="Try a different query…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-64"
          />
          <Button type="submit" size="sm" disabled={!query.trim() || isSearching} variant="secondary">
            <RotateCcw className="h-4 w-4" />
          </Button>
        </form>
      </div>

      {/* Main layout */}
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,2fr)_minmax(280px,1fr)] gap-6 items-start">
        {/* Left: video + chat */}
        <div className="space-y-4">
          {video && (
            <VideoPlayer
              ref={videoPlayerRef}
              src={video.url}
              segments={segments}
              onPlaybackTimeUpdate={setCurrentTime}
            />
          )}

          {/* Chat panel */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Chat with this lecture</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <ScrollArea className="h-72 pr-4">
                {chatMessages.length === 0 && (
                  <p className="text-sm text-muted-foreground text-center py-8">
                    Ask a question to get answers grounded in the video content.
                  </p>
                )}
                <div className="space-y-3">
                  {chatMessages.map((msg, i) => (
                    <div
                      key={i}
                      className={cn('flex', msg.role === 'user' ? 'justify-end' : 'justify-start')}
                    >
                      <div
                        className={cn(
                          'max-w-[80%] rounded-xl px-3.5 py-2.5 text-sm',
                          msg.role === 'user'
                            ? 'bg-primary text-primary-foreground rounded-br-sm'
                            : 'bg-muted rounded-bl-sm',
                        )}
                      >
                        {msg.role === 'user' ? (
                          <p>{msg.content}</p>
                        ) : (
                          <div className="prose prose-sm max-w-none dark:prose-invert">
                            <ReactMarkdown
                              components={{
                                a({ href, children }) {
                                  const match = href?.match(/^#segment-(\d+)$/)
                                  if (match && msg.segments) {
                                    const seg = msg.segments[parseInt(match[1], 10) - 1] as ChatSegment | undefined
                                    return (
                                      <button
                                        type="button"
                                        className="inline-flex items-center rounded px-1.5 py-0.5 text-xs font-semibold bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
                                        onClick={() => seg && videoPlayerRef.current?.seekTo(seg.start)}
                                      >
                                        {children}
                                      </button>
                                    )
                                  }
                                  return <a href={href}>{children}</a>
                                },
                              }}
                            >
                              {preprocessChatContent(msg.content)}
                            </ReactMarkdown>
                            {msg.segments && msg.segments.length > 0 && (
                              <div className="flex flex-wrap gap-1.5 mt-2 pt-2 border-t border-border/50">
                                {msg.segments.map((seg, j) => (
                                  <button
                                    key={j}
                                    type="button"
                                    className="rounded-md border border-primary/30 bg-primary/10 px-2 py-1 text-xs font-semibold text-primary hover:bg-primary/20 transition-colors"
                                    onClick={() => videoPlayerRef.current?.seekTo(seg.start)}
                                  >
                                    Segment {j + 1} · {formatTime(seg.start)}–{formatTime(seg.end)}
                                  </button>
                                ))}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                  {isChatLoading && (
                    <div className="flex justify-start">
                      <div className="bg-muted rounded-xl rounded-bl-sm px-4 py-3 flex gap-1 items-center">
                        {[0, 1, 2].map((i) => (
                          <span
                            key={i}
                            className="block h-1.5 w-1.5 rounded-full bg-muted-foreground/50 animate-bounce"
                            style={{ animationDelay: `${i * 150}ms` }}
                          />
                        ))}
                      </div>
                    </div>
                  )}
                  <div ref={chatEndRef} />
                </div>
              </ScrollArea>
              <form onSubmit={handleChatSubmit} className="flex gap-2">
                <Input
                  placeholder="Ask about this lecture…"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  disabled={isChatLoading}
                  className="flex-1"
                />
                <Button type="submit" size="icon" disabled={!chatInput.trim() || isChatLoading}>
                  <Send className="h-4 w-4" />
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>

        {/* Right: transcript */}
        <Card className="sticky top-20">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Transcript</CardTitle>
              <Badge variant="secondary" className="font-mono text-xs">
                {formatTime(currentTime)}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground">Follows playback position.</p>
          </CardHeader>
          <CardContent className="p-0">
            <ScrollArea className="h-[520px] px-4 pb-4">
              {isTranscriptLoading && (
                <p className="text-sm text-muted-foreground py-4 text-center">Loading transcript…</p>
              )}
              {!isTranscriptLoading && transcript.length === 0 && (
                <p className="text-sm text-muted-foreground py-4 text-center">No transcript available yet.</p>
              )}
              <div className="space-y-2">
                {transcript.map((seg, index) => {
                  const isActive = index === activeTranscriptIndex
                  return (
                    <div
                      key={`${seg.start}-${seg.end}-${index}`}
                      ref={(el) => { transcriptItemRefs.current[index] = el }}
                      className={cn(
                        'rounded-lg border p-3 text-sm transition-colors',
                        isActive ? 'border-primary/50 bg-primary/5' : 'border-transparent bg-muted/30',
                      )}
                    >
                      <div className="flex items-center justify-between mb-1 text-xs text-muted-foreground font-medium">
                        <span>{formatTime(seg.start)}</span>
                        {seg.speaker && <span>{seg.speaker}</span>}
                      </div>
                      <p className="leading-relaxed">{seg.text}</p>
                    </div>
                  )
                })}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
