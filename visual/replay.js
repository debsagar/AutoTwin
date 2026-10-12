const $ = (id) => document.getElementById(id),
  scene = new THREE.Scene();
scene.background = new THREE.Color("#101923");
const host = $("scene"),
  renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
host.prepend(renderer.domElement);
const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 10000),
  nodes = new Map(),
  stations = [],
  tokens = [],
  labels = [],
  connections = [];
scene.add(new THREE.AmbientLight(0xffffff, 2));
const light = new THREE.DirectionalLight(0xffffff, 3);
light.position.set(0, 800, 200);
scene.add(light);
const coords = DATA.nodes.map((n) => n.position),
  center = [
    (Math.min(...coords.map((p) => p[0])) +
      Math.max(...coords.map((p) => p[0]))) /
      2,
    (Math.min(...coords.map((p) => p[1])) +
      Math.max(...coords.map((p) => p[1]))) /
      2,
  ];
const extent = Math.max(
  700,
  ...coords.map(
    (p) => Math.max(Math.abs(p[0] - center[0]), Math.abs(p[1] - center[1])) * 2,
  ),
);
let angle = 0.15,
  elevation = 0.95,
  distance = extent * 1.4;
function view() {
  camera.position.set(
    Math.sin(angle) * Math.cos(elevation) * distance,
    Math.sin(elevation) * distance,
    Math.cos(angle) * Math.cos(elevation) * distance,
  );
  camera.lookAt(0, 0, 0);
}
view();
function label(text, pos) {
  const c = document.createElement("canvas");
  c.width = 512;
  c.height = 96;
  const x = c.getContext("2d");
  x.fillStyle = "#172635";
  x.fillRect(0, 0, 512, 96);
  x.fillStyle = "#e5edf4";
  x.font = "24px system-ui";
  x.textAlign = "center";
  const words = text.split(" ");
  let lines = [""];
  for (const word of words) {
    let i = lines.length - 1;
    if ((lines[i] + " " + word).length > 34) lines.push(word);
    else lines[i] += " " + word;
  }
  lines.slice(0, 3).forEach((s, i) => x.fillText(s, 256, 28 + i * 28));
  const sprite = new THREE.Sprite(
    new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(c) }),
  );
  sprite.position.copy(pos).add(new THREE.Vector3(0, 65, 0));
  sprite.scale.set(170, 32, 1);
  scene.add(sprite);
  labels.push({ sprite, text });
}
for (const n of DATA.nodes) {
  const task = n.kind === "task",
    mesh = new THREE.Mesh(
      task
        ? new THREE.BoxGeometry(110, 25, 65)
        : new THREE.CylinderGeometry(
            24,
            24,
            18,
            n.kind.includes("Gateway") ? 4 : 24,
          ),
      new THREE.MeshStandardMaterial({
        color: task ? "#42738d" : "#777a9a",
        roughness: 0.6,
      }),
    );
  mesh.position.set(n.position[0] - center[0], 12, n.position[1] - center[1]);
  mesh.userData = n;
  scene.add(mesh);
  nodes.set(n.id, mesh);
  stations.push(mesh);
  label(n.name, mesh.position);
}
for (const [a, b] of DATA.edges) {
  if (!nodes.has(a) || !nodes.has(b)) continue;
  const p = nodes.get(a).position.clone(),
    q = nodes.get(b).position.clone();
  p.y = q.y = 4;
  scene.add(
    new THREE.Line(
      new THREE.BufferGeometry().setFromPoints([p, q]),
      new THREE.LineBasicMaterial({
        color: "#426071",
        transparent: true,
        opacity: 0.18,
      }),
    ),
  );
}
scene.add(new THREE.GridHelper(extent * 1.3, 20, 0x334d60, 0x223440));
const cases = new Map();
for (const row of DATA.records) {
  if (!cases.has(row.case_id)) cases.set(row.case_id, []);
  cases.get(row.case_id).push(row);
}
for (const [id, rows] of cases) {
  rows.sort((a, b) => a.start_time - b.start_time);
  $("case").add(new Option(`${id} · ${rows.length} events`, id));
}
let rows = [],
  start = 0,
  end = 0,
  now = 0,
  playing = false,
  last = performance.now();
