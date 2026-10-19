const esc = (value) => String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));

async function refresh() {
  try {
    const response = await fetch(`/api/runs/${window.RUN_ID}/status`, {cache: 'no-store'});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    document.getElementById('overall-status').textContent = data.run.status;
    document.getElementById('progress-value').textContent = `${data.run.progress}% (${data.terminal_count}/${data.job_count})`;
    document.getElementById('progress-bar').style.width = `${data.run.progress}%`;
    document.getElementById('stages').innerHTML = data.stages.map(stage => `
      <div class="stage-row">
        <span><strong>${esc(stage.label)}</strong><small>${esc(JSON.stringify(stage.counts))}</small></span>
        <span class="pill ${stage.state.toLowerCase()}">${esc(stage.state)}</span>
      </div>`).join('');
    const artifacts = data.artifacts.filter((item, index, all) => all.findIndex(x => x.path === item.path) === index);
    document.getElementById('artifacts').innerHTML = artifacts.length
      ? artifacts.map(item => `<a class="artifact" href="${esc(item.url)}">${esc(item.name)}<small>${esc(item.path)}</small></a>`).join('')
      : '<p class="muted">Brak gotowych artefaktów.</p>';
    document.getElementById('events').innerHTML = data.events.length
      ? data.events.map(item => `<div class="event"><time>${esc(new Date(item.at).toLocaleString())}</time><span class="event-type">${esc(item.type)}</span><span>${esc(item.message)}</span></div>`).join('')
      : '<p class="muted">Brak zdarzeń.</p>';
    if (!['COMPLETE', 'PARTIAL', 'FAILED'].includes(data.run.status)) setTimeout(refresh, 2500);
  } catch (error) {
    document.getElementById('events').innerHTML = `<div class="alert">Nie udało się odświeżyć statusu: ${esc(error.message)}</div>`;
    setTimeout(refresh, 5000);
  }
}
refresh();
