const monthSelect = document.getElementById("wiz-month");
const wizardState = {
  step: 1,
  agreement: null,
  employee: null,
  events: null,
  payroll: null,
  manualConceptValues: {},
  manualConceptEnabled: {},
};

for (let month = 1; month <= 12; month += 1) {
  const option = document.createElement("option");
  option.value = String(month).padStart(2, "0");
  option.textContent = String(month).padStart(2, "0");
  if (month === 5) option.selected = true;
  monthSelect.appendChild(option);
}

const money = (value) => new Intl.NumberFormat("es-AR", {
  style: "currency",
  currency: "ARS",
  minimumFractionDigits: 2,
}).format(Number(value || 0));

const quantityLabel = (value) => {
  const number = Number(value || 0);
  return new Intl.NumberFormat("es-AR", {
    minimumFractionDigits: Number.isInteger(number) ? 0 : 2,
    maximumFractionDigits: Number.isInteger(number) ? 0 : 2,
  }).format(number);
};

const canonical = (value) => String(value || "")
  .normalize("NFD")
  .replace(/[\u0300-\u036f]/g, "")
  .toUpperCase()
  .replace(/[^A-Z0-9]+/g, "_")
  .replace(/^_+|_+$/g, "");

const agreementWorkdayMetrics = () => {
  const jornada = wizardState.agreement?.jornada_tiempos?.jornada_estandar || {};
  const monthlyDays = Number(jornada.dias_mensuales || jornada.monthly_days || 30);
  const dailyHours = Number(jornada.maximo_horas_diarias || jornada.horas_diarias || jornada.daily_hours || 0);
  const monthlyHours = Number(jornada.horas_mensuales || jornada.monthly_hours || (dailyHours && monthlyDays ? dailyHours * monthlyDays : 200));
  return {
    monthlyHours,
    monthlyDays,
    dailyHours: dailyHours || (monthlyDays > 0 ? monthlyHours / monthlyDays : 0),
  };
};

