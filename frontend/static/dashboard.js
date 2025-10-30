let CURRENT_PAGE = 1;
let CURRENT_PER_PAGE = 5;
let TOTAL_PAGES = 0;
let CURRENT_FILTERS = {}; // keep filters for export and paging
const RESTRICTED_STORAGE_KEY = "restrictedHours";
let RESTRICTED_HOURS = { start: "", end: "" };
let RESTRICTED_FILTER_ACTIVE = false;

// CRUD
async function fetchTraffic(query = "") {
  const qs = query
    ? query
    : new URLSearchParams({
        page: CURRENT_PAGE,
        per_page: CURRENT_PER_PAGE,
        plate_text: CURRENT_FILTERS.plate_text || "",
        start_ts: CURRENT_FILTERS.start_ts || "",
        end_ts: CURRENT_FILTERS.end_ts || "",
        restricted_start: CURRENT_FILTERS.restricted_start || "",
        restricted_end: CURRENT_FILTERS.restricted_end || "",
      }).toString();

  const res = await fetch(`/traffic?${qs}`);
  const payload = await res.json();
  const data = payload.items || payload;
  const meta = payload.meta || {
    page: 1,
    per_page: data.length,
    total: data.length,
  };

  TOTAL_PAGES = Math.max(1, Math.ceil(meta.total / meta.per_page));

  // update page UI
  document.getElementById(
    "pageInfo"
  ).textContent = `صفحه ${meta.page} از ${TOTAL_PAGES}`;
  document.getElementById(
    "totalRowsInfo"
  ).textContent = `تعداد کل: ${toFarsiNumber(meta.total)}`;
  const tbody = document.getElementById("plates_body");
  tbody.innerHTML = "";

  data.forEach((t) => {
    const tr = document.createElement("tr");

    const imgTd = document.createElement("td");
    imgTd.innerHTML = `<img src="/tiny_plate_image/${t.uuid}/plate" 
    onclick='openPlateImageModal("/plate_image/${
      t.uuid
    }/original", ${JSON.stringify(t).replace(/"/g, "&quot;")})'>`;
    tr.appendChild(imgTd);

    // Plate glyphs cell
    const plateTd = document.createElement("td");
    plateTd.appendChild(createPlateComponent(t.plate_text, t.uuid));
    tr.appendChild(plateTd);

    // Timestamp cell
    const tsTd = document.createElement("td");
    const date = new Date(t.timestamp);
    const tehranTime = date.toLocaleString("fa-IR", {
      timeZone: "Asia/Tehran",
      hour12: false,
    });
    const [tehranDate, tehranClock] = tehranTime.split(", ");
    tsTd.innerHTML = `
    <div>
      <span>${toFarsiNumber(tehranDate)}</span>
      <br/>
      <span>${toFarsiNumber(tehranClock)}</span>
    </div>
    `;
    tr.appendChild(tsTd);

    // Location cell
    const actTd = document.createElement("td");
    actTd.className = "camera_location";
    actTd.innerHTML = `
    <div class="action-buttons">
      <label >${t.camera_location}</label>
    </div>
    `;
    tr.appendChild(actTd);
    tbody.appendChild(tr);
  });
}

function onPerPageChange() {
  CURRENT_PER_PAGE = parseInt(
    document.getElementById("perPageSelect").value,
    10
  );
  CURRENT_PAGE = 1;
  fetchTraffic();
}

function changePage(delta) {
  if (CURRENT_PAGE < TOTAL_PAGES && delta > 0) {
    CURRENT_PAGE++;
    fetchTraffic();
  } else if (CURRENT_PAGE > 1 && delta < 0) {
    CURRENT_PAGE--;
    fetchTraffic();
  }
}

function openPlateImageModal(src, plateData) {
  document.getElementById("modalLargeImg").src = src;

  const detailsDiv = document.getElementById("modalDetails");
  detailsDiv.innerHTML = `
    <p>شناسه: ${plateData.uuid}</p>
    <div class="plateTextModalContainer">
    <p><strong>شماره پلاک:</strong> <input class="center-text" id="editPlateText" value="${plateData.plate_text}"></p>
    <p><strong>نوع خودرو:</strong> <input class="center-text" id="editCarType" value="${plateData.car_type}"></p>
  <p><strong>رنگ خودرو:</strong> <input class="center-text" id="editCarColor" value="${plateData.car_color}"></p>
  <p><strong>صاحب خودرو:</strong> <input class="center-text" id="editCarOwner" value="${plateData.car_owner}"></p>
    </div>
    <div class="modal-actions">
      <button class="button green-btn" onclick="confirmUpdatePlate('${plateData.uuid}')">بروزرسانی</button>
      <button class="button red-btn" onclick="confirmDeletePlate('${plateData.uuid}')">حذف</button>
    </div>
  `;

  document.getElementById("imgDetailsModal").style.display = "flex";
  document.getElementById("editPlateText").focus();
}

