import { getTicker } from "../lib/ticker-api";
import { TickerFallback, TickerView } from "./TickerView";

export async function Ticker() {
  const data = await getTicker();
  if (!data || (data.live.length === 0 && data.recent_signals.length === 0)) {
    return <TickerFallback />;
  }
  return <TickerView live={data.live} signals={data.recent_signals} />;
}