const show = (id) => {
  document.querySelectorAll(".view").forEach((view) => view.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach((button) => button.classList.remove("active"));
  document.getElementById(id).classList.add("active");
  document.querySelector(`[data-tab="${id}"]`)?.classList.add("active");
};

const notify = (message, type = "success") => {
  const stack = document.getElementById("toast-stack");
  if (!stack) return;
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;
  stack.appendChild(toast);
  window.setTimeout(() => toast.remove(), 4200);
};

const showMessage = (target, message, type = "success") => {
  const element = document.getElementById(target);
  if (!element) return;
  element.className = `message-panel ${type}`;
  element.textContent = message;
  element.classList.remove("hidden");
};

const clearMessage = (target) => {
  const element = document.getElementById(target);
  if (element) element.classList.add("hidden");
};

const responseMessage = (data, fallback = "Operacion realizada correctamente.") => {
  if (!data) return fallback;
  if (data.detail) return String(data.detail);
  if (data.message) return String(data.message);
  if (data.status && typeof data.status === "string") return data.status;
  return fallback;
};

const renderAuditPanel = (target, audit) => {
  const element = document.getElementById(target);
  if (!element) return;
  const status = audit?.status || "WARNING";
  const issues = Array.isArray(audit?.issues) ? audit.issues : [];
  const recommendations = Array.isArray(audit?.recommendations) ? audit.recommendations : [];
  element.className = `audit-result-panel ${status.toLowerCase()}`;
  element.innerHTML = `
    <h3>Resultado: ${status}</h3>
    ${issues.length ? `<strong>Observaciones</strong><ul>${issues.map((issue) => `<li>${issue.message || issue}</li>`).join("")}</ul>` : "<p>Sin inconsistencias detectadas.</p>"}
    ${recommendations.length ? `<strong>Recomendaciones</strong><ul>${recommendations.map((item) => `<li>${item}</li>`).join("")}</ul>` : ""}
  `;
  element.classList.remove("hidden");
};

const readResponse = async (response) => {
  const text = await response.text();
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch {
    return { detail: text };
  }
};

const postJson = async (url, payload) => {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readResponse(response);
};

const getJson = async (url) => {
  const response = await fetch(url);
  return readResponse(response);
};

const asArray = (value, label = "items") => {
  if (Array.isArray(value)) return value;
  console.warn(`Expected ${label} array`, value);
  return [];
};

const renderAgreements = (agreements) => {
  agreements = asArray(agreements, "agreements");
  const tbody = document.getElementById("agreements-table");
  const count = document.getElementById("agreements-count");
  const metric = document.getElementById("metric-agreements");
  const query = document.getElementById("agreement-search").value.toLowerCase();
  const filtered = agreements.filter((agreement) => {
    const meta = agreement.metadata || {};
    return `${meta.agreement_id} ${meta.name} ${meta.version}`.toLowerCase().includes(query);
  });

  count.textContent = `Mostrando ${filtered.length} convenio${filtered.length === 1 ? "" : "s"}`;
  metric.textContent = String(agreements.length);

  if (!filtered.length) {
    tbody.innerHTML = `<tr><td colspan="7">Sin convenios cargados</td></tr>`;
    return;
  }

  tbody.innerHTML = filtered.map((agreement) => {
    const meta = agreement.metadata;
    return `
      <tr>
        <td>${meta.agreement_id}</td>
        <td>${meta.name}</td>
        <td>${meta.version}</td>
        <td>${meta.valid_from || "-"}</td>
        <td>${meta.valid_to || "-"}</td>
        <td><span class="status">Vigente</span></td>
        <td>
          <button class="icon-button" data-view-agreement="${meta.agreement_id}" data-version="${meta.version}">Ver</button>
          <button class="icon-button" data-activate-agreement="${meta.agreement_id}" data-version="${meta.version}">OK</button>
        </td>
      </tr>
    `;
  }).join("");
};

let agreementCache = [];
let employeeCache = [];
let selectedAgreement = null;

const activeAgreementsById = () => {
  const map = new Map();
  asArray(agreementCache, "agreementCache").forEach((agreement) => {
    const id = agreement.metadata?.agreement_id;
    if (!id) return;
    const current = map.get(id);
    if (!current || String(agreement.metadata.version) > String(current.metadata.version)) {
      map.set(id, agreement);
    }
  });
  return [...map.values()];
};

const populateAgreementSelects = () => {
  const agreements = activeAgreementsById();
  const options = agreements.map((agreement) => {
    const meta = agreement.metadata;
    return `<option value="${meta.agreement_id}">${meta.agreement_id} - ${meta.name}</option>`;
  }).join("");
  ["employee-agreement-select", "wiz-agreement-id"].forEach((id) => {
    const select = document.getElementById(id);
    if (!select) return;
    const current = select.value;
    select.innerHTML = options || `<option value="">Sin convenios cargados</option>`;
    if (current) select.value = current;
  });
  populateEmployeeCategorySelect();
};

const agreementById = (agreementId) => activeAgreementsById().find((agreement) => agreement.metadata?.agreement_id === agreementId);

const categoryZone = (category) => category?.zone || category?.location || "";

const categoriesForAgreement = (agreement, zone = "") => {
  const categories = agreement?.categories || [];
  const zoneFilter = canonical(zone);
  if (!zoneFilter) return categories;
  return categories.filter((category) => canonical(categoryZone(category)) === zoneFilter);
};

const agreementZones = (agreement) => {
  const zones = [];
  (agreement?.categories || []).forEach((category) => {
    const zone = categoryZone(category);
    if (zone && !zones.some((current) => canonical(current) === canonical(zone))) zones.push(zone);
  });
  return zones;
};

const syncEmployeeZoneField = (agreementId, selected = "") => {
  const field = document.getElementById("employee-zone-field");
  const select = document.getElementById("employee-zone-select");
  const agreement = agreementById(agreementId);
  const zones = agreementZones(agreement);
  if (!field || !select) return "";
  field.classList.toggle("hidden", zones.length === 0);
  if (!zones.length) {
    select.innerHTML = "";
    select.value = "";
    return "";
  }
  const current = selected || select.value;
  const extra = current && !zones.some((zone) => canonical(zone) === canonical(current))
    ? `<option value="${current}">${current}</option>`
    : "";
  select.innerHTML = `<option value="">Todas las zonas</option>${extra}${zones.map((zone) => (
    `<option value="${zone}">${zone}</option>`
  )).join("")}`;
  select.value = current || "";
  return select.value;
};

const populateCategorySelect = (selectId, agreementId, selected = "", options = {}) => {
  const select = document.getElementById(selectId);
  const agreement = agreementById(agreementId);
  if (!select) return;
  const categories = categoriesForAgreement(agreement, options.zone);
  select.innerHTML = categories.map((category) => (
    `<option value="${category.category_id}">${category.category_id} - ${category.name}${categoryZone(category) ? ` (${categoryZone(category)})` : ""}</option>`
  )).join("") || `<option value="">Sin puestos / roles</option>`;
  if (selected && categories.some((category) => category.category_id === selected)) select.value = selected;
};

const categoryLabel = (agreementId, categoryId) => {
  const category = agreementById(agreementId)?.categories?.find((item) => item.category_id === categoryId);
  return category ? `${category.category_id} - ${category.name}${categoryZone(category) ? ` (${categoryZone(category)})` : ""}` : categoryId;
};

const populateEmployeeCategorySelect = (selectedCategory = "", selectedZone = "") => {
  const agreementId = document.getElementById("employee-agreement-select")?.value;
  const zone = syncEmployeeZoneField(agreementId, selectedZone);
  populateCategorySelect("employee-category-select", agreementId, selectedCategory, { zone });
};

const yearsFromHireDate = (value) => {
  if (!value) return 0;
  const start = new Date(`${value}T00:00:00`);
  const now = new Date();
  let years = now.getFullYear() - start.getFullYear();
  const beforeAnniversary = now.getMonth() < start.getMonth() || (now.getMonth() === start.getMonth() && now.getDate() < start.getDate());
  if (beforeAnniversary) years -= 1;
  return Math.max(years, 0);
};

const setImportStages = (stages = []) => {
  const items = document.querySelectorAll("#agreement-import-stages li");
  items.forEach((item) => {
    const stage = stages.find((candidate) => candidate.name === item.dataset.stage);
    item.className = stage ? String(stage.status || "DONE").toLowerCase() : "";
  });
};

const renderWarnings = (warnings = []) => {
  const panel = document.getElementById("agreement-warnings");
  if (!warnings.length) {
    panel.innerHTML = "";
    panel.classList.remove("active");
    return;
  }
  panel.classList.add("active");
  panel.innerHTML = `<strong>Warnings de Gemini / validacion</strong>${warnings.map((warning) => `<span>${warning}</span>`).join("")}`;
};

const editableInput = (field, value, type = "text") => `<input data-field="${field}" type="${type}" value="${value ?? ""}">`;
const removeButton = () => `<button class="icon-button danger-row" data-remove-row="1">Quitar</button>`;

const renderAgreementEditor = (agreement) => {
  if (agreement?.detail) {
    showMessage("agreement-feedback", agreement.detail, "error");
    notify(agreement.detail, "error");
    return;
  }
  selectedAgreement = agreement;
  if (!agreement) return;
  const meta = agreement.metadata;
  document.getElementById("agreement-summary").innerHTML = `
    <strong>${meta.agreement_id} - ${meta.name}</strong>
    <span>Version ${meta.version}</span>
    <span>Estado ${meta.status || "-"}</span>
    <span>Vigencia ${meta.valid_from || "-"} a ${meta.valid_to || "-"}</span>
  `;
  renderCategoryRows(agreement.categories || []);
  renderSalaryRows("editor-remunerative", agreement.salary_model?.remunerative_items || []);
  renderSalaryRows("editor-non-remunerative", agreement.salary_model?.non_remunerative_items || []);
  renderDeductionRows(agreement.salary_model?.deductions || []);
  renderOvertimeRows(agreement.salary_model?.overtime_rules || []);
};

const renderCategoryRows = (rows) => {
  document.getElementById("editor-categories").innerHTML = rows.map((row) => `
    <tr>
      <td>${editableInput("category_id", row.category_id)}</td>
      <td>${editableInput("name", row.name)}</td>
      <td>${editableInput("zone", row.zone || row.location || "")}</td>
      <td>${editableInput("basic_salary", row.basic_salary, "number")}</td>
      <td>${removeButton()}</td>
    </tr>
  `).join("") || `<tr><td colspan="5">Sin puestos / roles</td></tr>`;
};

const renderSalaryRows = (target, rows) => {
  document.getElementById(target).innerHTML = rows.map((row) => `
    <tr>
      <td>${editableInput("code", row.code)}</td>
      <td>${editableInput("name", row.name)}</td>
      <td><select data-field="calculation_type"><option ${row.calculation_type === "FIXED" ? "selected" : ""}>FIXED</option><option ${row.calculation_type === "PERCENTAGE" ? "selected" : ""}>PERCENTAGE</option><option ${row.calculation_type === "FORMULA" ? "selected" : ""}>FORMULA</option></select></td>
      <td>${editableInput("base_reference", row.base_reference || "BASIC")}</td>
      <td>${editableInput("value", row.rate ?? row.amount ?? "", "number")}</td>
      <td>${removeButton()}</td>
    </tr>
  `).join("") || `<tr><td colspan="6">Sin conceptos</td></tr>`;
};

const renderDeductionRows = (rows) => {
  document.getElementById("editor-deductions").innerHTML = rows.map((row) => `
    <tr>
      <td>${editableInput("code", row.code)}</td>
      <td>${editableInput("name", row.name)}</td>
      <td>${editableInput("rate", row.rate, "number")}</td>
      <td>${editableInput("base", row.base || "REMUNERATIVE_TOTAL")}</td>
      <td>
        <select data-field="application_type">
          <option value="MANDATORY" ${row.application_type !== "EMPLOYEE_OPT_IN" ? "selected" : ""}>Obligatoria</option>
          <option value="EMPLOYEE_OPT_IN" ${row.application_type === "EMPLOYEE_OPT_IN" ? "selected" : ""}>Depende del trabajador</option>
        </select>
      </td>
      <td>${editableInput("applies_when", row.applies_when || "")}</td>
      <td>${removeButton()}</td>
    </tr>
  `).join("") || `<tr><td colspan="7">Sin descuentos</td></tr>`;
};

const renderOvertimeRows = (rows) => {
  document.getElementById("editor-overtime").innerHTML = rows.map((row) => `
    <tr>
      <td>${editableInput("code", row.code)}</td>
      <td>${editableInput("multiplier", row.multiplier, "number")}</td>
      <td>${removeButton()}</td>
    </tr>
  `).join("") || `<tr><td colspan="3">Sin reglas de horas extra</td></tr>`;
};

const rowsFromTable = (target, mapper) => [...document.querySelectorAll(`#${target} tr`)]
  .filter((row) => row.querySelector("[data-field]"))
  .map(mapper);

const collectSalaryRows = (target, itemType) => rowsFromTable(target, (row) => {
  const data = fieldMap(row);
  const item = {
    code: data.code,
    name: data.name,
    type: itemType,
    calculation_type: data.calculation_type || "FIXED",
    base_reference: data.base_reference || "BASIC",
  };
  const value = Number(data.value || 0);
  if (item.calculation_type === "PERCENTAGE") item.rate = value;
  else item.amount = value;
  return item;
});

const fieldMap = (row) => {
  const data = {};
  row.querySelectorAll("[data-field]").forEach((input) => {
    data[input.dataset.field] = input.value;
  });
  return data;
};

const collectAgreementFromEditor = () => {
  if (!selectedAgreement) return null;
  const agreement = structuredClone(selectedAgreement);
  agreement.categories = rowsFromTable("editor-categories", (row) => {
    const data = fieldMap(row);
    return {
      category_id: data.category_id,
      name: data.name,
      zone: data.zone || null,
      location: data.zone || null,
      basic_salary: Number(data.basic_salary || 0),
    };
  });
  agreement.salary_model.remunerative_items = collectSalaryRows("editor-remunerative", "REMUNERATIVE");
  agreement.salary_model.non_remunerative_items = collectSalaryRows("editor-non-remunerative", "NON_REMUNERATIVE");
  agreement.salary_model.deductions = rowsFromTable("editor-deductions", (row) => {
    const data = fieldMap(row);
    return {
      code: data.code,
      name: data.name,
      rate: Number(data.rate || 0),
      base: data.base || "REMUNERATIVE_TOTAL",
      application_type: data.application_type || "MANDATORY",
      applies_when: data.applies_when || null,
      requires_employee_flag: data.application_type === "EMPLOYEE_OPT_IN" ? "union_affiliated" : null,
    };
  });
  agreement.salary_model.overtime_rules = rowsFromTable("editor-overtime", (row) => {
    const data = fieldMap(row);
    return { code: data.code, multiplier: Number(data.multiplier || 1) };
  });
  return agreement;
};

const putJson = async (url, payload) => {
  const response = await fetch(url, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  return readResponse(response);
};

const loadAgreements = async () => {
  const response = await getJson("/agreements");
  agreementCache = asArray(response, "agreements response");
  renderAgreements(agreementCache);
  populateAgreementSelects();
  renderEmployees(employeeCache);
};

const renderEmployees = (employees) => {
  employees = asArray(employees, "employees");
  const tbody = document.getElementById("employees-table");
  if (!tbody) return;
  if (!employees.length) {
    tbody.innerHTML = `<tr><td colspan="8">Sin empleados cargados</td></tr>`;
    return;
  }
  tbody.innerHTML = employees.map((employee) => `
    <tr>
      <td>${employee.employee_id}</td>
      <td>${employee.cuil || "-"}</td>
      <td>${employee.agreement_id}</td>
      <td>${categoryLabel(employee.agreement_id, employee.category_id)}</td>
      <td>${employee.hire_date || "-"}</td>
      <td>${employee.seniority_years}</td>
      <td>${employee.union_affiliated ? "Si" : "No"}</td>
      <td><button class="icon-button" data-edit-employee="${employee.employee_id}">Editar</button></td>
    </tr>
  `).join("");
};

const loadEmployees = async () => {
  const response = await getJson("/employees");
  employeeCache = asArray(response, "employees response");
  renderEmployees(employeeCache);
};

const resetEmployeeForm = () => {
  const form = document.getElementById("employee-form");
  form.reset();
  document.getElementById("employee-editing-id").value = "";
  document.getElementById("employee-save-button").textContent = "Guardar empleado";
  document.querySelector("#employee-form [name='employee_id']").disabled = false;
  document.getElementById("employee-seniority-preview").value = 0;
  form.elements.union_affiliated.checked = false;
  populateAgreementSelects();
  populateEmployeeCategorySelect();
};

const fillEmployeeForm = (employee) => {
  const form = document.getElementById("employee-form");
  document.getElementById("employee-editing-id").value = employee.employee_id;
  form.elements.employee_id.value = employee.employee_id;
  form.elements.employee_id.disabled = true;
  form.elements.cuil.value = employee.cuil || "";
  form.elements.hire_date.value = employee.hire_date || "";
  form.elements.agreement_id.value = employee.agreement_id;
  const category = agreementById(employee.agreement_id)?.categories?.find((item) => item.category_id === employee.category_id);
  populateEmployeeCategorySelect(employee.category_id, employee.zone || categoryZone(category));
  form.elements.workday.value = employee.workday || "";
  form.elements.union_affiliated.checked = Boolean(employee.union_affiliated);
  document.getElementById("employee-seniority-preview").value = employee.seniority_years || 0;
  document.getElementById("employee-save-button").textContent = "Actualizar empleado";
};

const periodValue = () => `${document.getElementById("wiz-year").value}-${document.getElementById("wiz-month").value}`;

const activeCategory = () => {
  const categoryId = document.getElementById("wiz-category-id").value;
  return wizardState.agreement?.categories?.find((category) => category.category_id === categoryId);
};

const buildWizardEvents = () => {
  const events = [];
  const pushDays = (type, subtype, id) => {
    const days = Number(document.getElementById(id).value || 0);
    if (days > 0) events.push({ type, subtype, days });
  };
  const pushAmount = (subtype, id, description) => {
    const amount = Number(document.getElementById(id).value || 0);
    if (amount > 0) events.push({ type: "BONUS", subtype, amount, description });
  };

  pushDays("ABSENCE", "JUSTIFIED", "ev-absence-justified");
  pushDays("ABSENCE", "UNJUSTIFIED", "ev-absence-unjustified");
  pushDays("LEAVE", "SICKNESS", "ev-leave-sickness");
  pushDays("LEAVE", "ACCIDENT", "ev-leave-accident");
  pushDays("LEAVE", "MARRIAGE", "ev-leave-marriage");
  pushDays("LEAVE", "EXAM", "ev-leave-exam");
  pushDays("LEAVE", "BIRTH", "ev-leave-birth");
  pushDays("HOLIDAY_WORKED", "WORKED", "ev-holiday-worked");
  pushDays("HOLIDAY_WORKED", "NOT_WORKED", "ev-holiday-not-worked");
  pushDays("SUSPENSION", "GENERAL", "ev-suspensions");
  const workedHours = Number(document.getElementById("ev-worked-hours").value || 0);
  const workedDays = Number(document.getElementById("ev-worked-days").value || 0);
  if (workedHours > 0) events.push({ type: "WORKED_HOURS", subtype: "HORAS_TRABAJADAS", hours: workedHours });
  if (workedDays > 0) events.push({ type: "WORKED_DAYS", subtype: "DIAS_TRABAJADOS", days: workedDays });
  pushAmount("COMMISSION", "ev-commissions", "Comisiones");
  pushAmount("BONUS", "ev-bonuses", "Bonos");
  const liquidationType = document.getElementById("wiz-liquidation-type").value;
  if (liquidationType && liquidationType !== "mensual") {
    events.push({
      type: "LIQUIDATION",
      subtype: liquidationType.toUpperCase(),
      description: `Tipo de liquidacion: ${liquidationType}`,
    });
  }

  document.querySelectorAll("[data-overtime-code]").forEach((input) => {
    const hours = Number(input.value || 0);
    if (hours > 0) events.push({ type: "OVERTIME", subtype: input.dataset.overtimeCode, hours });
  });
  document.querySelectorAll("[data-manual-concept-toggle]").forEach((toggle) => {
    if (!toggle.checked) return;
    const code = toggle.dataset.manualConceptToggle;
    const unit = String(toggle.dataset.manualConceptUnit || "").toUpperCase();
    const quantityInput = document.querySelector(`[data-manual-concept-quantity="${code}"]`);
    const quantity = quantityInput ? Number(quantityInput.value || 0) : 1;
    if (quantity > 0) {
      const event = {
        type: "SALARY_ITEM",
        subtype: code,
        description: `${toggle.dataset.manualConceptName || code}${unit ? ` (${unit})` : ""}`,
      };
      if (unit === "AMOUNT") {
        event.amount = quantity;
      } else {
        event.quantity = quantity;
      }
      events.push(event);
    }
  });

  return {
    employee_id: document.getElementById("wiz-employee-id").value,
    period: periodValue(),
    events,
  };
};

const captureManualConceptValues = () => {
  document.querySelectorAll("[data-manual-concept-quantity]").forEach((input) => {
    wizardState.manualConceptValues[input.dataset.manualConceptQuantity] = input.value;
  });
  document.querySelectorAll("[data-manual-concept-toggle]").forEach((input) => {
    wizardState.manualConceptEnabled[input.dataset.manualConceptToggle] = input.checked;
  });
};

const unitLabel = (unit) => ({
  KM: "Kilometros",
  DAY: "Dias",
  TRIP: "Viajes",
  NIGHT: "Noches",
  AMOUNT: "Importe",
  HOUR: "Horas",
})[String(unit || "").toUpperCase()] || "Cantidad";

const hasDailyViaticoCode = (item) => {
  const code = canonical(item?.code || "");
  return code.startsWith("VIAT_") || code.startsWith("VIATICO_");
};

const effectiveUnit = (item) => {
  const explicit = String(item.unit || "").toUpperCase();
  if (explicit) return explicit;
  const value = canonical(`${item.code} ${item.name} ${item.base_reference} ${item.formula || ""}`);
  if (value.includes("KM") || value.includes("KILOMETRO")) return "KM";
  if (value.includes("PERNOCT")) return "NIGHT";
  if (value.includes("VIAJE")) return "TRIP";
  if (value.includes("HORA")) return "HOUR";
  if (
    hasDailyViaticoCode(item)
    || value.includes("DIA")
    || value.includes("DIAS")
    || value.includes("DAYS")
    || value.includes("DIARIO")
    || value.includes("JORNAL")
    || value.includes("REVISTA")
    || value.includes("COMIDA")
  ) return "DAY";
  if (item.input_mode === "MANUAL" && hasDailyViaticoCode(item)) return "DAY";
  if (value.includes("COMISION")) return "AMOUNT";
  return "";
};

const manualInputLabel = (item) => {
  const unit = effectiveUnit(item);
  if (unit === "DAY") return "Dias a liquidar";
  if (unit) return unitLabel(unit);
  if (item.calculation_type === "PERCENTAGE" || item.rate !== undefined && item.rate !== null) return "Aplicar";
  return "Cantidad";
};

const itemAppliesToWizardEmployee = (item, category) => {
  const categoryFilters = (item.applies_to_categories || []).map(canonical).filter(Boolean);
  if (categoryFilters.length) {
    if (!category) return true;
    const categoryValues = [category?.category_id, category?.name].map(canonical).filter(Boolean);
    const appliesToAll = categoryFilters.some((filter) => ["TODO", "TODOS", "TODA", "TODAS", "ALL"].includes(filter))
      || categoryFilters.some((filter) => ["PERSONAL", "TRABAJADORES"].includes(filter))
        && categoryFilters.some((filter) => ["TODO", "TODOS", "TODA", "TODAS"].includes(filter));
    const exceptIndex = categoryFilters.findIndex((filter) => ["EXCEPTO", "EXCEPT", "SALVO"].includes(filter));
    if (exceptIndex >= 0) {
      const excludedFilters = categoryFilters.slice(exceptIndex + 1);
      if (excludedFilters.some((filter) => categoryValues.some((value) => categoryTokensMatch(filter, value)))) return false;
      if (appliesToAll) return true;
    }
    if (!appliesToAll && !categoryFilters.some((filter) => categoryValues.some((value) => categoryTokensMatch(filter, value)))) return false;
  }

  const tagFilters = (item.applies_to_tags || []).map(canonical).filter(Boolean);
  if (!tagFilters.length) return true;
  if (!category) return true;
  const employeeValues = [
    document.getElementById("wiz-zone").value,
    document.getElementById("wiz-workday").value,
    category?.name,
    category?.zone,
    category?.location,
  ].map(canonical).filter(Boolean);
  const blob = employeeValues.join("_");
  return tagFilters.some((tag) => employeeValues.includes(tag) || blob.includes(tag));
};

const isManualSalaryItem = (item) => {
  if (item.input_mode === "MANUAL") return true;
  if (effectiveUnit(item)) return true;
  const value = canonical(`${item.code} ${item.name} ${item.base_reference}`);
  const coreAutoTokens = ["ANTIG", "ANTIGUEDAD", "SENIORITY", "PRESENTISMO", "ATTENDANCE", "ASISTENCIA"];
  if (coreAutoTokens.some((token) => value.includes(token))) return false;
  const conditionalTokens = [
    "ADIC",
    "ADICIONAL",
    "PLUS",
    "RAMA",
    "DIFERENCIAL",
    "PLURALIDAD",
  ];
  if ((item.applies_to_categories || []).length || (item.applies_to_tags || []).length) return true;
  if (conditionalTokens.some((token) => value.includes(token))) return true;
  if (hasDailyViaticoCode(item)) return true;
  return [
    "KM",
    "KILOMETRO",
    "KILOMETROS",
    "VIAJE",
    "VIAJES",
    "DIARIO",
    "DIARIOS",
    "REVISTAS",
    "COMISION",
    "COMISIONES",
    "PRODUCTIVIDAD",
  ].some((token) => value.includes(token));
};

const categoryTokensMatch = (filter, value) => {
  if (!filter || !value) return false;
  if (filter === value || filter.includes(value) || value.includes(filter)) return true;
  const equivalents = [
    ["CHOFER", "CHOFERES", "CONDUCTOR", "CONDUCTORES"],
    ["AUXILIAR", "AYUDANTE", "AYUDANTES"],
    ["PEON", "PEONES"],
    ["RECOLECTOR", "RECOLECTORES", "RECOLECCION", "RESIDUOS"],
    ["ADMINISTRATIVO", "ADMINISTRACION"],
  ];
  return equivalents.some((group) => group.some((token) => filter.includes(token)) && group.some((token) => value.includes(token)));
};

const itemValueLabel = (item) => {
  if (item.calculation_type === "PERCENTAGE") return `${Number(item.rate || 0)}%`;
  if (item.amount !== undefined && item.amount !== null) return money(item.amount);
  return item.calculation_type || "FORMULA";
};

const manualConceptCard = (item) => {
  const unit = effectiveUnit(item);
  const enabled = Boolean(wizardState.manualConceptEnabled[item.code]);
  const value = wizardState.manualConceptValues[item.code] ?? (unit ? "0" : "1");
  const label = manualInputLabel(item);
  const hasQuantity = Boolean(unit);
  return `
    <article class="concept-card manual-concept">
      <div>
        <strong>${item.name || item.code}</strong>
        <small>${item.code} - ${item.type === "REMUNERATIVE" ? "Remunerativo" : "No remunerativo"}</small>
        <small>Valor unitario: ${itemValueLabel(item)}${unit ? ` / ${unit}` : ""}</small>
        ${hasQuantity ? "<small>Activar y cargar la cantidad correspondiente</small>" : "<small>Activar para incluir este haber en la liquidacion</small>"}
      </div>
      <div class="manual-controls">
        <label class="switch-control">
          <input
            data-manual-concept-toggle="${item.code}"
            data-manual-concept-name="${item.name || item.code}"
            data-manual-concept-unit="${unit || ""}"
            data-manual-concept-type="${item.type || ""}"
            type="checkbox"
            ${enabled ? "checked" : ""}>
          <span></span>
          <em>${enabled ? "Activo" : "Inactivo"}</em>
        </label>
        ${hasQuantity ? `
          <label class="manual-quantity ${enabled ? "" : "hidden"}">${label}
            <input
              data-manual-concept-quantity="${item.code}"
              data-manual-concept-name="${item.name || item.code}"
              data-manual-concept-unit="${unit || ""}"
              data-manual-concept-type="${item.type || ""}"
              type="number"
              min="0"
              step="0.01"
              placeholder="0"
              value="${value}"
              ${enabled ? "" : "disabled"}>
          </label>
        ` : ""}
      </div>
    </article>
  `;
};

const conceptSection = (title, items, emptyText, renderer) => `
  <section class="concept-section">
    <header>
      <h3>${title}</h3>
      <span>${items.length}</span>
    </header>
    <div class="concept-list inner">
      ${items.length ? items.map(renderer).join("") : `<div class="empty-state">${emptyText}</div>`}
    </div>
  </section>
`;

const deductionCard = (deduction) => `
  <article class="concept-card">
    <div>
      <strong>${deduction.name || deduction.code}</strong>
      <small>${deduction.code} - Base: ${deduction.base || "REMUNERATIVE_TOTAL"}</small>
      ${deduction.applies_when ? `<small>${deduction.applies_when}</small>` : ""}
    </div>
    <span>${Number(deduction.rate || 0)}%</span>
  </article>
`;

const renderAgreementDrivenSections = () => {
  captureManualConceptValues();
  const additionals = document.getElementById("agreement-additionals");
  const overtime = document.getElementById("overtime-rules");
  const rules = document.getElementById("event-rules-preview");
  const agreement = wizardState.agreement;
  const category = activeCategory();

  if (!agreement) {
    additionals.innerHTML = `<div class="empty-state">Selecciona un convenio activo para leer conceptos remunerativos y no remunerativos.</div>`;
    overtime.innerHTML = "";
    return;
  }

  const salaryModel = agreement.salary_model || {};
  const allItems = [
    ...(salaryModel.remunerative_items || []),
    ...(salaryModel.non_remunerative_items || []),
  ].filter((item) => item.code !== "BASIC");
  const automaticItems = allItems.filter((item) => !isManualSalaryItem(item) && itemAppliesToWizardEmployee(item, category));
  const manualItems = allItems.filter((item) => isManualSalaryItem(item));
  const visibleItems = [...automaticItems, ...manualItems];
  const automaticRemunerative = automaticItems.filter((item) => item.type === "REMUNERATIVE");
  const automaticNonRemunerative = automaticItems.filter((item) => item.type === "NON_REMUNERATIVE");
  const manualRemunerative = manualItems.filter((item) => item.type === "REMUNERATIVE");
  const manualNonRemunerative = manualItems.filter((item) => item.type === "NON_REMUNERATIVE");
  const deductions = salaryModel.deductions || [];
  const mandatoryDeductions = deductions.filter((item) => String(item.application_type || "MANDATORY").toUpperCase() === "MANDATORY");
  const conditionalDeductions = deductions.filter((item) => String(item.application_type || "MANDATORY").toUpperCase() !== "MANDATORY");

  additionals.innerHTML = visibleItems.length || deductions.length
    ? [
      conceptSection("Haberes remunerativos automaticos", automaticRemunerative, "Sin haberes remunerativos automaticos para este convenio.", (item) => `
          <article class="concept-card">
            <div>
              <strong>${item.name || item.code}</strong>
              <small>${item.code}</small>
            </div>
            <span>${itemValueLabel(item)}</span>
          </article>
        `),
      conceptSection("Haberes remunerativos de carga manual", manualRemunerative, "Este convenio no tiene haberes remunerativos manuales activos.", manualConceptCard),
      conceptSection("Haberes no remunerativos automaticos", automaticNonRemunerative, "Sin haberes no remunerativos automaticos para este convenio.", (item) => `
          <article class="concept-card">
            <div>
              <strong>${item.name || item.code}</strong>
              <small>${item.code}</small>
            </div>
            <span>${itemValueLabel(item)}</span>
          </article>
        `),
      conceptSection("Haberes no remunerativos de carga manual", manualNonRemunerative, "Este convenio no tiene haberes no remunerativos manuales activos.", manualConceptCard),
      conceptSection("Retenciones obligatorias del convenio", mandatoryDeductions, "Este convenio no declara retenciones obligatorias.", deductionCard),
      conceptSection("Retenciones segun condicion del trabajador", conditionalDeductions, "Este convenio no declara retenciones condicionales.", deductionCard),
    ].join("")
    : `<div class="empty-state">El convenio no declara adicionales en salary_model.</div>`;

  const baseSalary = Number(category?.basic_salary || 0);
  const metrics = agreementWorkdayMetrics();
  const hourly = metrics.monthlyHours > 0 ? baseSalary / metrics.monthlyHours : 0;
  overtime.innerHTML = (salaryModel.overtime_rules || []).map((rule) => `
    <article class="overtime-card">
      <div>
        <strong>${rule.code}</strong>
        <small>Valor hora: ${money(hourly)} x ${rule.multiplier}</small>
      </div>
      <label>Horas<input data-overtime-code="${rule.code}" type="number" min="0" value="0"></label>
      <strong>${money(hourly * Number(rule.multiplier || 1))}</strong>
    </article>
  `).join("") || `<div class="empty-state">El convenio no declara overtime_rules.</div>`;

  rules.textContent = (agreement.event_rules || []).length
    ? `Reglas detectadas: ${agreement.event_rules.map((rule) => `${rule.event_type}/${rule.subtype || "*"}`).join(", ")}`
    : "El convenio no declara event_rules.";
};

const loadEmployeeIntoWizard = async () => {
  const employeeId = document.getElementById("wiz-employee-id").value;
  if (!employeeId) return;
  const employee = await getJson(`/employees/${employeeId}`);
  if (employee.detail) return;

  wizardState.employee = employee;
  document.getElementById("wiz-cuil").value = employee.cuil || "";
  document.getElementById("wiz-hire-date").value = employee.hire_date || "";
  document.getElementById("wiz-agreement-id").value = employee.agreement_id || "";
  populateCategorySelect("wiz-category-id", employee.agreement_id, employee.category_id);
  document.getElementById("wiz-seniority").value = employee.seniority_years || 0;
  document.getElementById("wiz-zone").value = employee.zone || "";
  document.getElementById("wiz-workday").value = employee.workday || "Completa";

  wizardState.agreement = await getJson(`/agreements/${employee.agreement_id}`);
  if (!wizardState.agreement.categories.some((category) => category.category_id === employee.category_id)) {
    showMessage("payroll-result", "El puesto/rol del empleado no pertenece al convenio activo.", "error");
  }
  renderAgreementDrivenSections();
};

const setWizardStep = (step) => {
  wizardState.step = Math.max(1, Math.min(6, step));
  document.querySelectorAll("[data-step-panel]").forEach((panel) => {
    panel.classList.toggle("active", Number(panel.dataset.stepPanel) === wizardState.step);
  });
  document.querySelectorAll("#payroll-stepper li").forEach((item) => {
    const itemStep = Number(item.dataset.step);
    item.classList.toggle("active", itemStep === wizardState.step);
    item.classList.toggle("done", itemStep < wizardState.step);
  });
  document.getElementById("wizard-prev").disabled = wizardState.step === 1;
  document.getElementById("wizard-next").classList.toggle("hidden", wizardState.step === 6);
  document.getElementById("wizard-calculate").classList.toggle("hidden", wizardState.step !== 6);
  if (wizardState.step === 4 || wizardState.step === 5) renderAgreementDrivenSections();
};

const receiptAmount = (item) => item.type === "DEDUCTION"
  ? Math.abs(Number(item.amount || 0))
  : Number(item.amount || 0);

const receiptGroup = (title, items) => `
  <article class="receipt-card">
    <h3>${title}</h3>
    ${items.length ? items.map((item) => {
      const value = receiptAmount(item);
      return `<div class="${value < 0 ? "negative" : ""}"><span>${item.name}</span><strong>${money(value)}</strong></div>`;
    }).join("") : "<small>Sin conceptos</small>"}
    <div class="receipt-total"><span>Total ${title.toLowerCase()}</span><strong>${money(items.reduce((total, item) => total + receiptAmount(item), 0))}</strong></div>
  </article>
`;

const salaryItemsByCode = () => {
  const model = wizardState.agreement?.salary_model || {};
  return new Map([
    ...(model.remunerative_items || []),
    ...(model.non_remunerative_items || []),
  ].map((item) => [item.code, item]));
};

const deductionsByCode = () => {
  const model = wizardState.agreement?.salary_model || {};
  return new Map((model.deductions || []).map((item) => [item.code, item]));
};

const eventsBySubtype = () => new Map((wizardState.events?.events || []).map((event) => [event.subtype, event]));

const overtimeByCode = () => {
  const model = wizardState.agreement?.salary_model || {};
  return new Map((model.overtime_rules || []).map((rule) => [rule.code, rule]));
};

const explainPayrollDetail = (detail) => {
  const category = activeCategory();
  const baseSalary = Number(category?.basic_salary || 0);
  const salaryItem = salaryItemsByCode().get(detail.code);
  const deduction = deductionsByCode().get(detail.code);
  const event = eventsBySubtype().get(detail.code);
  const overtime = overtimeByCode().get(detail.code);

  if (detail.code === "BASIC") {
    return `Basico del puesto/rol ${category?.name || ""}: ${money(baseSalary)}`;
  }

  if (salaryItem) {
    const base = salaryItem.base_reference && !["", "NO_INDICADO"].includes(String(salaryItem.base_reference).toUpperCase())
      ? salaryItem.base_reference
      : "Basico";
    const quantity = Number(event?.quantity || event?.days || event?.hours || 0);
    if (quantity > 0) {
      const unit = effectiveUnit(salaryItem);
      const unitValue = Math.abs(Number(detail.amount || 0)) / quantity;
      return `${salaryItem.name || detail.name} = ${money(unitValue)} x ${quantity}${unit ? ` ${unitLabel(unit).toLowerCase()}` : ""}`;
    }
    if (salaryItem.calculation_type === "PERCENTAGE" || salaryItem.rate !== undefined && salaryItem.rate !== null) {
      return `${salaryItem.name || detail.name} = ${base} x ${Number(salaryItem.rate || 0)}%`;
    }
    if (salaryItem.calculation_type === "FORMULA" && salaryItem.formula) {
      return `${salaryItem.name || detail.name} = ${salaryItem.formula}`;
    }
    if (salaryItem.amount !== undefined && salaryItem.amount !== null) {
      return `${salaryItem.name || detail.name} = importe fijo ${money(salaryItem.amount)}`;
    }
  }

  if (overtime || detail.code.startsWith("OT_")) {
    const hours = Number(event?.hours || 0);
    const multiplier = Number(overtime?.multiplier || 1);
    const metrics = agreementWorkdayMetrics();
    const hourly = metrics.monthlyHours > 0 ? baseSalary / metrics.monthlyHours : 0;
    return `Horas extra = ${money(hourly)} valor hora x ${multiplier} x ${hours} horas`;
  }

  if (detail.code.startsWith("HOLIDAY_WORKED")) {
    const event = (wizardState.events?.events || []).find((item) => item.type === "HOLIDAY_WORKED");
    const days = Number(event?.days || 0);
    return `Feriado trabajado = (${money(baseSalary)} / 30) x 2 x ${days} dias`;
  }

  if (detail.code.startsWith("ABSENCE") || detail.amount < 0 && detail.type === "REMUNERATIVE") {
    const event = (wizardState.events?.events || []).find((item) => detail.code.startsWith(item.type));
    const days = Number(event?.days || 0);
    return `Descuento por novedad = (${money(baseSalary)} / 30) x ${days} dias`;
  }

  if (deduction || detail.type === "DEDUCTION") {
    const rate = Number(deduction?.rate || 0);
    const base = deduction?.base || "Total remunerativo";
    return `${deduction?.name || detail.name} = ${base} x ${rate}%`;
  }

  if (detail.type === "BONUS") {
    return `${detail.name} = importe cargado manualmente ${money(detail.amount)}`;
  }

  return `${detail.name} = importe liquidado ${money(detail.amount)}`;
};

const renderPayrollResult = (payroll) => {
  const details = payroll.details || [];
  const remunerative = details.filter((detail) => detail.type === "REMUNERATIVE");
  const nonRemunerative = details.filter((detail) => detail.type === "NON_REMUNERATIVE");
  const deductions = details.filter((detail) => detail.type === "DEDUCTION");
  const category = activeCategory();
  const metrics = agreementWorkdayMetrics();
  const monthlyHours = metrics.monthlyHours;
  const monthlyDays = metrics.monthlyDays;
  const dailyHours = metrics.dailyHours;
  const baseSalary = Number(category?.basic_salary || 0);
  const hourlyValue = monthlyHours > 0 ? baseSalary / monthlyHours : 0;
  const dailyValue = monthlyDays > 0 ? baseSalary / monthlyDays : 0;
  const workdayInfo = `
    <article class="receipt-card workday-card">
      <h3>Jornada del convenio</h3>
      <div><span>Horas de jornada diaria</span><strong>${quantityLabel(dailyHours)}</strong></div>
      <div><span>Dias base de liquidacion</span><strong>${quantityLabel(monthlyDays)}</strong></div>
      <div><span>Valor hora calculado</span><strong>${money(hourlyValue)}</strong></div>
      <div><span>Valor dia calculado</span><strong>${money(dailyValue)}</strong></div>
    </article>
  `;

  document.getElementById("summary-gross").textContent = money(payroll.gross_salary);
  document.getElementById("summary-deductions").textContent = `-${money(payroll.deductions)}`;
  document.getElementById("summary-net").textContent = money(payroll.net_salary);
  document.getElementById("receipt-detail").innerHTML = [
    workdayInfo,
    receiptGroup("Haberes remunerativos", remunerative),
    receiptGroup("Haberes no remunerativos", nonRemunerative),
    receiptGroup("Retenciones", deductions),
    `<article class="receipt-card total"><h3>Neto final</h3><strong>${money(payroll.net_salary)}</strong></article>`,
  ].join("");

  document.getElementById("formula-detail").innerHTML = details.map((detail) => (
    `<article><strong>${detail.name}</strong><span>${explainPayrollDetail(detail)}</span><em>${money(detail.amount)}</em></article>`
  )).join("");

  const gross = Number(payroll.gross_salary || 0);
  const deductionsValue = Number(payroll.deductions || 0);
  const net = Number(payroll.net_salary || 0);
  const max = Math.max(gross, deductionsValue, net, 1);
  document.getElementById("salary-chart").innerHTML = [
    ["Haberes", gross, "green"],
    ["Descuentos", deductionsValue, "red"],
    ["Neto", net, "blue"],
  ].map(([label, value, color]) => `
    <div class="bar-row">
      <span>${label}</span>
      <div><i class="${color}" style="width:${(Number(value) / max) * 100}%"></i></div>
      <strong>${money(value)}</strong>
    </div>
  `).join("");

  const contributions = Math.round(gross * 0.18 * 100) / 100;
  const art = Math.round(gross * 0.03 * 100) / 100;
  const social = Math.round(gross * 0.06 * 100) / 100;
  document.getElementById("employer-cost").innerHTML = `
    <div><span>Contribuciones</span><strong>${money(contributions)}</strong></div>
    <div><span>ART</span><strong>${money(art)}</strong></div>
    <div><span>Cargas sociales</span><strong>${money(social)}</strong></div>
    <div class="total"><span>Costo empleador estimado</span><strong>${money(gross + contributions + art + social)}</strong></div>
  `;
};

const calculateWizardPayroll = async () => {
  if (!wizardState.employee) {
    showMessage("payroll-result", "Primero selecciona un empleado valido para cargar su convenio activo.", "error");
    return;
  }
  if (!wizardState.agreement || wizardState.agreement.metadata.agreement_id !== wizardState.employee.agreement_id) {
    showMessage("payroll-result", "El convenio cargado no coincide con el convenio activo del empleado.", "error");
    return;
  }
  if (!wizardState.agreement.categories.some((category) => category.category_id === wizardState.employee.category_id)) {
    showMessage("payroll-result", "El puesto/rol del empleado no pertenece al convenio activo.", "error");
    return;
  }
  const eventsPayload = buildWizardEvents();
  wizardState.events = await postJson("/events", eventsPayload);
  wizardState.payroll = await postJson("/payroll/calculate", {
    employee_id: eventsPayload.employee_id,
    period: eventsPayload.period,
  });
  if (wizardState.payroll.estado && wizardState.payroll.estado !== "ok") {
    const missing = (wizardState.payroll.datos_faltantes || []).join(", ");
    const alerts = (wizardState.payroll.alertas || []).join(" ");
    showMessage("payroll-result", wizardState.payroll.mensaje || alerts || `Faltan datos: ${missing}`, wizardState.payroll.estado === "faltan_datos" ? "warning" : "error");
    notify(wizardState.payroll.mensaje || "La liquidacion requiere revision.", "warning");
    renderPayrollResult(wizardState.payroll);
    return;
  }
  showMessage("payroll-result", "Liquidacion calculada correctamente.", "success");
  notify("Liquidacion calculada correctamente.");
  renderPayrollResult(wizardState.payroll);
};

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", () => show(button.dataset.tab));
});