function closePlateImageModal() {
  document.getElementById("imgDetailsModal").style.display = "none";
}

// Generic Confirmation Modal
function showConfirm(message, onConfirm) {
  document.getElementById("confirmMessage").textContent = message;
  const modal = document.getElementById("confirmModal");
  modal.style.display = "flex";

  document.getElementById("confirmYes").onclick = () => {
    modal.style.display = "none";
    onConfirm();
  };
  document.getElementById("confirmNo").onclick = () => {
    modal.style.display = "none";
  };
}

// Update Plate with Confirmation
function confirmUpdatePlate(uuid) {
  showConfirm(`آیا بروزرسانی شود؟`, async () => {
    const newPlate = document.getElementById("editPlateText").value;
    const newCarType = document.getElementById("editCarType").value;
    const newCarColor = document.getElementById("editCarColor").value;
    const newCarOwner = document.getElementById("editCarOwner").value;
    const newCameraLocation =
      document.getElementById("editCameraLocation").value;
    await fetch(`/update/${uuid}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        plate_text: newPlate,
        car_type: newCarType,
        car_color: newCarColor,
        car_owner: newCarOwner,
        camera_location: newCameraLocation,
      }),
    });
    showToast("پلاک بروزرسانی شد");
    fetchTraffic();
    closePlateImageModal();
  });
}

// Delete Plate with Confirmation
function confirmDeletePlate(uuid) {
  showConfirm(`آیا تاریخچه این تردد برای همیشه حذف گردد؟`, async () => {
    await fetch(`/traffic/${uuid}`, { method: "DELETE" });
    showToast("تردد حذف شد");
    fetchTraffic();
    closePlateImageModal();
  });
}

// -------------- Plate Modal
async function addPlate() {
  const plate = document.getElementById("plate_text").value;
  if (plate.length < 7) return showToast("پلاک ۸ رقم دارد", 2000);
  await fetch("/plates", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      plate_text: plate,
    }),
  });
  fetchPlates();
  document.getElementById("plate_text").value = "";
  showToast("پلاک جدید اضافه شد", 5000);
}

async function updatePlate(uuid, inputElem) {
  const tr = inputElem.closest("tr");
  const updated = {
    plate_text: tr.children[3].children[0].value,
  };
  showConfirm(
    `آیا از بروزرسانی پلاک ${uuid} مطمئنید؟`,
    await fetch(`/plates/${uuid}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updated),
    })
  );

  showToast("پلاک ویرایش شد", 5000);
}

// ------------------ Plate Modal End

// Add new plate modal
function openAddModal() {
  document.getElementById("addModal").style.display = "block";
  restoreInputs();
}
function closeAddModal() {
  document.getElementById("addModal").style.display = "none";
}
function cacheInputs() {
  localStorage.setItem(
    "newPlate",
    JSON.stringify({
      plate_text: document.getElementById("plate_text").value,
    })
  );
}
function restoreInputs() {
  const saved = JSON.parse(localStorage.getItem("newPlate") || "{}");
  if (saved.plate_text)
    document.getElementById("plate_text").value = saved.plate_text;
}

function showToast(message) {
  let toast = document.getElementById("toast");
  toast.textContent = message;
  toast.className = "show";
  setTimeout(() => {
    toast.className = "hide";
  }, 2500);
}

let loadingCounter = 0;
function showLoading(message = "در حال ذخیره...") {
  const overlay = document.getElementById("loadingOverlay");
  const messageEl = document.getElementById("loadingMessage");
  if (!overlay || !messageEl) return;

  loadingCounter += 1;
  messageEl.textContent = message;
  overlay.classList.add("active");
}

function hideLoading() {
  const overlay = document.getElementById("loadingOverlay");
  if (!overlay) return;

  loadingCounter = Math.max(loadingCounter - 1, 0);
  if (loadingCounter === 0) {
    overlay.classList.remove("active");
  }
}

