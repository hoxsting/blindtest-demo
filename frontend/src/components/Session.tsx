import { useEffect, useMemo, useState } from "react";
import type { LobbyState, SessionState } from "../api";
import { restartSession, submitAnswer } from "../api";

type Props = {
  lobby: LobbyState;
  session: SessionState;
  me: { playerId: string; isHost: boolean; token: string };
};

// Map a playerId → its latest feedback so cards animate independently.
function useFeedbackByPlayer(session: SessionState) {
  const [byPlayer, setByPlayer] = useState<
    Record<string, { correct: boolean; isFirstFull: boolean; seq: number }>
  >({});

  useEffect(() => {
    if (!session.lastFeedback) return;
    const { playerId, correct, isFirstFull, seq } = session.lastFeedback;
    setByPlayer((prev) => ({ ...prev, [playerId]: { correct, isFirstFull, seq } }));
  }, [session.lastFeedback]);

  // Clear at round start so animations don't leak between rounds
  useEffect(() => {
    setByPlayer({});
  }, [session.roundIndex]);

  return byPlayer;
}

function useCountdown(targetMs: number, running: boolean) {
  const [remaining, setRemaining] = useState(targetMs);
  useEffect(() => {
    setRemaining(targetMs);
  }, [targetMs]);
  useEffect(() => {
    if (!running) return;
    const start = Date.now();
    const initial = targetMs;
    const id = window.setInterval(() => {
      setRemaining(Math.max(0, initial - (Date.now() - start)));
    }, 100);
    return () => window.clearInterval(id);
  }, [targetMs, running]);
  return remaining;
}

export function Session({ lobby, session, me }: Props) {
  const isReveal = session.reveal !== null;
  const isFinal = session.phase === "final";
  const feedbackByPlayer = useFeedbackByPlayer(session);

  return (
    <div className="screen session">
      {isFinal ? (
        <FinalView session={session} lobby={lobby} me={me} />
      ) : (
        <>
          <SessionHeader session={session} isReveal={isReveal} />
          <HintRow session={session} />
          <PlayerGrid
            lobby={lobby}
            session={session}
            me={me}
            feedbackByPlayer={feedbackByPlayer}
          />
          {isReveal ? (
            <RevealCard session={session} />
          ) : (
            <AnswerInput token={me.token} disabled={session.timeLeftMs <= 0} />
          )}
        </>
      )}
    </div>
  );
}

function SessionHeader({
  session,
  isReveal,
}: {
  session: SessionState;
  isReveal: boolean;
}) {
  const running = !isReveal && session.timeLeftMs > 0;
  const remaining = useCountdown(session.timeLeftMs, running);
  const seconds = Math.ceil(remaining / 1000);

  return (
    <div className="session-header">
      <div className="round-counter">
        Round {(session.roundIndex ?? 0) + 1} / {session.totalRounds}
      </div>
      <div className={`chrono${seconds <= 5 ? " low" : ""}`}>{seconds}s</div>
    </div>
  );
}

function HintRow({ session }: { session: SessionState }) {
  if (session.hints.length === 0) {
    return <p className="hint">Écoute bien… les indices arrivent.</p>;
  }
  return (
    <div className="hints">
      {session.hints.map((h, i) => (
        <div key={i} className="hint-chip">
          <span className="hint-kind">
            {h.kind === "year" ? "Année" : "Initiales"}
          </span>
          <span className="hint-value">{h.value}</span>
        </div>
      ))}
    </div>
  );
}

function PlayerGrid({
  lobby,
  session,
  me,
  feedbackByPlayer,
}: {
  lobby: LobbyState;
  session: SessionState;
  me: { playerId: string };
  feedbackByPlayer: Record<
    string,
    { correct: boolean; isFirstFull: boolean; seq: number }
  >;
}) {
  return (
    <div className="player-grid">
      {lobby.players.map((p) => {
        const fb = feedbackByPlayer[p.id];
        const score = session.scores[p.id] ?? 0;
        const classes = ["player-card"];
        if (p.id === me.playerId) classes.push("me");
        if (fb) {
          classes.push("shake");
          classes.push(fb.correct ? "ok" : "ko");
          if (fb.isFirstFull) classes.push("first-full");
        }
        return (
          <div
            key={p.id}
            className={classes.join(" ")}
            // Re-trigger animation on each new feedback seq
            data-fb-seq={fb?.seq ?? 0}
          >
            <div className="player-name">{p.username}</div>
            <div className="player-score">{score} pts</div>
            {fb && (
              <div className={`feedback-icon ${fb.correct ? "ok" : "ko"}`}>
                {fb.correct ? "✓" : "✗"}
              </div>
            )}
            {fb?.isFirstFull && <div className="confetti">🎉</div>}
          </div>
        );
      })}
    </div>
  );
}