const fmt = (t) =>
  new Date(t).toISOString().replace("T", " ").replace(".000Z", " UTC");
const activity = (name) => {
  const matches = stations.filter((m) => m.userData.name === name);
  return matches.length === 1 ? matches[0] : null;
};
function select() {
  rows = cases.get($("case").value) || [];
  start = Math.min(...rows.map((r) => r.enable_time));
  end = Math.max(...rows.map((r) => r.end_time));
  now = start;
  const names = new Set(rows.map((r) => r.activity));
  for (const station of stations)
    station.material.color.set(
      names.has(station.userData.name) ? "#528da7" : "#273c4c",
    );
  for (const item of labels)
    item.sprite.material.opacity = names.has(item.text) ? 1 : 0.4;
  playing = false;
  $("play").textContent = "Play";
  for (const t of tokens) {
    scene.remove(t);
    t.geometry.dispose();
    t.material.dispose();
  }
  tokens.length = 0;
  for (let i = 0; i < rows.length; i++) {
    const token = new THREE.Mesh(
      new THREE.SphereGeometry(10, 12, 8),
      new THREE.MeshStandardMaterial({ color: "#ffcf70", emissive: "#8b4b08" }),
    );
    scene.add(token);
    tokens.push(token);
  }
  caseEvidence();
  update();
}
function update() {
  const completed = rows.filter((r) => r.end_time <= now).length,
    active = rows.filter((r) => r.start_time <= now && now < r.end_time);
  $("time").textContent =
    fmt(now) +
    " · " +
    ((now - start) / 3600000).toFixed(1) +
    " hours since case enabled";
  $("counts").textContent =
    `${completed} / ${rows.length} events complete · ${active.length} executing · ${rows.filter((r) => r.enable_time <= now && now < r.start_time).length} waiting`;
  $("scrub").value = ((now - start) / Math.max(1, end - start)) * 1000;
  rows.forEach((r, i) => {
    const token = tokens[i],
      station = activity(r.activity);
    token.visible = !!station && r.enable_time <= now && now < r.end_time;
    if (!token.visible) return;
    token.position.copy(station.position);
    token.position.y = 40 + (i % 3) * 15;
    token.material.color.set(now < r.start_time ? "#a8c6e6" : "#ffcf70");

  });
  $("detail").replaceChildren();
  const heading = document.createElement("h2");
  heading.textContent = "Case " + $("case").value;
  $("detail").append(heading);
  for (const r of rows) {
    const p = document.createElement("p");
    p.textContent = `${r.end_time <= now ? "✓" : r.start_time <= now ? "▶" : r.enable_time <= now ? "◷" : "·"} ${r.activity} — ${r.resource}`;
    $("detail").append(p);
  }
}
$("case").onchange = select;
$("play").onclick = () => {
  if (now >= end) now = start;
  playing = !playing;
  $("play").textContent = playing ? "Pause" : "Play";
};
$("reset").onclick = select;
$("scrub").oninput = (e) => {
  playing = false;
  $("play").textContent = "Play";
  now = start + ((end - start) * Number(e.target.value)) / 1000;
  update();
};
$("step").onclick = () => {
  playing = false;
  $("play").textContent = "Play";
  now = Math.min(
    end,
    [...new Set(rows.flatMap((r) => [r.enable_time, r.start_time, r.end_time]))]
      .sort((a, b) => a - b)
      .find((t) => t > now) || end,
  );
  update();
};
const comparison = DATA.report.comparison || {};
$("notice").textContent =
  comparison.case_span_ratio != null
    ? `Legacy diagnostic: generated / held-out median span ${Number(comparison.case_span_ratio).toFixed(2)}×; activity-share distance ${Number(comparison.activity_share_total_variation).toFixed(3)}. Not evidence of operational validity.`
    : DATA.report.evaluations?.length
      ? `Generated model with ${DATA.report.evaluations.length} recorded evaluation(s). See the report below for metrics and limitations. Evaluated does not mean operationally validated.`
      : "Generated model; evaluation is separate. Ask the CLI agent to evaluate a selected partition and explain its report. This replay is not evidence of operational validity.";