// Add plate modal
function openAddPlateModal() {
  document.getElementById("addPlateModal").style.display = "flex";
  document.getElementById("modal_plate_text").focus();
}

function closeAddPlateModal() {
  document.getElementById("addPlateModal").style.display = "none";
  document.getElementById("modal_plate_text").value = "";
  document.getElementById("modal_car_type").value = "";
  document.getElementById("modal_car_color").value = "";
  document.getElementById("modal_car_owner").value = "";
}

async function submitAddManualTraffic() {
  const plate = document.getElementById("modal_plate_text").value;
  const carType = document.getElementById("modal_car_type").value;
  const carColor = document.getElementById("modal_car_color").value;
  const carOwner = document.getElementById("modal_car_owner").value;
  const camera_location = document.getElementById(
    "modal_camera_location"
  ).value;
  if (plate.length < 7) return showToast("پلاک ۸ رقم دارد", 2000);

  try {
    const res = await fetch("/traffic", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        plate_text: plate,
        car_type: carType,
        car_color: carColor,
        car_owner: carOwner,
        camera_location: camera_location,
      }),
    });
    const data = await res.json();
    showToast("تردد با موفقیت افزوده شد");
    closeAddPlateModal();
    fetchTraffic();
  } catch (e) {
    console.error(e);
    showToast("خطا در ثبت تردد");
  }
}

// Add plate modal

// plate component
function createPlateComponent(plateText, plateId) {
  const container = document.createElement("div");
  container.className = "plate-component";

  if (plateText == "DETECTION_FAILED") {
    const input = document.createElement("label");
    input.textContent = "شناسایی ناموفق";
    container.appendChild(input);
  } else {
    [...plateText].reverse().forEach((char, idx) => {
      const input = document.createElement("label");
      input.textContent = toFarsiNumber(char);
      input.dataset.charIndex = idx;
      input.dataset.plateId = plateId;
      input.className = "plate-glyph";
      container.appendChild(input);
    });
  }

  return container;
}
// plate component

// helper
function toFarsiNumber(str) {
  const farsiDigits = ["۰", "۱", "۲", "۳", "۴", "۵", "۶", "۷", "۸", "۹"];
  return String(str).replace(/\d/g, (d) => farsiDigits[d]);
}

window.onclick = function (event) {
  const imgModal = document.getElementById("imgDetailsModal");
  if (event.target == imgModal) closePlateImageModal();

  const addPlateModal = document.getElementById("addPlateModal");
  if (event.target == addPlateModal) closeAddPlateModal();

  const confirmModal = document.getElementById("confirmModal");
  if (event.target == confirmModal) confirmModal.style.display = "none";

  const rotationModal = document.getElementById("rotationModal");
  if (event.target == rotationModal) Rotation.close();

  const hotZoneModal = document.getElementById("hotZoneModal");
  if (event.target == hotZoneModal) HotZone.close();
};

// Filtering
let filtersVisible = false;

function toggleFilterBar() {
  filtersVisible = !filtersVisible;
  document.getElementById("filterBar").style.display = filtersVisible
    ? "block"
    : "none";
}

function applyFilters() {
  const plate = document.getElementById("filterPlate").value;
  const start = document.getElementById("filterStart").value;
  const end = document.getElementById("filterEnd").value;

  const params = new URLSearchParams();
  if (plate) {
    CURRENT_FILTERS.plate_text = toFarsiNumber(plate);
    params.append("plate_text", toFarsiNumber(plate));
  } else {
    delete CURRENT_FILTERS.plate_text;
  }
  if (start) {
    CURRENT_FILTERS.start_ts = start;
    params.append("start_ts", start);
  } else {
    delete CURRENT_FILTERS.start_ts;
  }
  if (end) {
    CURRENT_FILTERS.end_ts = end;
    params.append("end_ts", end);
  } else {
    delete CURRENT_FILTERS.end_ts;
  }

  if (RESTRICTED_FILTER_ACTIVE) {
    params.append("restricted_start", CURRENT_FILTERS.restricted_start);
    params.append("restricted_end", CURRENT_FILTERS.restricted_end);
  }

  fetchTraffic(params.toString());
}

function clearFilters() {
  document.getElementById("filterPlate").value = "";
  document.getElementById("filterStart").value = "";
  document.getElementById("filterEnd").value = "";
  CURRENT_FILTERS = {};
  setRestrictedFilterState(false);
  toggleFilterBar();
  fetchTraffic();
}

