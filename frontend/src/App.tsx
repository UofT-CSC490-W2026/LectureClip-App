import { useEffect, useState } from 'react'
import { getSession, signOut } from '@/lib/auth.ts'
import type { AuthSession } from '@/lib/auth.ts'
import { registerUser } from '@/lib/api.ts'
import { AuthPage } from '@/pages/AuthPage.tsx'
import { DashboardPage } from '@/pages/DashboardPage.tsx'
import { PlayerPage } from '@/pages/PlayerPage.tsx'
import { QueryPage } from '@/pages/QueryPage.tsx'
import { UploadPage } from '@/pages/UploadPage.tsx'
import { Avatar, AvatarFallback } from '@/components/ui/avatar.tsx'
import { Button } from '@/components/ui/button.tsx'
import { Separator } from '@/components/ui/separator.tsx'
import type { Segment, Video } from '@/lib/types.ts'

type AppView =
  | { kind: 'dashboard' }
  | { kind: 'upload' }
  | { kind: 'query'; videoId: string; file: File | null; videoUrl?: string }
  | { kind: 'player'; videoId: string; file: File | null; videoUrl?: string; segments: Segment[] }

type MainAppProps = {
  session: AuthSession
  onSignOut: () => void
}

function MainApp({ session, onSignOut }: MainAppProps) {
  const [view, setView] = useState<AppView>({ kind: 'dashboard' })

  function handleUploadComplete(videoId: string, file: File) {
    setView({ kind: 'query', videoId, file })
  }

  function handleQueryComplete(videoId: string, file: File | null, videoUrl: string | undefined, segments: Segment[]) {
    setView({ kind: 'player', videoId, file, videoUrl, segments })
  }

  function handleSelectVideo(video: Video) {
    setView({ kind: 'query', videoId: video.videoId, file: null, videoUrl: video.playbackUrl ?? undefined })
  }

  const initials = session.email.slice(0, 2).toUpperCase()

  return (
    <div className="min-h-screen bg-muted/40">
      <header className="sticky top-0 z-10 border-b border-indigo-900/20 bg-gradient-to-r from-indigo-600 to-violet-600 shadow-sm">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
          <div>
            <p className="text-xs font-semibold tracking-widest text-indigo-200 uppercase">LectureClip</p>
            <p className="text-sm text-white/80 hidden sm:block font-medium">Find the moments that answer your question.</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2">
              <Avatar className="h-7 w-7 border border-white/30">
                <AvatarFallback className="text-xs bg-white/20 text-white">{initials}</AvatarFallback>
              </Avatar>
              <span className="text-sm text-white/90">{session.email}</span>
            </div>
            <Separator orientation="vertical" className="hidden sm:block h-5 bg-white/20" />
            <Button variant="ghost" size="sm" onClick={onSignOut} className="text-white/90 hover:text-white hover:bg-white/10">
              Sign out
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-8 min-h-[calc(100vh-56px)]">
        {view.kind === 'dashboard' && (
          <DashboardPage
            userId={session.email}
            onSelectVideo={handleSelectVideo}
            onUploadNew={() => setView({ kind: 'upload' })}
          />
        )}
        {view.kind === 'upload' && (
          <UploadPage
            userId={session.email}
            onUploadComplete={handleUploadComplete}
            onBack={() => setView({ kind: 'dashboard' })}
          />
        )}
        {view.kind === 'query' && (
          <QueryPage
            videoId={view.videoId}
            onQueryComplete={(segments) =>
              handleQueryComplete(view.videoId, view.file, view.videoUrl, segments)
            }
            onBack={() => setView({ kind: 'dashboard' })}
          />
        )}
        {view.kind === 'player' && (
          <PlayerPage
            videoId={view.videoId}
            file={view.file}
            videoUrl={view.videoUrl}
            segments={view.segments}
            onQueryComplete={(segments) =>
              setView({ kind: 'player', videoId: view.videoId, file: view.file, videoUrl: view.videoUrl, segments })
            }
            onBackToUpload={() => setView({ kind: 'dashboard' })}
          />
        )}
      </main>
    </div>
  )
}

export default function App() {
  const [session, setSession] = useState<AuthSession | null | 'loading'>('loading')

  useEffect(() => {
    getSession()
      .then(async (s) => {
        if (s) await registerUser(s.email).catch(() => {/* non-blocking */})
        setSession(s)
      })
      .catch(() => setSession(null))
  }, [])

  if (session === 'loading') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-violet-50 flex items-center justify-center">
        <p className="text-muted-foreground text-sm animate-pulse">Loading…</p>
      </div>
    )
  }

  if (!session) {
    return <AuthPage onSignIn={setSession} />
  }

  return (
    <MainApp
      session={session}
      onSignOut={() => { signOut(); setSession(null) }}
    />
  )
}
