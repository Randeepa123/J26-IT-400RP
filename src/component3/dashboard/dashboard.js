/**
 * Kukule Ganga Component 3 - Live Dashboard Controller
 */

// Fallback baseline data from the latest run (outputs/run_component3/)
const BASELINE_REC = {
  "date": "2026-10-18",
  "primary_method": "hybrid",
  "turbine_release_m3s": 23.31,
  "turbine_release_m3": 2014134.93,
  "generation_mwh": 901.06,
  "mandatory_release_m3s": 3.0,
  "expected_end_storage_pct": 74.57,
  "expected_end_storage_m3": 1245353.07,
  "demand_weight": 1.03,
  "methods_day0_turbine_release_m3s": {
    "rolling_lp": 23.31,
    "reference": 30.96,
    "hybrid": 23.31
  },
  "data_status": "MODELLED / ASSUMED INPUTS - decision support only"
};

const BASELINE_ALERTS = [
  "2026-10-18: FLOOD WATCH - P90 inflow over next 3 days exceeds turbine capacity + free storage by 8.90 MCM; pre-drawdown is built into the plan.",
  "2026-10-19: FLOOD WATCH - P90 inflow over next 3 days exceeds turbine capacity + free storage by 9.69 MCM; pre-drawdown is built into the plan.",
  "2026-10-20: FLOOD WATCH - P90 inflow over next 3 days exceeds turbine capacity + free storage by 10.42 MCM; pre-drawdown is built into the plan."
];