function syncRestrictedHours(start, end, options = {}) {
  const { updateInputs = true, persist = true, triggerFetch = false } = options;

  const normalizedStart = start || "";
  const normalizedEnd = end || "";
  const hasValidRange =
    normalizedStart && normalizedEnd && normalizedStart !== normalizedEnd;

  if (hasValidRange) {
    RESTRICTED_HOURS = {
      start: normalizedStart,
      end: normalizedEnd,
    };
    if (persist) {
      localStorage.setItem(
        RESTRICTED_STORAGE_KEY,
        JSON.stringify(RESTRICTED_HOURS)
      );
    }
  } else {
    RESTRICTED_HOURS = { start: "", end: "" };
    if (persist) {
      localStorage.removeItem(RESTRICTED_STORAGE_KEY);
    }
  }

  if (updateInputs) {
    const startInput = document.getElementById("restricted_hours_start");
    const endInput = document.getElementById("restricted_hours_end");
    if (startInput) startInput.value = RESTRICTED_HOURS.start || "";
    if (endInput) endInput.value = RESTRICTED_HOURS.end || "";
  }

  updateRestrictedStatusDisplay();

  if (RESTRICTED_FILTER_ACTIVE && !hasValidRange) {
    setRestrictedFilterState(false);
    if (triggerFetch) fetchTraffic();
  } else if (RESTRICTED_FILTER_ACTIVE && hasValidRange) {
    setRestrictedFilterState(true);
    if (triggerFetch) fetchTraffic();
  }
}

async function initializeRestrictedHours() {
  let storedStart = "";
  let storedEnd = "";

  try {
    const stored = JSON.parse(
      localStorage.getItem(RESTRICTED_STORAGE_KEY) || "{}"
    );
    if (stored.start && stored.end && stored.start !== stored.end) {
      storedStart = stored.start;
      storedEnd = stored.end;
    }
  } catch (error) {
    console.warn("Failed to load restricted hours from local storage:", error);
  }

  let start = storedStart;
  let end = storedEnd;

  try {
    const response = await fetch("/settings");
    if (response.ok) {
      const settingsData = await response.json();
      const serverStart = settingsData.restricted_hours_start;
      const serverEnd = settingsData.restricted_hours_end;
      if (serverStart && serverEnd && serverStart !== serverEnd) {
        start = serverStart;
        end = serverEnd;
      } else if (!serverStart || !serverEnd) {
        start = "";
        end = "";
      }
    }
  } catch (error) {
    console.warn("Failed to load restricted hours from settings:", error);
  }

  syncRestrictedHours(start, end, { triggerFetch: false });
  setRestrictedFilterState(false);
}

function updateRestrictedStatusDisplay() {
  const windowLabel = document.getElementById("restrictedWindow");
  if (!windowLabel) return;

  if (RESTRICTED_HOURS.start && RESTRICTED_HOURS.end) {
    windowLabel.textContent = `${toFarsiNumber(
      RESTRICTED_HOURS.start
    )} تا ${toFarsiNumber(RESTRICTED_HOURS.end)}`;
  } else {
    windowLabel.textContent = "—";
  }
}

function setRestrictedFilterState(isActive) {
  const canActivate = Boolean(
    RESTRICTED_HOURS.start && RESTRICTED_HOURS.end
  );
  const nextState = Boolean(isActive) && canActivate;
  RESTRICTED_FILTER_ACTIVE = nextState;

  const button = document.getElementById("restrictedFilterBtn");
  if (button) {
    button.classList.toggle("active", RESTRICTED_FILTER_ACTIVE);
    button.setAttribute(
      "aria-pressed",
      RESTRICTED_FILTER_ACTIVE ? "true" : "false"
    );
  }

  if (RESTRICTED_FILTER_ACTIVE) {
    CURRENT_FILTERS.restricted_start = RESTRICTED_HOURS.start;
    CURRENT_FILTERS.restricted_end = RESTRICTED_HOURS.end;
  } else {
    delete CURRENT_FILTERS.restricted_start;
    delete CURRENT_FILTERS.restricted_end;
  }
}

function toggleRestrictedFilter() {
  if (!RESTRICTED_HOURS.start || !RESTRICTED_HOURS.end) {
    showToast("ابتدا ساعات ممنوعه را در تنظیمات ذخیره کنید");
    return;
  }

  const newState = !RESTRICTED_FILTER_ACTIVE;
  setRestrictedFilterState(newState);
  fetchTraffic();
  showToast(
    newState
      ? "نمایش ترددهای ساعات ممنوعه فعال شد"
      : "نمایش ترددهای ساعات ممنوعه غیرفعال شد"
  );
}

