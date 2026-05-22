import { useMemo, useState } from "react";
import { Welcome } from "./components/Welcome";
import { Lobby } from "./components/Lobby";
import { useLobby } from "./hooks/useLobby";

type Session = {
  token: string;
  playerId: string;
  isHost: boolean;
};

export default function App() {
  const hostToken = useMemo(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get("host");
  }, []);

  const [session, setSession] = useState<Session | null>(null);
  const { state, connected } = useLobby(session?.token ?? null);

  if (!session) {
    return (
      <Welcome
        hostToken={hostToken}
        onJoined={(token, playerId, isHost) =>
          setSession({ token, playerId, isHost })
        }
      />
    );
  }

  return (
    <Lobby
      state={state}
      connected={connected}
      me={{ playerId: session.playerId, isHost: session.isHost }}
    />
  );
}
