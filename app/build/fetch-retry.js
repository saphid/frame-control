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

module.exports = { fetchWithRetry };