document.getElementById("refresh-agreements").addEventListener("click", loadAgreements);
document.getElementById("agreement-search").addEventListener("input", () => renderAgreements(agreementCache));

document.getElementById("agreements-table").addEventListener("click", async (event) => {
  const viewButton = event.target.closest("[data-view-agreement]");
  const activateButton = event.target.closest("[data-activate-agreement]");
  if (viewButton) {
    const id = viewButton.dataset.viewAgreement;
    const version = viewButton.dataset.version;
    document.getElementById("agreement-id").value = id;
    document.getElementById("agreement-version").value = version;
    const agreement = await getJson(`/agreements/${id}?version=${version}`);
    showMessage("agreement-feedback", `Convenio ${id} version ${version} cargado para edicion.`, "success");
    renderAgreementEditor(agreement);
  }
  if (activateButton) {
    const id = activateButton.dataset.activateAgreement;
    const version = activateButton.dataset.version;
    const result = await postJson(`/agreements/${id}/activate`, { version });
    showMessage("agreement-feedback", responseMessage(result, `Version ${version} activada correctamente.`), result.detail ? "error" : "success");
    notify(result.detail ? responseMessage(result) : `Version ${version} activada correctamente.`, result.detail ? "error" : "success");
    await loadAgreements();
  }
});