function AnswerInput({ token, disabled }: { token: string; disabled: boolean }) {
  const [guess, setGuess] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const value = guess.trim();
    if (!value || disabled || busy) return;
    setBusy(true);
    setError(null);
    try {
      await submitAnswer(token, value);
      setGuess("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="answer-form" onSubmit={submit}>
      <input
        type="text"
        value={guess}
        autoFocus
        maxLength={120}
        placeholder="Artiste ou titre…"
        onChange={(e) => setGuess(e.target.value)}
        disabled={disabled}
      />
      <button type="submit" disabled={!guess.trim() || disabled || busy}>
        Envoyer
      </button>
      {error && <p className="error">{error}</p>}
    </form>
  );
}

function RevealCard({ session }: { session: SessionState }) {
  const s = session.reveal!;
  return (
    <div className="reveal">
      <p className="hint">La chanson était :</p>
      <h2>
        {s.artist} — <em>{s.title}</em>
      </h2>
      {s.year && <p className="subtitle">({s.year})</p>}
    </div>
  );
}

function FinalView({
  session,
  lobby,
  me,
}: {
  session: SessionState;
  lobby: LobbyState;
  me: { playerId: string; isHost: boolean; token: string };
}) {
  const usernamesById = useMemo(
    () => Object.fromEntries(lobby.players.map((p) => [p.id, p.username])),
    [lobby.players],
  );
  const sortedScores = useMemo(
    () =>
      Object.entries(session.scores)
        .map(([id, score]) => ({ id, score, username: usernamesById[id] ?? id }))
        .sort((a, b) => b.score - a.score),
    [session.scores, usernamesById],
  );

  return (
    <>
      <h1>🏆 Fin de partie</h1>
      <Podium podium={session.podium ?? []} usernamesById={usernamesById} />

      <div className="scoreboard">
        {sortedScores.map((row, i) => (
          <div key={row.id} className={`score-row${row.id === me.playerId ? " me" : ""}`}>
            <span className="rank">{i + 1}</span>
            <span className="name">{row.username}</span>
            <span className="score">{row.score}</span>
          </div>
        ))}
      </div>

      {me.isHost && <RestartPrompt session={session} token={me.token} />}
      {!me.isHost && (
        <p className="hint">L'hôte choisit de relancer ou non…</p>
      )}
    </>
  );
}

function Podium({
  podium,
  usernamesById,
}: {
  podium: { player_id: string; rank: number; score: number }[];
  usernamesById: Record<string, string>;
}) {
  if (podium.length === 0) return null;
  // Place: 2 - 1 - 3 visually
  const byRank = Object.fromEntries(podium.map((e) => [e.rank, e]));
  const slots = [byRank[2], byRank[1], byRank[3]];
  return (
    <div className="podium">
      {slots.map((entry, i) => {
        if (!entry) return <div key={i} className="podium-slot empty" />;
        const heightClass = `rank-${entry.rank}`;
        return (
          <div key={entry.player_id} className={`podium-slot ${heightClass}`}>
            <div className="podium-username">
              {usernamesById[entry.player_id] ?? entry.player_id}
            </div>
            <div className="podium-score">{entry.score} pts</div>
            <div className="podium-rank">#{entry.rank}</div>
          </div>
        );
      })}
    </div>
  );
}

function RestartPrompt({
  session,
  token,
}: {
  session: SessionState;
  token: string;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [remaining, setRemaining] = useState(0);

  useEffect(() => {
    if (!session.restartDeadlineMs) return;
    const tick = () => {
      const left = Math.max(0, session.restartDeadlineMs! - Date.now());
      setRemaining(left);
    };
    tick();
    const id = window.setInterval(tick, 200);
    return () => window.clearInterval(id);
  }, [session.restartDeadlineMs]);

  async function handleRestart() {
    setBusy(true);
    setError(null);
    try {
      await restartSession(token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="restart-prompt">
      <button
        className="primary"
        onClick={handleRestart}
        disabled={busy || remaining === 0}
      >
        {busy
          ? "Relance…"
          : remaining > 0
            ? `Relancer une session (${Math.ceil(remaining / 1000)}s)`
            : "Trop tard"}
      </button>
      {error && <p className="error">{error}</p>}
    </div>
  );
}
