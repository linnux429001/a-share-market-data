const base = "https://push2.eastmoney.com/api/qt/";
const holidays2026 = [
  ["01-01", "01-03"], ["02-15", "02-23"], ["04-04", "04-06"],
  ["05-01", "05-05"], ["06-19", "06-21"], ["09-25", "09-27"],
  ["10-01", "10-07"],
];

export function isTradingMinute(ms) {
  const local = new Date(ms + 8 * 3600000);
  const day = local.getUTCDay();
  const date = local.toISOString().slice(5, 10);
  const minute = local.getUTCHours() * 60 + local.getUTCMinutes();
  // Fail closed until the next annual exchange calendar is verified.
  return local.getUTCFullYear() === 2026 && day >= 1 && day <= 5
    && !holidays2026.some(([first, last]) => date >= first && date <= last)
    && ((minute >= 570 && minute < 690) || (minute >= 780 && minute < 900));
}

async function get(path, params) {
  const response = await fetch(base + path + "?" + new URLSearchParams(params), {
    headers: { "User-Agent": "Mozilla/5.0", Referer: "https://quote.eastmoney.com/" },
    signal: AbortSignal.timeout(12000),
  });
  if (!response.ok) throw new Error(path + " HTTP " + response.status);
  const { rc, data } = await response.json();
  if (rc !== 0 || !data || typeof data !== "object") {
    throw new Error(path + " invalid upstream response");
  }
  return data;
}

const numeric = (value) => Number.isFinite(value) ? value : null;

async function board(kind) {
  const { total, diff } = await get("clist/get", {
    pn: 1, pz: 100, po: 1, np: 1, fltt: 2, invt: 2, fid: "f3",
    fs: "m:90+t:" + kind, fields: "f12,f14,f3,f6,f8",
  });
  if (!Array.isArray(diff) || !diff.length || !Number.isInteger(total)
      || total < diff.length || diff.some((row) => !row?.f12 || !row.f14)) {
    throw new Error("Invalid board list " + kind);
  }
  return { total, top: diff.map((row) => ({
    code: row.f12, name: row.f14, change_pct: numeric(row.f3),
    turnover_cny: numeric(row.f6), turnover_rate_pct: numeric(row.f8),
  })) };
}

async function stock(secid) {
  const row = await get("stock/get", {
    secid, fields: "f57,f58,f43,f44,f45,f48,f170", fltt: 2, invt: 2,
  });
  if (row.f57 !== secid.split(".")[1] || !row.f58) {
    throw new Error("Invalid stock identity " + secid);
  }
  return {
    code: row.f57, name: row.f58, price: numeric(row.f43),
    change_pct: numeric(row.f170), high: numeric(row.f44),
    low: numeric(row.f45), turnover_cny: numeric(row.f48),
  };
}

const responseHeaders = { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" };

export default {
  async scheduled(event, env) {
    if (!isTradingMinute(event.scheduledTime) || !isTradingMinute(Date.now())) return;
    try {
      const [industry, concept, ...watchlist] = await Promise.all([
        board(2), board(3), stock("0.300364"), stock("1.603533"),
      ]);
      const snapshot = {
        collected_at: new Date().toISOString(),
        scheduled_at: new Date(event.scheduledTime).toISOString(),
        timezone: "Asia/Shanghai",
        source: "Eastmoney public web API (unofficial)",
        market_data_timestamp: null,
        note: "Collection time is not a verified exchange quote time.",
        industry, concept, watchlist,
      };
      await env.MARKET.put("latest", JSON.stringify(snapshot));
      console.log("Snapshot saved", snapshot.scheduled_at, industry.top.length, concept.top.length, watchlist.length);
    } catch (error) {
      console.error("Collection failed", error.message);
      throw error;
    }
  },

  async fetch(request, env) {
    if (new URL(request.url).pathname !== "/data/latest.json") {
      return Response.json({ error: "not_found" }, { status: 404, headers: responseHeaders });
    }
    if (request.method !== "GET") {
      return Response.json({ error: "method_not_allowed" }, {
        status: 405, headers: { ...responseHeaders, allow: "GET" },
      });
    }
    try {
      const snapshot = await env.MARKET.get("latest");
      if (snapshot !== null) return new Response(snapshot, { headers: responseHeaders });
      return Response.json({ error: "awaiting_first_snapshot" }, { status: 503, headers: responseHeaders });
    } catch {
      return Response.json({ error: "storage_unavailable" }, { status: 503, headers: responseHeaders });
    }
  },
};