document.getElementById("upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const filesInput = document.getElementById("agreement-files");
  const status = document.getElementById("agreement-upload-status");
  const button = document.getElementById("create-agreement-button");
  if (!filesInput.files.length) {
    status.textContent = "Primero selecciona al menos un archivo del convenio.";
    status.className = "upload-status warning";
    return;
  }
  const data = new FormData();
  Array.from(filesInput.files).forEach((file) => data.append("files", file));

  status.textContent = `Extrayendo texto de ${filesInput.files.length} archivo(s) con Gemini...`;
  status.className = "upload-status loading";
  setImportStages([{ name: "Archivo recibido", status: "DONE" }, { name: "Extrayendo con Gemini", status: "RUNNING" }]);
  renderWarnings([]);
  button.disabled = true;
  button.textContent = "Procesando...";

  try {
    const response = await fetch("/agreements/upload-files", {
      method: "POST",
      body: data,
    });
    const result = await readResponse(response);
    const meta = result.agreement?.metadata;
    if (!response.ok || !meta) {
      throw new Error(result.detail || "No se pudo estructurar el convenio.");
    }
    setImportStages(result.stages || []);
    renderWarnings(result.warnings || []);
    status.textContent = `Convenio creado: ${meta.agreement_id} version ${meta.version}. Ya esta activo para liquidar y auditar.`;
    status.className = "upload-status success";
    showMessage("agreement-feedback", `Convenio ${meta.agreement_id} creado correctamente y listo para usar.`, "success");
    notify("Convenio creado correctamente.");
    event.target.reset();
    await loadAgreements();
  } catch (error) {
    const quotaExceeded = /429|quota|rate-limit|rate limit/i.test(error.message);
    status.textContent = quotaExceeded
        ? "Gemini no tiene cuota disponible para este proyecto. Active USE_MOCK_GEMINI=true para desarrollo o espere/restaure cuota para usar IA real."
        : `No se pudo crear el convenio: ${error.message}`;
    status.className = "upload-status error";
    setImportStages([
      { name: "Archivo recibido", status: "DONE" },
      { name: "Extrayendo con Gemini", status: "ERROR" },
    ]);
  } finally {
    button.disabled = false;
    button.textContent = "Crear convenio";
  }
});