$("evidence").textContent = JSON.stringify(
  DATA.report.assumptions || {},
  null,
  2,
);
$("report").textContent = JSON.stringify(DATA.report, null, 2);
$("manifest").textContent = JSON.stringify(DATA.manifest, null, 2);
let drag = null,
  moved = false;
renderer.domElement.onpointerdown = (e) => {
  drag = [e.clientX, e.clientY];
  moved = false;
  renderer.domElement.setPointerCapture(e.pointerId);
};
renderer.domElement.onpointermove = (e) => {
  if (!drag) return;
  const dx = e.clientX - drag[0],
    dy = e.clientY - drag[1];
  moved = moved || Math.abs(dx) + Math.abs(dy) > 3;
  angle -= dx * 0.005;
  elevation = Math.max(0.15, Math.min(1.5, elevation + dy * 0.005));
  drag = [e.clientX, e.clientY];
  view();
};
renderer.domElement.onpointerup = (e) => {
  drag = null;
  if (moved) return;
  const rect = renderer.domElement.getBoundingClientRect(),
    ray = new THREE.Raycaster();
  ray.setFromCamera(
    new THREE.Vector2(
      ((e.clientX - rect.left) / rect.width) * 2 - 1,
      (-(e.clientY - rect.top) / rect.height) * 2 + 1,
    ),
    camera,
  );
  const hit = ray.intersectObjects(stations)[0];
  if (hit) {
    $("activity").value = hit.object.userData.id;
    inspectActivity();
  }
};
renderer.domElement.onwheel = (e) => {
  e.preventDefault();
  distance = Math.max(
    extent * 0.3,
    Math.min(extent * 4, distance * Math.exp(e.deltaY * 0.001)),
  );
  view();
};
new ResizeObserver(() => {
  renderer.setSize(host.clientWidth, host.clientHeight);
  camera.aspect = host.clientWidth / host.clientHeight;
  camera.updateProjectionMatrix();
}).observe(host);