const BASELINE_SCHEDULE = [
  {"day":1,"date":"2026-10-18","turbine_release_m3s":23.31,"turbine_release_m3":2014135,"spill_m3s":0,"mandatory_m3s":3.0,"storage_pct":74.57,"level_masl":205.51,"generation_mwh":901.06,"net_head_m":183.43,"demand_weight":1.03,"units":2,"inflow_p50_m3s":28.0,"inflow_p90_m3s":52.3},
  {"day":2,"date":"2026-10-19","turbine_release_m3s":23.31,"turbine_release_m3":2014135,"spill_m3s":0,"mandatory_m3s":3.0,"storage_pct":83.96,"level_masl":205.69,"generation_mwh":901.95,"net_head_m":183.61,"demand_weight":1.03,"units":2,"inflow_p50_m3s":29.1,"inflow_p90_m3s":55.1},
  {"day":3,"date":"2026-10-20","turbine_release_m3s":23.31,"turbine_release_m3":2014135,"spill_m3s":0,"mandatory_m3s":3.0,"storage_pct":82.56,"level_masl":205.67,"generation_mwh":901.81,"net_head_m":183.59,"demand_weight":1.03,"units":2,"inflow_p50_m3s":27.8,"inflow_p90_m3s":57.4},
  {"day":4,"date":"2026-10-21","turbine_release_m3s":23.31,"turbine_release_m3":2014135,"spill_m3s":0,"mandatory_m3s":3.0,"storage_pct":70.86,"level_masl":205.44,"generation_mwh":900.70,"net_head_m":183.36,"demand_weight":1.035,"units":2,"inflow_p50_m3s":24.5,"inflow_p90_m3s":46.2},
  {"day":5,"date":"2026-10-22","turbine_release_m3s":23.31,"turbine_release_m3":2014135,"spill_m3s":0,"mandatory_m3s":3.0,"storage_pct":49.01,"level_masl":205.01,"generation_mwh":898.61,"net_head_m":182.93,"demand_weight":1.029,"units":2,"inflow_p50_m3s":19.2,"inflow_p90_m3s":35.0},
  {"day":6,"date":"2026-10-23","turbine_release_m3s":8.77,"turbine_release_m3":757721,"spill_m3s":0,"mandatory_m3s":3.0,"storage_pct":95.23,"level_masl":205.91,"generation_mwh":332.13,"net_head_m":185.96,"demand_weight":1.022,"units":2,"inflow_p50_m3s":21.5,"inflow_p90_m3s":32.1},
  {"day":7,"date":"2026-10-24","turbine_release_m3s":15.97,"turbine_release_m3":1380000,"spill_m3s":0,"mandatory_m3s":3.0,"storage_pct":100.0,"level_masl":206.00,"generation_mwh":602.54,"net_head_m":185.24,"demand_weight":0.973,"units":2,"inflow_p50_m3s":18.9,"inflow_p90_m3s":28.0},
  {"day":8,"date":"2026-10-25","turbine_release_m3s":15.23,"turbine_release_m3":1315642,"spill_m3s":0,"mandatory_m3s":3.0,"storage_pct":100.0,"level_masl":206.00,"generation_mwh":574.77,"net_head_m":185.34,"demand_weight":0.909,"units":2,"inflow_p50_m3s":18.2,"inflow_p90_m3s":25.4},
  {"day":9,"date":"2026-10-26","turbine_release_m3s":14.44,"turbine_release_m3":1247903,"spill_m3s":0,"mandatory_m3s":3.0,"storage_pct":97.64,"level_masl":205.95,"generation_mwh":545.36,"net_head_m":185.40,"demand_weight":1.023,"units":2,"inflow_p50_m3s":17.0,"inflow_p90_m3s":23.1},
  {"day":10,"date":"2026-10-27","turbine_release_m3s":14.44,"turbine_release_m3":1247903,"spill_m3s":0,"mandatory_m3s":3.0,"storage_pct":87.87,"level_masl":205.77,"generation_mwh":544.81,"net_head_m":185.22,"demand_weight":1.023,"units":2,"inflow_p50_m3s":15.5,"inflow_p90_m3s":21.0},
  {"day":11,"date":"2026-10-28","turbine_release_m3s":14.44,"turbine_release_m3":1247903,"spill_m3s":0,"mandatory_m3s":3.0,"storage_pct":72.34,"level_masl":205.47,"generation_mwh":543.93,"net_head_m":184.92,"demand_weight":1.028,"units":2,"inflow_p50_m3s":14.4,"inflow_p90_m3s":19.5},
  {"day":12,"date":"2026-10-29","turbine_release_m3s":14.44,"turbine_release_m3":1247903,"spill_m3s":0,"mandatory_m3s":3.0,"storage_pct":52.84,"level_masl":205.09,"generation_mwh":542.81,"net_head_m":184.54,"demand_weight":1.021,"units":2,"inflow_p50_m3s":13.6,"inflow_p90_m3s":18.2},
  {"day":13,"date":"2026-10-30","turbine_release_m3s":14.44,"turbine_release_m3":1247903,"spill_m3s":0,"mandatory_m3s":3.0,"storage_pct":20.00,"level_masl":204.43,"generation_mwh":540.88,"net_head_m":183.88,"demand_weight":1.014,"units":2,"inflow_p50_m3s":11.1,"inflow_p90_m3s":16.0},
  {"day":14,"date":"2026-10-31","turbine_release_m3s":2.73,"turbine_release_m3":235615,"spill_m3s":0,"mandatory_m3s":3.0,"storage_pct":40.34,"level_masl":204.84,"generation_mwh":102.86,"net_head_m":185.21,"demand_weight":0.964,"units":2,"inflow_p50_m3s":8.9,"inflow_p90_m3s":14.0},
  {"day":15,"date":"2026-11-01","turbine_release_m3s":2.73,"turbine_release_m3":235615,"spill_m3s":0,"mandatory_m3s":4.0,"storage_pct":50.00,"level_masl":205.03,"generation_mwh":102.97,"net_head_m":185.40,"demand_weight":0.901,"units":2,"inflow_p50_m3s":7.5,"inflow_p90_m3s":12.2}
];

const BASELINE_METHODS = [
  {"method":"Hybrid LP-DQN","day1_release_m3s":23.31,"plan_energy_mwh":8812,"final_storage_pct":50.0,"min_storage_pct":20.0,"avoidable_spill_mcm":0.0,"reserve_breach_days":0,"unmet_days":0,"floor_breach_days":0},
  {"method":"Rolling LP","day1_release_m3s":23.31,"plan_energy_mwh":8812,"final_storage_pct":50.0,"min_storage_pct":20.0,"avoidable_spill_mcm":0.0,"reserve_breach_days":0,"unmet_days":0,"floor_breach_days":0},
  {"method":"DQN","day1_release_m3s":21.80,"plan_energy_mwh":8640,"final_storage_pct":46.5,"min_storage_pct":19.8,"avoidable_spill_mcm":0.0,"reserve_breach_days":1,"unmet_days":0,"floor_breach_days":0},
  {"method":"Reference rule (causal)","day1_release_m3s":30.96,"plan_energy_mwh":8450,"final_storage_pct":32.0,"min_storage_pct":17.2,"avoidable_spill_mcm":0.42,"reserve_breach_days":3,"unmet_days":1,"floor_breach_days":0}
];