// export CSV using current filters
function exportCSV() {
  const params = new URLSearchParams({
    plate_text: CURRENT_FILTERS.plate_text || "",
    start_ts: CURRENT_FILTERS.start_ts || "",
    end_ts: CURRENT_FILTERS.end_ts || "",
    restricted_start: CURRENT_FILTERS.restricted_start || "",
    restricted_end: CURRENT_FILTERS.restricted_end || "",
  }).toString();

  window.open(`/traffic/export?${params}`, "_blank");
}

// initial load
window.onload = async () => {
  document.getElementById("perPageSelect").value = String(CURRENT_PER_PAGE);
  await initializeRestrictedHours();
  fetchTraffic();
};

document
  .getElementById("filterPlate")
  .addEventListener("keydown", function (e) {
    if (e.key === "Enter") {
      applyFilters(this.value.trim());
    }
  });

// #region Settings Modal
function openSettingsModal() {
  document.getElementById("settingsModal").style.display = "flex";
  loadSettings();

  const hotZoneBtn = document.getElementById("hotZoneBtn");
  if (hotZoneBtn && !hotZoneBtn.dataset.listenerAttached) {
    hotZoneBtn.dataset.listenerAttached = "true";
    hotZoneBtn.addEventListener("click", () => HotZone.open(config.hot_zone));
  }
}

function closeSettingsModal() {
  document.getElementById("settingsModal").style.display = "none";
}

let config = {};

async function loadSettings() {
  try {
    const response = await fetch("/settings");
    config = await response.json();
    for (const key in config) {
      const el = document.getElementById(key);
      if (!el) continue;

      const value = config[key];

      if (el.tagName === "INPUT") {
        el.value = value;
        // update slider display if range
        if (
          el.type === "range" &&
          el.nextElementSibling?.tagName === "OUTPUT"
        ) {
          el.nextElementSibling.value = value;
        }
      } else if (el.tagName === "SELECT") {
        el.value = value;
      } else if (el.tagName === "OUTPUT") {
        el.value = value;
      } else {
        el.textContent = value;
      }
    }
    updateVideoStream();
    applyRotation(config.rotation_angle || 0);
    syncRestrictedHours(
      config.restricted_hours_start,
      config.restricted_hours_end,
      { triggerFetch: false }
    );
    checkBackendStatus();
  } catch (error) {
    console.error("Error loading settings:", error);
  }
}

async function saveSettings() {
  const restrictedStartInput = document.getElementById(
    "restricted_hours_start"
  );
  const restrictedEndInput = document.getElementById("restricted_hours_end");

  const restrictedStart = restrictedStartInput?.value || "";
  const restrictedEnd = restrictedEndInput?.value || "";

  if ((restrictedStart && !restrictedEnd) || (!restrictedStart && restrictedEnd)) {
    showToast("برای فعالسازی، هر دو ساعت را وارد کنید");
    return;
  }

  if (restrictedStart && restrictedEnd && restrictedStart === restrictedEnd) {
    showToast("ساعت شروع و پایان نمی‌تواند یکسان باشد");
    return;
  }

  const newConfig = {
    video_path: document.getElementById("video_path").value,
    camera_location: document.getElementById("camera_location").value,
    frame_skip: parseInt(document.getElementById("frame_skip").value, 10),
    car_detection_threshold: parseFloat(
      document.getElementById("car_detection_threshold").value
    ),
    plate_detection_threshold: parseFloat(
      document.getElementById("plate_detection_threshold").value
    ),
    crop_dimension_threshold: parseInt(
      document.getElementById("crop_dimension_threshold").value,
      10
    ),
    restricted_hours_start: restrictedStart,
    restricted_hours_end: restrictedEnd,
  };

  showLoading("در حال ذخیره تنظیمات...");
  try {
    await fetch("/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...config, ...newConfig }),
    });

    config = { ...config, ...newConfig };
    syncRestrictedHours(
      newConfig.restricted_hours_start,
      newConfig.restricted_hours_end,
      { triggerFetch: true }
    );
    updateVideoStream();
    showToast("تنظیمات ذخیره شد");
    closeSettingsModal();
  } catch (error) {
    console.error("Error saving settings:", error);
    showToast("خطا در ذخیره تنظیمات");
  } finally {
    hideLoading();
  }
}

