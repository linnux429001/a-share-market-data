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
    && (minute === 565 || (minute >= 570 && minute < 690) || (minute >= 780 && minute < 900));
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

const githubFile = "https://api.github.com/repos/linnux429001/a-share-market-data/contents/data/latest.json";

function marketFields(snapshot) {
  // Ignore collection metadata and object key order.
  const stable = (key, value) => value && typeof value === "object" && !Array.isArray(value)
    ? Object.fromEntries(Object.keys(value).sort().map((name) => [name, value[name]]))
    : value;
  return JSON.stringify([snapshot.industry, snapshot.concept, snapshot.watchlist], stable);
}

async function syncGitHub(snapshot, serialized, token) {
  if (!token) throw new Error("GitHub sync secret missing");
  const headers = {
    Authorization: "Bearer " + token,
    Accept: "application/vnd.github+json",
    "User-Agent": "a-share-market-data-worker",
  };
  const current = await fetch(githubFile + "?ref=main", {
    headers, redirect: "error", signal: AbortSignal.timeout(12000),
  });
  if (!current.ok) throw new Error("GitHub read HTTP " + current.status);
  const { sha, content, encoding } = await current.json();
  if (!sha || !content || encoding !== "base64") throw new Error("Invalid GitHub file response");
  const oldBytes = Uint8Array.from(atob(content), (byte) => byte.charCodeAt(0));
  const old = JSON.parse(new TextDecoder().decode(oldBytes));
  if (Date.parse(old.collected_at) >= Date.parse(snapshot.collected_at)
      || marketFields(old) === marketFields(snapshot)) return;
  const bytes = new TextEncoder().encode(serialized);
  let binary = "";
  for (let offset = 0; offset < bytes.length; offset += 8192) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 8192));
  }
  const update = await fetch(githubFile, {
    method: "PUT", headers: { ...headers, "Content-Type": "application/json" },
    redirect: "error", signal: AbortSignal.timeout(12000),
    body: JSON.stringify({
      message: "Update market snapshot [skip ci]", branch: "main", sha, content: btoa(binary),
    }),
  });
  if (!update.ok) throw new Error("GitHub write HTTP " + update.status);
  console.log("GitHub snapshot synced", snapshot.collected_at);
}

const responseHeaders = { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" };

export default {
  async scheduled(event, env) {
    const normalSession = isTradingMinute(event.scheduledTime) && isTradingMinute(Date.now());
    const testStart = Date.parse("2026-11-10T23:51:00+08:00");
    const testEnd = Date.parse("2026-11-11T00:10:00+08:00");
    if (!normalSession) {
      if (event.scheduledTime < testStart || Date.now() >= testEnd
          || await env.MARKET.get("after-hours-test-20261110")) return;
      await env.MARKET.put("after-hours-test-20261110", "attempted", { expirationTtl: 3600 });
    }
    try {
      const [industry, concept, ...watchlist] = await Promise.all([
        board(2), board(3), stock("0.300364"), stock("1.603533"),
      ]);
      const snapshot = {
        collected_at: new Date().toISOString(),
        scheduled_at: new Date(event.scheduledTime).toISOString(),
        ...(!normalSession ? { collection_mode: "after_hours_test" } : {}),
        timezone: "Asia/Shanghai",
        source: "Eastmoney public web API (unofficial)",
        market_data_timestamp: null,
        note: "Collection time is not a verified exchange quote time.",
        industry, concept, watchlist,
      };
      const serialized = JSON.stringify(snapshot);
      await env.MARKET.put("latest", serialized);
      try {
        await syncGitHub(snapshot, serialized, env.GITHUB_SYNC_TOKEN);
      } catch (error) {
        const status = /^GitHub (read|write) HTTP \d+$/.test(error.message) ? error.message : "GitHub sync unavailable";
        console.error(status, snapshot.collected_at);
      }
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

