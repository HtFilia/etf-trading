export default function WsUrlBadge({ url }) {
  return (
    <div
      className="px-2 py-1 rounded-lg bg-zinc-800 text-zinc-300 text-xs font-mono whitespace-nowrap max-w-[50vw] overflow-hidden text-ellipsis"
      title={url}
    >
      {url}
    </div>
  );
}