// Scoreboard cache data
const SCOREBOARD_DATA = [
  {"method":"Hybrid LP-DQN","episode_score":30.22,"energy_gwh":190.5,"capacity_factor_pct":31.1,"avoidable_spill_mcm":2.05,"reserve_breach_days":6.5,"floor_breach_days":0.0,"decision_ms":2.93},
  {"method":"Rolling LP","episode_score":27.05,"energy_gwh":189.6,"capacity_factor_pct":30.9,"avoidable_spill_mcm":4.87,"reserve_breach_days":9.1,"floor_breach_days":0.0,"decision_ms":2.16},
  {"method":"DQN","episode_score":21.07,"energy_gwh":190.8,"capacity_factor_pct":31.1,"avoidable_spill_mcm":2.13,"reserve_breach_days":17.2,"floor_breach_days":0.0,"decision_ms":0.31},
  {"method":"Reference (reads gauge)","episode_score":17.35,"energy_gwh":191.7,"capacity_factor_pct":31.3,"avoidable_spill_mcm":0.0,"reserve_breach_days":21.2,"floor_breach_days":0.0,"decision_ms":0.004},
  {"method":"Reference (causal)","episode_score":-9.71,"energy_gwh":165.8,"capacity_factor_pct":27.0,"avoidable_spill_mcm":58.46,"reserve_breach_days":21.3,"floor_breach_days":0.0,"decision_ms":0.004},
  {"method":"Perfect-foresight LP (bound)","episode_score":37.38,"energy_gwh":192.3,"capacity_factor_pct":31.4,"avoidable_spill_mcm":0.0,"reserve_breach_days":3.0,"floor_breach_days":0.0,"decision_ms":0.0003}
];

// App State
let state = {
  apiOnline: false,
  apiBase: 'http://127.0.0.1:8765',
  storagePct: 60,
  inflowScale: 1.0,
  p90Scale: 1.0,
  demandScale: 1.0,
  units: 2,
  method: 'hybrid',
  source: 'whatif',
  align: 'today',
  autoRefresh: false,
  timerId: null,
  currentSchedule: BASELINE_SCHEDULE,
  currentSummary: null,
  currentMethods: BASELINE_METHODS,
  currentAlerts: BASELINE_ALERTS
};

// Chart references
let charts = {
  discharge: null,
  reservoir: null,
  generation: null,
  methods: null,
  benchmark: null
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  setupEventListeners();
  initCharts();
  renderScoreboardTable();
  checkApiHealth();
});

function setupEventListeners() {
  // Navigation Tabs
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-view').forEach(v => v.style.display = 'none');
      btn.classList.add('active');
      const targetView = document.getElementById(btn.dataset.target);
      if (targetView) targetView.style.display = 'block';
    });
  });

  // Slider inputs & live values
  const setupSlider = (id, valId, key, formatFn) => {
    const slider = document.getElementById(id);
    const label = document.getElementById(valId);
    if (!slider || !label) return;
    slider.addEventListener('input', (e) => {
      const val = parseFloat(e.target.value);
      state[key] = val;
      label.textContent = formatFn ? formatFn(val) : val;
      debouncePlanRecalc();
    });
  };

  setupSlider('storage-slider', 'storage-val', 'storagePct', v => `${v.toFixed(0)}%`);
  setupSlider('inflow-slider', 'inflow-val', 'inflowScale', v => `${v.toFixed(1)}x`);
  setupSlider('p90-slider', 'p90-val', 'p90Scale', v => `${v.toFixed(1)}x`);
  setupSlider('demand-slider', 'demand-val', 'demandScale', v => `${v.toFixed(1)}x`);

  // Unit toggle buttons
  document.querySelectorAll('.unit-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.unit-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.units = parseInt(btn.dataset.units);
      fetchPlan();
    });
  });

  // Method selector
  const methodSelect = document.getElementById('method-select');
  if (methodSelect) {
    methodSelect.addEventListener('change', (e) => {
      state.method = e.target.value;
      fetchPlan();
    });
  }

  // Source selector
  const sourceSelect = document.getElementById('source-select');
  if (sourceSelect) {
    sourceSelect.addEventListener('change', (e) => {
      state.source = e.target.value;
      fetchPlan();
    });
  }

  // Action buttons
  document.getElementById('recalc-btn')?.addEventListener('click', fetchPlan);
  document.getElementById('reset-btn')?.addEventListener('click', resetDefaults);
  document.getElementById('spike-btn')?.addEventListener('click', simulateSpike);
  document.getElementById('export-btn')?.addEventListener('click', exportScheduleCSV);
  
  // Auto refresh toggle
  const autoToggle = document.getElementById('auto-refresh-toggle');
  if (autoToggle) {
    autoToggle.addEventListener('change', (e) => {
      state.autoRefresh = e.target.checked;
      if (state.autoRefresh) {
        state.timerId = setInterval(fetchPlan, 10000);
      } else if (state.timerId) {
        clearInterval(state.timerId);
      }
    });
  }
}

