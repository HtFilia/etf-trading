import ConnBadge from "./ConnBadge";
import WsUrlBadge from "./WsUrlBadge";

export default function Header({ status, staleSeconds, wsUrl }) {
  return (
    <header className="sticky top-0 z-10 backdrop-blur bg-zinc-950/70 border-b border-zinc-800">
      <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-2xl bg-zinc-800 grid place-items-center shadow-inner">
            <span className="text-sm">ETF</span>
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">AMM Dashboard · MVP</h1>
            <p className="text-xs text-zinc-400">Live ETF vs iNAV · 1s ticks</p>
          </div>
        </div>

        <div className="flex items-center gap-3 text-sm">
          <ConnBadge status={status} />
          <div className="hidden sm:block text-zinc-400">
            {staleSeconds == null ? "–" : `last tick ${staleSeconds.toFixed(1)}s ago`}
          </div>
          <WsUrlBadge url={wsUrl} />
        </div>
      </div>
    </header>
  );
}