function applyRotation(angle) {
  const numeric = Number(angle) || 0;
  const transformValue = numeric ? `rotate(${numeric}deg)` : "none";
  const elements = [
    document.getElementById("videoFeed"),
    document.getElementById("rotationImage"),
  ];
  elements.forEach((el) => {
    if (el) el.style.transform = transformValue;
  });
  const overlay = document.getElementById("rotationOverlay");
  if (overlay) {
    overlay.style.transform = numeric
      ? `translate(-50%, -50%) rotate(${numeric}deg)`
      : "translate(-50%, -50%)";
  }
}

function updateVideoStream() {
  const videoPath = document.getElementById("video_path").value;
  const videoFeed = document.getElementById("videoFeed");
  if (videoPath) {
    videoFeed.src = `/video_feed?url=${encodeURIComponent(
      videoPath
    )}&t=${new Date().getTime()}`;
  } else {
    videoFeed.src = "";
  }
}

async function checkBackendStatus() {
  return;
  // TODO POST MVP
  try {
    const response = await fetch("/status");
    const data = await response.json();
    document.getElementById("backendStatus").textContent = data.status;
  } catch (error) {
    document.getElementById("backendStatus").textContent = "Error";
  }
}

window.addEventListener("load", () => {
  // Check backend status periodically
  setInterval(checkBackendStatus, 5000);

  const videoWrapper = document.querySelector(".video-preview-wrapper");
  const videoFeed = document.getElementById("videoFeed");

  if (videoWrapper && videoFeed) {
    videoWrapper.addEventListener("dblclick", () => {
      if (!videoWrapper.classList.contains("fullscreen")) {
        videoWrapper.classList.add("fullscreen");
      } else {
        videoWrapper.classList.remove("fullscreen");
        updateVideoStream(); // Resume stream with new timestamp
      }
    });
  }
});

// #region Rotation Module
const Rotation = (() => {
  const modal = document.getElementById("rotationModal");
  const previewImage = document.getElementById("rotationImage");
  const slider = document.getElementById("rotationSlider");
  const input = document.getElementById("rotationInput");
  const overlay = document.getElementById("rotationOverlay");
  let currentAngle = 0;

  const clamp = (value) => {
    const numeric = Number(value);
    if (Number.isNaN(numeric)) return 0;
    return Math.max(-180, Math.min(180, Math.round(numeric)));
  };

  const updatePreview = (angle) => {
    if (previewImage) {
      previewImage.style.transform = angle ? `rotate(${angle}deg)` : "none";
    }
    if (overlay) {
      overlay.style.transform = angle
        ? `translate(-50%, -50%) rotate(${angle}deg)`
        : "translate(-50%, -50%)";
    }
  };

  const syncControls = (value) => {
    currentAngle = clamp(value);
    if (slider) slider.value = currentAngle;
    if (input) input.value = currentAngle;
    updatePreview(currentAngle);
    return currentAngle;
  };

  const getPersistedAngle = () =>
    clamp(document.getElementById("rotation_angle")?.value || config.rotation_angle || 0);

  const setPreviewSource = () => {
    if (!previewImage) return;
    const feedSrc = document.getElementById("videoFeed")?.src;
    if (feedSrc) {
      previewImage.src = feedSrc;
    } else {
      previewImage.src = "/static/plate_raw.jpg";
    }
  };

  function open() {
    if (!modal) return;
    setPreviewSource();
    syncControls(getPersistedAngle());
    modal.style.display = "flex";
  }

  function close() {
    if (modal) modal.style.display = "none";
  }

  function updateFromSlider(value) {
    syncControls(value);
  }

  function updateFromInput(value) {
    syncControls(value);
  }

  async function save() {
    const angle = currentAngle;
    const cfg = { ...config, rotation_angle: angle };

    showLoading("در حال ذخیره زاویه چرخش...");
    try {
      await fetch("/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cfg),
      });
      config = cfg;
      const angleInput = document.getElementById("rotation_angle");
      if (angleInput) angleInput.value = angle;
      applyRotation(angle);
      showToast("زاویه چرخش به‌روزرسانی شد");
      close();
    } catch (error) {
      console.error("Error saving rotation:", error);
      showToast("خطا در ذخیره زاویه چرخش");
    } finally {
      hideLoading();
    }
  }

  function handleManualInput(value) {
    const angle = syncControls(value);
    const angleInput = document.getElementById("rotation_angle");
    if (angleInput) angleInput.value = angle;
    applyRotation(angle);
  }

  return {
    open,
    close,
    save,
    updateFromSlider,
    updateFromInput,
    handleManualInput,
  };
})();
// #endregion