let debounceTimer = null;
function debouncePlanRecalc() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(fetchPlan, 250);
}

function resetDefaults() {
  state.storagePct = 60;
  state.inflowScale = 1.0;
  state.p90Scale = 1.0;
  state.demandScale = 1.0;
  state.units = 2;
  state.method = 'hybrid';
  state.source = 'whatif';

  document.getElementById('storage-slider').value = 60;
  document.getElementById('storage-val').textContent = '60%';
  document.getElementById('inflow-slider').value = 1.0;
  document.getElementById('inflow-val').textContent = '1.0x';
  document.getElementById('p90-slider').value = 1.0;
  document.getElementById('p90-val').textContent = '1.0x';
  document.getElementById('demand-slider').value = 1.0;
  document.getElementById('demand-val').textContent = '1.0x';

  document.querySelectorAll('.unit-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.units === '2');
  });
  if (document.getElementById('method-select')) document.getElementById('method-select').value = 'hybrid';
  if (document.getElementById('source-select')) document.getElementById('source-select').value = 'whatif';

  fetchPlan();
}

function simulateSpike() {
  state.inflowScale = 2.0;
  state.p90Scale = 1.8;
  document.getElementById('inflow-slider').value = 2.0;
  document.getElementById('inflow-val').textContent = '2.0x';
  document.getElementById('p90-slider').value = 1.8;
  document.getElementById('p90-val').textContent = '1.8x';
  fetchPlan();
}

async function checkApiHealth() {
  const statusPill = document.getElementById('status-pill');
  try {
    const res = await fetch(`${state.apiBase}/health`, { signal: AbortSignal.timeout(1500) });
    if (res.ok) {
      state.apiOnline = true;
      if (statusPill) {
        statusPill.className = 'status-pill';
        statusPill.innerHTML = '<span class="pulse-dot"></span> LIVE CONNECTED (127.0.0.1:8765)';
      }
      fetchPlan();
      return;
    }
  } catch (err) {
    // API server not running locally
  }
  state.apiOnline = false;
  if (statusPill) {
    statusPill.className = 'status-pill offline';
    statusPill.innerHTML = '<span class="pulse-dot"></span> OFFLINE SNAPSHOT (RUN OUTPUT)';
  }
  // Render using baseline run data
  renderBaseline();
}

async function fetchPlan() {
  if (!state.apiOnline) {
    renderBaselineSimulated();
    return;
  }

  const query = new URLSearchParams({
    storage_pct: state.storagePct,
    inflow_scale: state.inflowScale,
    p90_scale: state.p90Scale,
    demand_scale: state.demandScale,
    units: state.units,
    method: state.method,
    source: state.source,
    align: state.align
  });

  try {
    const [planRes, sumRes, methRes] = await Promise.all([
      fetch(`${state.apiBase}/plan?${query}`),
      fetch(`${state.apiBase}/plan/summary?${query}`),
      fetch(`${state.apiBase}/plan/methods?${query}`)
    ]);

    if (planRes.ok && sumRes.ok) {
      const planData = await planRes.json();
      const summaryData = await sumRes.json();
      const methodsData = methRes.ok ? await methRes.json() : BASELINE_METHODS;

      if (planData.length > 0) {
        state.currentSchedule = planData;
        state.currentSummary = summaryData[0];
        state.currentMethods = methodsData;
        updateUI();
        return;
      }
    }
  } catch (e) {
    console.warn('API call failed, falling back to local simulation:', e);
  }

  renderBaselineSimulated();
}

