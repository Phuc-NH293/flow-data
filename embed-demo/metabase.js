async function main() {
  const status = document.getElementById('status');
  const dashboard = document.getElementById('dashboard');
  const cfg = await (await fetch('/api/embed-config')).json();
  window.metabaseConfig = {
    isGuest: true,
    instanceUrl: cfg.metabase_url,
    guestEmbedProviderUri: '/api/metabase-guest-token',
  };
  dashboard.setAttribute('dashboard-id', String(cfg.dashboard_id));
  status.textContent = `Dashboard #${cfg.dashboard_id} connected`;
}

main().catch(err => {
  document.getElementById('status').textContent = `Embed unavailable: ${err.message}`;
});
