async function api(path, opts={}){
  const r = await fetch(path, {headers: {"Content-Type":"application/json"}, ...opts});
  if(!r.ok){ throw new Error(await r.text()); }
  return r.json();
}

async function load(){
  const s = await api('/api/settings');
  for(const k of ['poll_interval_minutes']){
    document.getElementById(k).value = s[k];
  }
  for(const k of ['mqtt_host','mqtt_port','mqtt_username','mqtt_password','mqtt_base_topic']){
    document.getElementById(k).value = s['mqtt'][k];
  }
  render();
}

async function render(){
  const pkgs = await api('/api/packages');
  const tbody = document.getElementById('pkgs-body');
  tbody.innerHTML = '';
  for(const p of pkgs){
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><code>${p.id}</code></td>
      <td>${p.carrier.toUpperCase()}</td>
      <td><code>${p.number}</code></td>
      <td>${p.label ?? ''}</td>
      <td>${p.detailed_status ?? ''}</td>
      <td><b>${p.summary_status ?? ''}</b></td>
      <td>${p.last_update ? new Date(p.last_update).toLocaleString() : ''}</td>
      <td><button data-del="${p.id}">Usuń</button></td>
    `;
    tbody.appendChild(tr);
  }
  tbody.querySelectorAll('button[data-del]').forEach(btn => {
    btn.addEventListener('click', async () => {
      await api('/api/packages/' + btn.dataset.del, {method:'DELETE'});
      await render();
    });
  });
}

document.getElementById('add-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const carrier = document.getElementById('carrier').value;
  const number = document.getElementById('number').value;
  const label = document.getElementById('label').value;
  await api('/api/packages', {method:'POST', body: JSON.stringify({carrier, number, label})});
  document.getElementById('number').value = '';
  document.getElementById('label').value = '';
  await render();
});

document.getElementById('settings-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const s = {
    poll_interval_minutes: parseInt(document.getElementById('poll_interval_minutes').value, 10),
    mqtt: {
      host: document.getElementById('mqtt_host').value,
      port: parseInt(document.getElementById('mqtt_port').value, 10),
      username: document.getElementById('mqtt_username').value,
      password: document.getElementById('mqtt_password').value,
      base_topic: document.getElementById('mqtt_base_topic').value
    }
  };
  await api('/api/settings', {method:'POST', body: JSON.stringify(s)});
  alert('Zapisano. MQTT Discovery może przez chwilę się propagować.');
});

document.getElementById('poll-btn').addEventListener('click', async () => {
  await api('/api/trigger-poll', {method:'POST'});
  await render();
});

load();