function renderBaseline() {
  state.currentSchedule = BASELINE_SCHEDULE;
  state.currentSummary = {
    date: BASELINE_REC.date,
    method: "Hybrid LP-DQN",
    release_m3s: BASELINE_REC.turbine_release_m3s,
    generation_mwh: BASELINE_REC.generation_mwh,
    end_storage_pct: BASELINE_REC.expected_end_storage_pct,
    level_masl: 205.51,
    mandatory_m3s: BASELINE_REC.mandatory_release_m3s,
    demand_weight: BASELINE_REC.demand_weight,
    plan_energy_mwh: 8812,
    spill_mcm: 0.0,
    floor_breach_days: 0,
    reserve_breach_days: 0,
    alert_level: 1,
    alert_text: "Flood watch (3 of next 3 days)"
  };
  state.currentAlerts = BASELINE_ALERTS;
  state.currentMethods = BASELINE_METHODS;
  updateUI();
}

function renderBaselineSimulated() {
  // Approximate what-if dynamic scaling in browser
  const inScale = state.inflowScale;
  const p90Scale = state.p90Scale;
  const uCap = state.units === 2 ? 48.0 : (state.units === 1 ? 24.0 : 0.0);
  
  let currentStorage = state.storagePct;
  const simSchedule = BASELINE_SCHEDULE.map((row, i) => {
    const inf50 = row.inflow_p50_m3s * inScale;
    const inf90 = row.inflow_p90_m3s * inScale * p90Scale;
    let rel = Math.min(uCap, inf50 * 0.85);
    if (currentStorage < 25) rel = Math.min(rel, 8.0);
    if (currentStorage > 80) rel = Math.min(uCap, rel + 10.0);
    
    // storage mass balance approx
    const deltaMcm = (inf50 - rel - 3.0) * 0.0864;
    currentStorage = Math.min(100, Math.max(15, currentStorage + (deltaMcm / 1.67) * 100));
    const gen = (rel / 48.0) * (state.units * 35 * 24) * 0.88 * row.demand_weight;

    return {
      ...row,
      inflow_p50_m3s: parseFloat(inf50.toFixed(2)),
      inflow_p90_m3s: parseFloat(inf90.toFixed(2)),
      turbine_release_m3s: parseFloat(rel.toFixed(2)),
      storage_pct: parseFloat(currentStorage.toFixed(1)),
      level_masl: parseFloat((204.0 + (currentStorage / 100.0) * 2.0).toFixed(2)),
      generation_mwh: parseFloat(gen.toFixed(1)),
      units: state.units
    };
  });

  const totEnergy = simSchedule.reduce((a, b) => a + b.generation_mwh, 0);
  const minStorage = Math.min(...simSchedule.map(s => s.storage_pct));

  state.currentSchedule = simSchedule;
  state.currentSummary = {
    date: simSchedule[0].date,
    method: state.method === 'hybrid' ? 'Hybrid LP-DQN' : (state.method === 'rolling_lp' ? 'Rolling LP' : 'DQN'),
    release_m3s: simSchedule[0].turbine_release_m3s,
    generation_mwh: simSchedule[0].generation_mwh,
    end_storage_pct: simSchedule[0].storage_pct,
    level_masl: simSchedule[0].level_masl,
    mandatory_m3s: 3.0,
    demand_weight: simSchedule[0].demand_weight,
    plan_energy_mwh: Math.round(totEnergy),
    spill_mcm: 0.0,
    floor_breach_days: 0,
    reserve_breach_days: minStorage < 20 ? 1 : 0,
    alert_level: inScale > 1.4 ? 2 : (inScale > 1.1 ? 1 : 0),
    alert_text: inScale > 1.4 ? "High flood alert - Inflow exceeds turbine discharge limit" : "Normal operating plan"
  };

  updateUI();
}

