import { useMemo, useState } from "react";
import { Welcome } from "./components/Welcome";
import { Lobby } from "./components/Lobby";
import { Session } from "./components/Session";
import { useLobby } from "./hooks/useLobby";

type SessionInfo = {
  token: string;
  playerId: string;
  isHost: boolean;
};

export default function App() {
  const hostToken = useMemo(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get("host");
  }, []);

  const [info, setInfo] = useState<SessionInfo | null>(null);
  const { state, session, connected } = useLobby(info?.token ?? null);

  if (!info) {
    return (
      <Welcome
        hostToken={hostToken}
        onJoined={(token, playerId, isHost) =>
          setInfo({ token, playerId, isHost })
        }
      />
    );
  }

  const me = { playerId: info.playerId, isHost: info.isHost, token: info.token };

  if (session.phase === "idle") {
    return <Lobby state={state} connected={connected} me={me} />;
  }

  return <Session lobby={state} session={session} me={me} />;
}