document.getElementById("load-agreement").addEventListener("click", async () => {
  const id = document.getElementById("agreement-id").value;
  const version = document.getElementById("agreement-version").value;
  const url = version ? `/agreements/${id}?version=${version}` : `/agreements/${id}`;
  const agreement = await getJson(url);
  if (agreement.detail) {
    showMessage("agreement-feedback", agreement.detail, "error");
    notify(agreement.detail, "error");
    return;
  }
  showMessage("agreement-feedback", `Convenio ${agreement.metadata?.agreement_id || id} cargado para edicion.`, "success");
  renderAgreementEditor(agreement);
});

document.getElementById("activate-agreement").addEventListener("click", async () => {
  const id = document.getElementById("agreement-id").value;
  const version = document.getElementById("agreement-version").value;
  const result = await postJson(`/agreements/${id}/activate`, { version });
  showMessage("agreement-feedback", responseMessage(result, `Version ${version} activada correctamente.`), result.detail ? "error" : "success");
  notify(result.detail ? responseMessage(result) : `Version ${version} activada correctamente.`, result.detail ? "error" : "success");
  await loadAgreements();
});

document.getElementById("agreement-friendly-editor").addEventListener("click", (event) => {
  if (event.target.closest("[data-remove-row]")) {
    event.target.closest("tr").remove();
  }
});