function updateUI() {
  const sum = state.currentSummary;
  if (!sum) return;

  // Update KPI Cards
  document.getElementById('kpi-release').textContent = sum.release_m3s.toFixed(1);
  document.getElementById('kpi-release-vol').textContent = `${(sum.release_m3s * 0.0864).toFixed(3)} MCM/d`;
  
  document.getElementById('kpi-gen').textContent = sum.generation_mwh.toFixed(0);
  document.getElementById('kpi-gen-cf').textContent = `Weight: x${sum.demand_weight.toFixed(3)}`;
  
  document.getElementById('kpi-storage').textContent = `${sum.end_storage_pct.toFixed(1)}%`;
  document.getElementById('kpi-level').textContent = `Level: ${sum.level_masl.toFixed(2)} masl`;

  document.getElementById('kpi-energy-15d').textContent = sum.plan_energy_mwh.toLocaleString();
  document.getElementById('kpi-energy-sub').textContent = `Horizon: 15 Days`;

  document.getElementById('kpi-floor-breaches').textContent = sum.floor_breach_days;
  
  // Alert Section
  const alertsCont = document.getElementById('alerts-container');
  if (alertsCont) {
    if (sum.alert_level > 0 && state.currentAlerts.length > 0) {
      alertsCont.style.display = 'flex';
      alertsCont.innerHTML = state.currentAlerts.map(a => `
        <div class="alert-card ${sum.alert_level === 1 ? 'warning' : ''}">
          <div class="alert-icon">⚠️</div>
          <div class="alert-text-group">
            <div class="alert-title">RESERVOIR HYDRAULIC WATCH</div>
            <div class="alert-desc">${a}</div>
          </div>
        </div>
      `).join('');
    } else {
      alertsCont.style.display = 'none';
    }
  }

  // Update Charts
  updateCharts();

  // Update 15-day Schedule Table
  renderScheduleTable();

  // Update Method Comparison Boxes
  renderMethodBoxes();
}

