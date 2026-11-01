// Cloudflare Worker: tells the dashboard whether the merged file in gtm-data is newer
// than the published totals, and starts the update job if so. The GitHub token stays
// here as a secret. Visitors only ever get a status, so they cannot change any numbers.
const OWNER = 'Bharathwaj1316';
const DATA_REPO = 'gtm-data';
const DASHBOARD_REPO = 'gtm-dashboard';
const WORKFLOW = 'update-summary.yml';
const ASSET = 'merged.csv.gz';
const ALLOWED_ORIGIN = 'https://bharathwaj1316.github.io';

function github(env, path, options = {}) {
  return fetch(`https://api.github.com/repos/${OWNER}/${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: options.accept || 'application/vnd.github+json',
      'User-Agent': 'gtm-update-check',
    },
  });
}

async function githubJson(env, path, options) {
  const res = await github(env, path, options);
  if (!res.ok) throw new Error(`GitHub returned ${res.status} for ${path}`);
  return res.json();
}

async function check(env) {
  const release = await githubJson(env, `${DATA_REPO}/releases/tags/latest-export`);
  const asset = release.assets.find(a => a.name === ASSET);
  if (!asset) return { status: 'failed' };
  const fileUpdated = asset.updated_at;

  const summary = await githubJson(env, `${DASHBOARD_REPO}/contents/docs/summary.json`, {
    accept: 'application/vnd.github.raw+json',
  });
  if (new Date(summary.updated) >= new Date(fileUpdated)) return { status: 'current', fileUpdated };

  const { workflow_runs: runs } = await githubJson(env, `${DASHBOARD_REPO}/actions/workflows/${WORKFLOW}/runs?per_page=1`);
  const latest = runs[0];
  if (latest && latest.status !== 'completed') return { status: 'updating', fileUpdated };
  // A finished run already tried this file: don't start the job again on every page open
  if (latest && new Date(latest.created_at) > new Date(fileUpdated)) {
    return { status: latest.conclusion === 'success' ? 'updating' : 'failed', fileUpdated };
  }

  const started = await github(env, `${DASHBOARD_REPO}/actions/workflows/${WORKFLOW}/dispatches`, {
    method: 'POST',
    body: JSON.stringify({ ref: 'main' }),
  });
  if (!started.ok) throw new Error(`GitHub returned ${started.status} starting the job`);
  return { status: 'updating', fileUpdated };
}

export default {
  async fetch(request, env) {
    const headers = {
      'Access-Control-Allow-Origin': ALLOWED_ORIGIN,
      'Content-Type': 'application/json',
      'Cache-Control': 'no-store',
    };
    if (request.method === 'OPTIONS') return new Response(null, { headers });
    if (request.method !== 'GET') return new Response(JSON.stringify({ status: 'failed' }), { status: 405, headers });
    try {
      return new Response(JSON.stringify(await check(env)), { headers });
    } catch (err) {
      console.error(err.message);
      return new Response(JSON.stringify({ status: 'error' }), { status: 502, headers });
    }
  },
};