document.getElementById("add-category-row").addEventListener("click", () => {
  const agreement = collectAgreementFromEditor();
  if (!agreement) return;
  renderCategoryRows([...(agreement.categories || []), { category_id: "NUEVO", name: "Nuevo puesto / rol", zone: "", basic_salary: 0 }]);
});

document.getElementById("add-remunerative-row").addEventListener("click", () => {
  const agreement = collectAgreementFromEditor();
  if (!agreement) return;
  renderSalaryRows("editor-remunerative", [...agreement.salary_model.remunerative_items, { code: "NUEVO", name: "Nuevo haber", type: "REMUNERATIVE", calculation_type: "FIXED", amount: 0 }]);
});

document.getElementById("add-non-remunerative-row").addEventListener("click", () => {
  const agreement = collectAgreementFromEditor();
  if (!agreement) return;
  renderSalaryRows("editor-non-remunerative", [...agreement.salary_model.non_remunerative_items, { code: "NUEVO_NR", name: "Nuevo no remunerativo", type: "NON_REMUNERATIVE", calculation_type: "FIXED", amount: 0 }]);
});

document.getElementById("add-deduction-row").addEventListener("click", () => {
  const agreement = collectAgreementFromEditor();
  if (!agreement) return;
  renderDeductionRows([...agreement.salary_model.deductions, { code: "NUEVO_DESC", name: "Nuevo descuento", rate: 0, base: "REMUNERATIVE_TOTAL" }]);
});