function initCharts() {
  // Chart 1: Discharge & Inflow Forecast
  const ctxDischarge = document.getElementById('chart-discharge')?.getContext('2d');
  if (ctxDischarge) {
    charts.discharge = new Chart(ctxDischarge, {
      type: 'line',
      data: {
        labels: [],
        datasets: [
          {
            label: 'Planned Release (m³/s)',
            data: [],
            borderColor: '#10b981',
            backgroundColor: 'rgba(16, 185, 129, 0.15)',
            borderWidth: 2.5,
            fill: true,
            tension: 0.25
          },
          {
            label: 'Inflow Median P50 (m³/s)',
            data: [],
            borderColor: '#06b6d4',
            borderDash: [5, 5],
            borderWidth: 2,
            tension: 0.25
          },
          {
            label: 'Inflow Upper P90 (m³/s)',
            data: [],
            borderColor: '#38bdf8',
            backgroundColor: 'rgba(56, 189, 248, 0.08)',
            borderWidth: 1.5,
            borderDash: [3, 3],
            fill: '+1'
          },
          {
            label: 'Mandatory Environmental Release (m³/s)',
            data: [],
            borderColor: '#f59e0b',
            borderWidth: 1.5,
            borderDash: [2, 2]
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: '#94a3b8', font: { family: 'Plus Jakarta Sans', size: 11 } } },
          tooltip: { mode: 'index', intersect: false }
        },
        scales: {
          x: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#64748b' } },
          y: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94a3b8' }, title: { display: true, text: 'Discharge m³/s', color: '#64748b' } }
        }
      }
    });
  }

  // Chart 2: Storage & Pond Elevation
  const ctxReservoir = document.getElementById('chart-reservoir')?.getContext('2d');
  if (ctxReservoir) {
    charts.reservoir = new Chart(ctxReservoir, {
      type: 'line',
      data: {
        labels: [],
        datasets: [
          {
            label: 'Storage (%)',
            data: [],
            borderColor: '#0ea5e9',
            backgroundColor: 'rgba(14, 165, 233, 0.2)',
            fill: true,
            borderWidth: 2.5,
            yAxisID: 'y'
          },
          {
            label: 'Pond Level (masl)',
            data: [],
            borderColor: '#a855f7',
            borderWidth: 2,
            borderDash: [4, 4],
            yAxisID: 'y1'
          },
          {
            label: '20% Reserve Floor',
            data: [],
            borderColor: '#f43f5e',
            borderDash: [6, 6],
            borderWidth: 1.5,
            pointRadius: 0,
            yAxisID: 'y'
          },
          {
            label: '50% Target',
            data: [],
            borderColor: '#f59e0b',
            borderDash: [6, 6],
            borderWidth: 1.5,
            pointRadius: 0,
            yAxisID: 'y'
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: '#94a3b8', font: { family: 'Plus Jakarta Sans', size: 11 } } }
        },
        scales: {
          x: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#64748b' } },
          y: {
            position: 'left',
            min: 0,
            max: 105,
            grid: { color: 'rgba(255, 255, 255, 0.05)' },
            ticks: { color: '#0ea5e9', callback: v => `${v}%` },
            title: { display: true, text: 'Active Storage %', color: '#0ea5e9' }
          },
          y1: {
            position: 'right',
            min: 203.5,
            max: 206.5,
            grid: { drawOnChartArea: false },
            ticks: { color: '#a855f7', callback: v => `${v.toFixed(1)}m` },
            title: { display: true, text: 'Elevation (masl)', color: '#a855f7' }
          }
        }
      }
    });
  }

  // Chart 3: Generation & Demand Weight
  const ctxGen = document.getElementById('chart-generation')?.getContext('2d');
  if (ctxGen) {
    charts.generation = new Chart(ctxGen, {
      type: 'bar',
      data: {
        labels: [],
        datasets: [
          {
            label: 'Generation (MWh)',
            data: [],
            backgroundColor: 'rgba(16, 185, 129, 0.7)',
            borderRadius: 4,
            yAxisID: 'y'
          },
          {
            type: 'line',
            label: 'Demand Weight',
            data: [],
            borderColor: '#f59e0b',
            borderWidth: 2,
            pointRadius: 3,
            yAxisID: 'y1'
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: '#94a3b8', font: { family: 'Plus Jakarta Sans', size: 11 } } }
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: '#64748b' } },
          y: {
            position: 'left',
            grid: { color: 'rgba(255, 255, 255, 0.05)' },
            ticks: { color: '#10b981' },
            title: { display: true, text: 'Daily Generation (MWh)', color: '#10b981' }
          },
          y1: {
            position: 'right',
            min: 0.8,
            max: 1.2,
            grid: { drawOnChartArea: false },
            ticks: { color: '#f59e0b' },
            title: { display: true, text: 'Demand Multiplier', color: '#f59e0b' }
          }
        }
      }
    });
  }

  // Chart 4: Methods Performance
  const ctxMethods = document.getElementById('chart-methods')?.getContext('2d');
  if (ctxMethods) {
    charts.methods = new Chart(ctxMethods, {
      type: 'bar',
      data: {
        labels: ['Hybrid LP-DQN', 'Rolling LP', 'DQN', 'Reference Rule'],
        datasets: [
          {
            label: '15-Day Energy (MWh)',
            data: [8812, 8812, 8640, 8450],
            backgroundColor: ['#10b981', '#0ea5e9', '#f43f5e', '#64748b']
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false }, ticks: { color: '#94a3b8' } },
          y: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94a3b8' } }
        }
      }
    });
  }
}

function updateCharts() {
  const sched = state.currentSchedule;
  if (!sched || sched.length === 0) return;

  const dates = sched.map(s => s.date ? s.date.slice(5) : `D${s.day}`);

  // Chart 1
  if (charts.discharge) {
    charts.discharge.data.labels = dates;
    charts.discharge.data.datasets[0].data = sched.map(s => s.turbine_release_m3s);
    charts.discharge.data.datasets[1].data = sched.map(s => s.inflow_p50_m3s);
    charts.discharge.data.datasets[2].data = sched.map(s => s.inflow_p90_m3s);
    charts.discharge.data.datasets[3].data = sched.map(s => s.mandatory_m3s || 3.0);
    charts.discharge.update();
  }

  // Chart 2
  if (charts.reservoir) {
    charts.reservoir.data.labels = dates;
    charts.reservoir.data.datasets[0].data = sched.map(s => s.storage_pct);
    charts.reservoir.data.datasets[1].data = sched.map(s => s.level_masl);
    charts.reservoir.data.datasets[2].data = sched.map(() => 20.0);
    charts.reservoir.data.datasets[3].data = sched.map(() => 50.0);
    charts.reservoir.update();
  }

  // Chart 3
  if (charts.generation) {
    charts.generation.data.labels = dates;
    charts.generation.data.datasets[0].data = sched.map(s => s.generation_mwh);
    charts.generation.data.datasets[1].data = sched.map(s => s.demand_weight);
    charts.generation.update();
  }
}