// #region Hot Zone Module
const HotZone = (() => {
  const canvas = document.getElementById("hotZoneCanvas");
  const ctx = canvas.getContext("2d");
  const img = document.getElementById("hotZoneImage");
  const handleSize = 8;
  let polygon = [];
  let selectedPoint = null;
  let action = null,
    offset = { x: 0, y: 0 };

  function open(saved) {
    document.getElementById("hotZoneModal").style.display = "block";
    img.src = document.getElementById("videoFeed").src;
    img.onload = () => {
      syncCanvas();
      if (saved) polygon = scalePolygon(saved, canvas.width, canvas.height);
      else polygon = defaultPolygon();
      draw();
    };
  }

  function close() {
    document.getElementById("hotZoneModal").style.display = "none";
  }

  function syncCanvas() {
    canvas.width = img.clientWidth;
    canvas.height = img.clientHeight;
  }

  function getMousePos(evt) {
    const r = canvas.getBoundingClientRect();
    return {
      x: (evt.clientX - r.left) * (canvas.width / r.width),
      y: (evt.clientY - r.top) * (canvas.height / r.height),
    };
  }

  function getPointAt(x, y) {
    return polygon.find(
      (p) => Math.abs(p.x - x) <= handleSize && Math.abs(p.y - y) <= handleSize
    );
  }

  function isOverHandle(x, y) {
    const handles = {
      tl: [rect.x1, rect.y1],
      tr: [rect.x2, rect.y1],
      bl: [rect.x1, rect.y2],
      br: [rect.x2, rect.y2],
    };
    return (
      Object.entries(handles).find(
        ([name, [hx, hy]]) =>
          Math.abs(x - hx) <= handleSize && Math.abs(y - hy) <= handleSize
      )?.[0] || null
    );
  }

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (polygon.length === 0) return;

    ctx.strokeStyle = "red";
    ctx.lineWidth = 2;
    ctx.beginPath();
    polygon.forEach((p, i) =>
      i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)
    );
    ctx.closePath();
    ctx.stroke();

    ctx.fillStyle = "white";
    ctx.strokeStyle = "black";
    polygon.forEach((p) => {
      ctx.fillRect(
        p.x - handleSize / 2,
        p.y - handleSize / 2,
        handleSize,
        handleSize
      );
      ctx.strokeRect(
        p.x - handleSize / 2,
        p.y - handleSize / 2,
        handleSize,
        handleSize
      );
    });
  }

  function start(evt) {
    const { x, y } = getMousePos(evt);
    selectedPoint = getPointAt(x, y);
    if (!selectedPoint) {
      action = "moveAll";
      offset = { x, y };
    }
  }

  function move(evt) {
    const { x, y } = getMousePos(evt);
    if (selectedPoint) {
      selectedPoint.x = x;
      selectedPoint.y = y;
    } else if (action === "moveAll") {
      const dx = x - offset.x,
        dy = y - offset.y;
      polygon.forEach((p) => {
        p.x += dx;
        p.y += dy;
      });
      offset = { x, y };
    }
    draw();
  }

  function resize(handle, x, y) {
    switch (handle) {
      case "tl":
        rect.x1 = x;
        rect.y1 = y;
        break;
      case "tr":
        rect.x2 = x;
        rect.y1 = y;
        break;
      case "bl":
        rect.x1 = x;
        rect.y2 = y;
        break;
      case "br":
        rect.x2 = x;
        rect.y2 = y;
        break;
    }
  }

  function end() {
    selectedPoint = null;
    action = null;
    draw();
  }

  async function save() {
    const normalized = polygon.map((p) => ({
      x: p.x / canvas.width,
      y: p.y / canvas.height,
    }));
    const cfg = { ...config, hot_zone: normalized };

    showLoading("در حال ذخیره منطقه تشخیص...");
    try {
      await fetch("/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cfg),
      });
      config = cfg;
      showToast("منطقه تشخیص ذخیره شد");
      close();
    } catch (error) {
      console.error("Error saving hot zone:", error);
      showToast("خطا در ذخیره منطقه تشخیص");
    } finally {
      hideLoading();
    }
  }

  function defaultPolygon() {
    const w = canvas.width,
      h = canvas.height;
    return [
      { x: w * 0.2, y: h * 0.2 },
      { x: w * 0.8, y: h * 0.2 },
      { x: w * 0.8, y: h * 0.8 },
      { x: w * 0.2, y: h * 0.8 },
    ];
  }
  function scalePolygon(saved, w, h) {
    return saved.map((p) => ({ x: p.x * w, y: p.y * h }));
  }

  function defaultRect() {
    return {
      x1: canvas.width * 0.25,
      y1: canvas.height * 0.25,
      x2: canvas.width * 0.75,
      y2: canvas.height * 0.75,
    };
  }
  function scaleRect(saved, w, h) {
    return {
      x1: saved.x1 * w,
      y1: saved.y1 * h,
      x2: saved.x2 * w,
      y2: saved.y2 * h,
    };
  }

  canvas.onmousedown = start;
  canvas.onmousemove = move;
  canvas.onmouseup = canvas.onmouseleave = end;

  return { open, close, save, draw };
})();
// #endregion

