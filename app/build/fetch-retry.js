const https = require("https");

function get(url, redirects = 5, transport = https) {
  return new Promise((resolve, reject) => {
    transport.get(url, { timeout: 60000 }, (res) => {
      res.on("error", reject);
      res.on("aborted", () => reject(new Error(`${url}: response aborted`)));
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        res.resume();
        if (!redirects) return reject(new Error(`${url}: too many redirects`));
        let next;
        try { next = new URL(res.headers.location, url).href; }
        catch { return reject(new Error(`${url}: bad redirect ${res.headers.location}`)); }
        return resolve(get(next, redirects - 1, transport));
      }
      if (res.statusCode !== 200) {
        res.resume();
        const error = new Error(`${url}: HTTP ${res.statusCode}`);
        error.statusCode = res.statusCode;
        return reject(error);
      }
      const chunks = [];
      res.on("data", (chunk) => chunks.push(chunk));
      res.on("end", () => resolve(Buffer.concat(chunks)));
    }).on("timeout", function () { this.destroy(new Error(`${url}: timed out`)); }).on("error", reject);
  });
}

// Release assets are pinned by SHA-256 at the call site. Retry only transport
// failures and transient HTTP responses; the caller still rejects bad bytes.
async function fetchWithRetry(fetcher, url, pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms))) {
  for (let attempt = 0; attempt < 3; attempt++) {
    try { return await fetcher(url); }
    catch (error) {
      const code = error.statusCode;
      if (code != null && code !== 408 && code !== 429 && code < 500) throw error;
      if (attempt === 2) throw error;
      await pause((attempt + 1) * 1000);
    }
  }
}

module.exports = { get, fetchWithRetry };