document.getElementById("add-overtime-row").addEventListener("click", () => {
  const agreement = collectAgreementFromEditor();
  if (!agreement) return;
  renderOvertimeRows([...agreement.salary_model.overtime_rules, { code: "OT_NUEVA", multiplier: 1.5 }]);
});

document.getElementById("save-agreement-friendly").addEventListener("click", async () => {
  if (!selectedAgreement) return;
  const agreement = collectAgreementFromEditor();
  if (!agreement) return;
  const result = await putJson(`/agreements/${agreement.metadata.agreement_id}`, agreement);
  showMessage("agreement-feedback", responseMessage(result, "Convenio actualizado correctamente."), result.detail ? "error" : "success");
  notify(result.detail ? responseMessage(result) : "Convenio actualizado correctamente.", result.detail ? "error" : "success");
  renderAgreementEditor(result);
  await loadAgreements();
});

document.getElementById("delete-agreement-friendly").addEventListener("click", async () => {
  if (!selectedAgreement) return;
  const meta = selectedAgreement.metadata;
  const ok = window.confirm(`Eliminar convenio ${meta.agreement_id} version ${meta.version}?`);
  if (!ok) return;
  const response = await fetch(`/agreements/${meta.agreement_id}?version=${meta.version}`, { method: "DELETE" });
  const result = await readResponse(response);
  showMessage("agreement-feedback", responseMessage(result, "Convenio eliminado correctamente."), response.ok ? "success" : "error");
  notify(response.ok ? "Convenio eliminado correctamente." : responseMessage(result), response.ok ? "success" : "error");
  selectedAgreement = null;
  document.getElementById("agreement-summary").innerHTML = "";
  renderCategoryRows([]);
  renderSalaryRows("editor-remunerative", []);
  renderSalaryRows("editor-non-remunerative", []);
  renderDeductionRows([]);
  renderOvertimeRows([]);
  await loadAgreements();
});

