import { classNames } from "../utils/format";

export default function ConnBadge({ status }) {
  const color =
    status === "open"
      ? "bg-emerald-500"
      : status === "connecting"
      ? "bg-amber-500"
      : "bg-red-500";
  const label =
    status === "open"
      ? "connected"
      : status === "connecting"
      ? "connecting"
      : "disconnected";
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className={classNames("inline-block h-2.5 w-2.5 rounded-full", color)} />
      <span className="text-zinc-300">{label}</span>
    </div>
  );
}