function renderScheduleTable() {
  const tbody = document.getElementById('schedule-table-body');
  if (!tbody) return;

  tbody.innerHTML = state.currentSchedule.map(row => `
    <tr>
      <td class="text-left">${row.date || `Day ${row.day}`}</td>
      <td><strong>${row.turbine_release_m3s.toFixed(2)}</strong></td>
      <td>${(row.turbine_release_m3 / 1e6).toFixed(3)}</td>
      <td>${row.inflow_p50_m3s.toFixed(2)}</td>
      <td>${row.generation_mwh.toFixed(1)}</td>
      <td>${row.storage_pct.toFixed(1)}%</td>
      <td>${row.level_masl.toFixed(2)}</td>
      <td>${row.net_head_m ? row.net_head_m.toFixed(1) : '183.5'}</td>
      <td>x${row.demand_weight.toFixed(3)}</td>
      <td><span class="badge-tag ${row.units === 2 ? 'safe' : (row.units === 1 ? 'info' : 'alert')}">${row.units} Units</span></td>
    </tr>
  `).join('');
}

function renderMethodBoxes() {
  const container = document.getElementById('methods-comparison-container');
  if (!container) return;

  container.innerHTML = state.currentMethods.map(m => `
    <div class="method-box ${m.method.includes('Hybrid') ? 'selected' : ''}">
      <div class="method-box-header">
        <span class="method-name">${m.method}</span>
        ${m.method.includes('Hybrid') ? '<span class="badge-tag safe">Selected</span>' : ''}
      </div>
      <div class="method-stat"><span>Day-1 Release:</span> <span class="val">${m.day1_release_m3s} m³/s</span></div>
      <div class="method-stat"><span>15-Day Energy:</span> <span class="val">${m.plan_energy_mwh.toLocaleString()} MWh</span></div>
      <div class="method-stat"><span>Ending Storage:</span> <span class="val">${m.final_storage_pct}%</span></div>
      <div class="method-stat"><span>Min Storage:</span> <span class="val">${m.min_storage_pct}%</span></div>
      <div class="method-stat"><span>Avoidable Spill:</span> <span class="val">${m.avoidable_spill_mcm} MCM</span></div>
      <div class="method-stat"><span>Floor Breaches:</span> <span class="badge-tag safe">0 Breaches</span></div>
    </div>
  `).join('');
}

function renderScoreboardTable() {
  const tbody = document.getElementById('scoreboard-table-body');
  if (!tbody) return;

  tbody.innerHTML = SCOREBOARD_DATA.map(r => `
    <tr>
      <td class="text-left"><strong>${r.method}</strong></td>
      <td><span class="badge-tag ${r.episode_score > 25 ? 'safe' : (r.episode_score > 0 ? 'info' : 'alert')}">${r.episode_score.toFixed(1)}</span></td>
      <td>${r.energy_gwh.toFixed(1)} GWh</td>
      <td>${r.capacity_factor_pct.toFixed(1)}%</td>
      <td>${r.avoidable_spill_mcm.toFixed(2)} MCM</td>
      <td>${r.reserve_breach_days.toFixed(1)} days</td>
      <td><span class="badge-tag safe">0</span></td>
      <td>${r.decision_ms < 1 ? '<1 ms' : `${r.decision_ms.toFixed(1)} ms`}</td>
    </tr>
  `).join('');
}

function exportScheduleCSV() {
  const headers = ['Date', 'Turbine_Release_m3s', 'Turbine_Release_m3', 'Inflow_P50_m3s', 'Generation_MWh', 'Storage_Pct', 'Pond_Level_masl', 'Net_Head_m', 'Demand_Weight', 'Units'];
  const rows = state.currentSchedule.map(s => [
    s.date,
    s.turbine_release_m3s,
    s.turbine_release_m3,
    s.inflow_p50_m3s,
    s.generation_mwh,
    s.storage_pct,
    s.level_masl,
    s.net_head_m || 183.5,
    s.demand_weight,
    s.units
  ]);

  const csvContent = "data:text/csv;charset=utf-8," + [headers.join(','), ...rows.map(e => e.join(','))].join('\n');
  const encodedUri = encodeURI(csvContent);
  const link = document.createElement('a');
  link.setAttribute('href', encodedUri);
  link.setAttribute('download', `kukule_ganga_schedule_${state.method}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}