document.getElementById("employee-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.target;
  const data = Object.fromEntries(new FormData(form));
  data.union_affiliated = form.elements.union_affiliated.checked;
  const selectedCategory = agreementById(data.agreement_id)?.categories?.find((category) => category.category_id === data.category_id);
  data.zone = data.zone || categoryZone(selectedCategory) || "";
  const editingId = document.getElementById("employee-editing-id").value;
  if (editingId) data.employee_id = editingId;
  const result = editingId
    ? await fetch(`/employees/${editingId}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) }).then(readResponse)
    : await postJson("/employees", data);
  showMessage("employee-result", responseMessage(result, editingId ? "Empleado actualizado correctamente." : "Empleado creado correctamente."), result.detail ? "error" : "success");
  notify(result.detail ? responseMessage(result) : editingId ? "Empleado actualizado correctamente." : "Empleado creado correctamente.", result.detail ? "error" : "success");
  resetEmployeeForm();
  await loadEmployees();
});

document.getElementById("employee-agreement-select").addEventListener("change", () => populateEmployeeCategorySelect());
document.getElementById("employee-zone-select").addEventListener("change", () => populateEmployeeCategorySelect());
document.querySelector("#employee-form [name='hire_date']").addEventListener("change", (event) => {
  document.getElementById("employee-seniority-preview").value = yearsFromHireDate(event.target.value);
});
document.getElementById("refresh-employees").addEventListener("click", loadEmployees);
document.getElementById("employee-cancel-edit").addEventListener("click", resetEmployeeForm);
document.getElementById("employees-table").addEventListener("click", (event) => {
  const button = event.target.closest("[data-edit-employee]");
  if (!button) return;
  const employee = employeeCache.find((item) => item.employee_id === button.dataset.editEmployee);
  if (employee) fillEmployeeForm(employee);
});

document.getElementById("events-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = Object.fromEntries(new FormData(event.target));
  const events = [];
  const absence = Number(form.absence_unjustified || 0);
  const overtime50 = Number(form.overtime_50 || 0);
  const overtime100 = Number(form.overtime_100 || 0);
  const bonus = Number(form.bonus || 0);
  if (absence > 0) events.push({ type: "ABSENCE", subtype: "UNJUSTIFIED", days: absence });
  if (overtime50 > 0) events.push({ type: "OVERTIME", subtype: "OT_50", hours: overtime50 });
  if (overtime100 > 0) events.push({ type: "OVERTIME", subtype: "OT_100", hours: overtime100 });
  if (bonus > 0) events.push({ type: "BONUS", subtype: "BONUS", amount: bonus, description: "Bonos" });
  const result = await postJson("/events", {
    employee_id: form.employee_id,
    period: form.period,
    events,
  });
  showMessage("events-result", responseMessage(result, "Novedades registradas correctamente."), result.detail ? "error" : "success");
  notify(result.detail ? responseMessage(result) : "Novedades registradas correctamente.", result.detail ? "error" : "success");
});

document.getElementById("audit-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const audit = await postJson("/payroll/audit", Object.fromEntries(new FormData(event.target)));
  if (audit.detail) {
    showMessage("audit-result", audit.detail, "error");
    notify(audit.detail, "error");
    return;
  }
  renderAuditPanel("audit-result", audit);
  notify(`Auditoria finalizada: ${audit.status || "WARNING"}.`, audit.status === "APPROVED" ? "success" : "warning");
});

document.getElementById("wiz-employee-id").addEventListener("blur", loadEmployeeIntoWizard);
document.getElementById("wiz-category-id").addEventListener("input", renderAgreementDrivenSections);
document.getElementById("wiz-zone").addEventListener("input", renderAgreementDrivenSections);
document.getElementById("wiz-workday").addEventListener("change", renderAgreementDrivenSections);
document.getElementById("agreement-additionals").addEventListener("input", (event) => {
  const input = event.target.closest("[data-manual-concept-quantity]");
  if (input) wizardState.manualConceptValues[input.dataset.manualConceptQuantity] = input.value;
});
document.getElementById("agreement-additionals").addEventListener("change", (event) => {
  const toggle = event.target.closest("[data-manual-concept-toggle]");
  if (!toggle) return;
  const code = toggle.dataset.manualConceptToggle;
  wizardState.manualConceptEnabled[code] = toggle.checked;
  const quantityInput = document.querySelector(`[data-manual-concept-quantity="${code}"]`);
  if (quantityInput) {
    quantityInput.disabled = !toggle.checked;
    quantityInput.closest(".manual-quantity")?.classList.toggle("hidden", !toggle.checked);
    if (toggle.checked && !quantityInput.value) quantityInput.value = "0";
  }
  const label = toggle.closest(".switch-control")?.querySelector("em");
  if (label) label.textContent = toggle.checked ? "Activo" : "Inactivo";
});

document.getElementById("wizard-prev").addEventListener("click", () => setWizardStep(wizardState.step - 1));
document.getElementById("wizard-next").addEventListener("click", () => setWizardStep(wizardState.step + 1));
document.getElementById("payroll-stepper").addEventListener("click", (event) => {
  const item = event.target.closest("[data-step]");
  if (item) setWizardStep(Number(item.dataset.step));
});
document.getElementById("wizard-calculate").addEventListener("click", calculateWizardPayroll);

document.querySelectorAll(".tab-button").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".tab-button").forEach((tab) => tab.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((panel) => panel.classList.remove("active"));
    button.classList.add("active");
    document.getElementById(`result-${button.dataset.resultTab}`).classList.add("active");
  });
});

document.getElementById("wizard-audit").addEventListener("click", async () => {
  if (!wizardState.payroll) await calculateWizardPayroll();
  const audit = await postJson("/payroll/audit", {
    employee_id: document.getElementById("wiz-employee-id").value,
    period: periodValue(),
  });
  if (audit.detail) {
    showMessage("wizard-audit-result", audit.detail, "error");
    notify(audit.detail, "error");
    return;
  }
  renderAuditPanel("wizard-audit-result", audit);
  notify(`Auditoria finalizada: ${audit.status || "WARNING"}.`, audit.status === "APPROVED" ? "success" : "warning");
  const badge = document.getElementById("audit-badge");
  badge.textContent = audit.status || "WARNING";
  badge.className = `audit-badge ${(audit.status || "WARNING").toLowerCase()}`;
});

document.getElementById("new-payroll").addEventListener("click", () => {
  document.getElementById("payroll-wizard-form").reset();
  wizardState.agreement = null;
  wizardState.employee = null;
  wizardState.events = null;
  wizardState.payroll = null;
  wizardState.manualConceptValues = {};
  wizardState.manualConceptEnabled = {};
  renderAgreementDrivenSections();
  renderPayrollResult({ gross_salary: 0, deductions: 0, net_salary: 0, details: [] });
  clearMessage("wizard-audit-result");
  clearMessage("payroll-result");
  setWizardStep(1);
});

document.getElementById("clear-payroll").addEventListener("click", () => document.getElementById("new-payroll").click());

loadAgreements();
loadEmployees();
setWizardStep(1);