// #endregion

// Close modal on Escape key press
document.addEventListener("keydown", function (e) {
  if (e.key === "Escape") {
    const modals = document.querySelectorAll(".modal");
    modals.forEach((m) => {
      if (m.style.display === "flex" || m.style.display === "block") {
        m.style.display = "none";
      }
    });
  }
});

// Zoom Image
const modalImg = document.getElementById("modalLargeImg");
const fsModal = document.getElementById("fullscreenImgModal");
const fsImg = document.getElementById("fullscreenImg");

let fsScale = 1;
let offset = { x: 0, y: 0 };
let dragStart = null;
let isDragging = false;

// Open fullscreen modal
modalImg.addEventListener("click", () => {
  fsImg.src = modalImg.src;
  fsModal.style.display = "flex";
  fsScale = 1;
  offset = { x: 0, y: 0 };
  updateTransform();
});

// Close on click (only if not dragging)
fsImg.addEventListener("click", (e) => {
  if (!isDragging) fsModal.style.display = "none";
});

// Zoom on wheel where mouse is pointing
fsModal.addEventListener("wheel", (e) => {
  e.preventDefault();

  const rect = fsImg.getBoundingClientRect();
  const zoomFactor = e.deltaY < 0 ? 1.3 : 0.9;
  const prevScale = fsScale;
  fsScale = Math.min(Math.max(fsScale * zoomFactor, 1), 5);

  // Mouse position relative to image center
  const imgCenterX = rect.left + rect.width / 2;
  const imgCenterY = rect.top + rect.height / 2;
  const mouseX = e.clientX - imgCenterX;
  const mouseY = e.clientY - imgCenterY;

  if (fsScale === 1) {
    offset = { x: 0, y: 0 };
  } else {
    // Adjust offset so zoom pivots on cursor
    offset.x -= mouseX * (fsScale / prevScale - 1);
    offset.y -= mouseY * (fsScale / prevScale - 1);
  }

  updateTransform();
});

// Drag to move zoomed image
fsImg.addEventListener("mousedown", (e) => {
  e.preventDefault();
  dragStart = { x: e.clientX - offset.x, y: e.clientY - offset.y };
  isDragging = false;
  fsImg.style.cursor = "grabbing";
});

document.addEventListener("mousemove", (e) => {
  if (!dragStart) return;
  const dx = e.clientX - (dragStart.x + offset.x);
  const dy = e.clientY - (dragStart.y + offset.y);
  if (Math.abs(dx) > 3 || Math.abs(dy) > 3) isDragging = true;

  offset.x = e.clientX - dragStart.x;
  offset.y = e.clientY - dragStart.y;
  updateTransform();
});

document.addEventListener("mouseup", () => {
  dragStart = null;
  fsImg.style.cursor = "grab";
});

// Close on ESC
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") fsModal.style.display = "none";
});

function updateTransform() {
  fsImg.style.transform = `translate(${offset.x}px, ${offset.y}px) scale(${fsScale})`;
}

// Video Preview Fullscreen
const videoFeed = document.getElementById("videoFeed");
const videoPreviewModal = document.getElementById("videoPreviewModal");
const fullscreenVideoFeed = document.getElementById("fullscreenVideoFeed");

videoFeed.addEventListener("click", () => {
  fullscreenVideoFeed.src = videoFeed.src;
  videoPreviewModal.style.display = "flex";
});

videoPreviewModal.addEventListener("click", () => {
  videoPreviewModal.style.display = "none";
});