function textElement(tag, text, parent) {
  const node = document.createElement(tag);
  node.textContent = text;
  parent.append(node);
  return node;
}
const hours = (ms) => `${(ms / 3600000).toFixed(2)} h`;
function caseEvidence() {
  $("events-title").textContent = `Generated case ${$("case").value} · exact event evidence`;
  $("case-span").textContent = `${rows.length} events · ${hours(end - start)} from first enable to last completion`;
  const body = $("events").tBodies[0];
  body.replaceChildren();
  for (const r of rows) {
    const tr = document.createElement("tr");
    for (const value of [`${r.activity} / ${r.resource}`, fmt(r.enable_time), fmt(r.start_time), fmt(r.end_time), `${hours(r.start_time - r.enable_time)} / ${hours(r.end_time - r.start_time)}`])
      textElement("td", value, tr);
    body.append(tr);
  }
}
function inspectActivity() {
  const n = DATA.nodes.find((n) => n.id === $("activity").value);
  const panel = $("node-detail");
  panel.replaceChildren();
  if (!n) return;
  textElement("strong", n.name, panel);
  textElement("p", `${n.kind} · BPMN ID: ${n.id}`, panel);
  const matches = DATA.records.filter((r) => r.activity === n.name);
  const ids = [...new Set(matches.map((r) => r.case_id))];
  textElement("p", `${matches.length} generated events · ${ids.length} generated cases (activity-name matches across the baseline)`, panel);
  if (DATA.nodes.filter((v) => v.name === n.name).length > 1)
    textElement("p", "Duplicate model label: records have no node ID, so these counts cannot be assigned to this node alone. Replay tokens are omitted for ambiguous labels.", panel);
  if (ids.length) {
    const label = textElement("label", "Inspect a matching generated case ", panel);
    const choices = document.createElement("select");
    choices.setAttribute("aria-label", "Cases containing selected activity");
    choices.add(new Option("Select case…", ""));
    for (const id of ids) choices.add(new Option(id, id));
    choices.onchange = () => { if (choices.value) { $("case").value = choices.value; select(); } };
    label.append(choices);
  }
}
$("activity").add(new Option("Select activity…", ""));
for (const n of DATA.nodes) $("activity").add(new Option(`${n.name} [${n.id}]`, n.id));
$("activity").onchange = inspectActivity;
$("title").textContent = DATA.name;
document.title = `${DATA.name} · AutoTwin`;
$("subtitle").textContent = `Generated baseline · ${DATA.manifest.source?.split("/").at(-1) || "Source not recorded"} · ${DATA.manifest.status}`;
const first = Math.min(...DATA.records.map((r) => r.enable_time));
const lastEvent = Math.max(...DATA.records.map((r) => r.end_time));
for (const [value, label] of [[cases.size, "Generated cases"], [DATA.records.length, "Generated events"], [DATA.report.evaluations?.length || "Not evaluated", "Compatible evaluations"]]) {
  const stat = textElement("div", "", $("overview"));
  stat.className = "stat";
  textElement("strong", value, stat);
  textElement("span", label, stat);
}
textElement("p", `Generated range: ${fmt(first)} → ${fmt(lastEvent)}`, $("overview"));
const scope = DATA.manifest.scope || {};
const training = scope.split?.train;
textElement("p", `Observed training cohort: ${training?.cases ?? "not recorded"} cases · ${training?.events ?? "not recorded"} events.`, $("scope"));
if (scope.partitions?.train) textElement("p", `Training window [start, end): ${scope.partitions.train.start} → ${scope.partitions.train.end}`, $("scope"));
textElement("p", `Cohort: ${scope.case_value ?? "All selected categories"}. Exclusions: ${JSON.stringify(scope.excluded || {})}. Missing observed starts: ${DATA.manifest.quality?.missing_starts ?? "not recorded"}.`, $("scope"));
if (scope.caveat) textElement("p", scope.caveat, $("scope"));
for (const [key, value] of Object.entries(DATA.report.assumptions || {})) {
  textElement("dt", key.replaceAll("_", " "), $("assumptions"));
  textElement("dd", typeof value === "string" ? value : JSON.stringify(value), $("assumptions"));
}
$("hashes").textContent = JSON.stringify(DATA.artifact_sha256, null, 2);
if (!DATA.report.evaluations?.length) textElement("p", "Not evaluated. Ask the agent to evaluate a partition with explicit metrics and seeds, then export again.", $("validation"));
for (const e of DATA.report.evaluations || []) {
  textElement("h3", `${e.split} partition · ${e.cases} generated cases per seed · seeds ${(e.seeds || []).join(", ")}`, $("validation"));
  textElement("p", `Observed cases: ${e.observed_cases ?? "not recorded"} · Source: ${e.source_file}`, $("validation"));
  const wrapper = textElement("div", "", $("validation"));
  wrapper.className = "table-scroll";
  const table = textElement("table", "", wrapper);
  const head = textElement("tr", "", textElement("thead", "", table));
  for (const label of ["Metric / units", "Mean", "Population SD", "Definition and limits"]) textElement("th", label, head);
  const body = textElement("tbody", "", table);
  for (const [name, metric] of Object.entries(e.summary || {})) {
    const row = textElement("tr", "", body);
    for (const value of [name.replaceAll("_", " ") + " / " + (metric.units || "see report"), Number(metric.mean).toPrecision(4), Number(metric.std).toPrecision(4), `${metric.definition || ""} ${metric.caveats || ""}`]) textElement("td", value, row);
  }
  textElement("p", e.interpretation || "See recorded metric definitions; no acceptance threshold is inferred.", $("validation"));
  if (e.boundary_policy) textElement("p", e.boundary_policy, $("validation"));
  if (e.conformance) {
    const detail = textElement("details", "", $("validation"));
    textElement("summary", `Structural conformance · ${e.conformance.status || "recorded"}`, detail);
    textElement("pre", JSON.stringify(e.conformance, null, 2), detail);
  }
}
select();
function frame(t) {
  if (playing) {
    now = Math.min(end, now + ((t - last) / 30000) * (end - start));
    update();
    if (now === end) {
      playing = false;
      $("play").textContent = "Play";
    }
  }
  last = t;
  renderer.render(scene, camera);
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
