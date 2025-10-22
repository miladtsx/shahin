window.onload = fetchPlates;

let CURRENT_PAGE = 1;
let CURRENT_PER_PAGE = 5;
let TOTAL_PAGES = 0;
let CURRENT_FILTERS = {}; // keep filters for export and paging

// CRUD
async function fetchPlates(query = "") {
  const qs = query
    ? query
    : new URLSearchParams({
        page: CURRENT_PAGE,
        per_page: CURRENT_PER_PAGE,
        plate_text: CURRENT_FILTERS.plate_text || "",
        start_ts: CURRENT_FILTERS.start_ts || "",
        end_ts: CURRENT_FILTERS.end_ts || "",
      }).toString();

  const res = await fetch(`/plates?${qs}`);
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

  const tbody = document.getElementById("plates_body");
  tbody.innerHTML = "";

  data.forEach((p) => {
    const tr = document.createElement("tr");

    // ID cell
    const idTd = document.createElement("td");
    idTd.textContent = toFarsiNumber(p.id);
    tr.appendChild(idTd);

    // VID cell
    // const vidTd = document.createElement("td");
    // vidTd.textContent = p.vehicle_id;
    // tr.appendChild(vidTd);

    const imgTd = document.createElement("td");
    imgTd.innerHTML = `<img src="/plate_image/${p.vehicle_id}/best" 
    onclick='openPlateImageModal("/plate_image/${
      p.uuid
    }/original", ${JSON.stringify(p).replace(/"/g, "&quot;")})'>`;
    tr.appendChild(imgTd);

    // Plate glyphs cell
    const plateTd = document.createElement("td");
    plateTd.appendChild(createPlateComponent(p.plate_text, p.uuid));
    tr.appendChild(plateTd);

    // Timestamp cell
    const tsTd = document.createElement("td");
    const date = new Date(p.timestamp);
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

    // Actions cell
    const actTd = document.createElement("td");
    actTd.className = "actions";
    actTd.innerHTML = `
    <div class="action-buttons">
      <button class="button btn-delete" onclick="deletePlate('${p.uuid}')">حذف</button>
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
  fetchPlates();
}

function changePage(delta) {
  if (CURRENT_PAGE < TOTAL_PAGES && delta > 0) {
    CURRENT_PAGE++;
    fetchPlates();
  } else if (CURRENT_PAGE > 1 && delta < 0) {
    CURRENT_PAGE--;
    fetchPlates();
  }
}

function openPlateImageModal(src, plateData) {
  document.getElementById("modalLargeImg").src = src;

  // const tr = document.createElement("tr");
  // const plateTd = document.createElement("td");
  // plateTd.appendChild(createPlateComponent(p.plate_text, p.id));
  // tr.appendChild(plateTd);

  const detailsDiv = document.getElementById("modalDetails");
  detailsDiv.innerHTML = `
    <p>شناسه: ${plateData.uuid}</p>
    <div class="plateTextModalContainer">
    <p><strong>شماره پلاک:</strong> <input class="center-text" id="editPlateText" value="${plateData.plate_text}"></p>
    <p><strong>بدنه خودرو:</strong> <input class="center-text" id="editCarType" value="${plateData.car_type}"></p>
  <p><strong>رنگ خودرو:</strong> <input class="center-text" id="editCarColor" value="${plateData.car_color}"></p>
  <p><strong>صاحب خودرو:</strong> <input class="center-text" id="editCarOwner" value="${plateData.car_owner}"></p>
    </div>
    <div class="modal-actions">
      <button class="button new-plate" onclick="confirmUpdatePlate('${plateData.uuid}')">بروزرسانی</button>
      <button class="button btn-delete" onclick="confirmDeletePlate('${plateData.uuid}')">حذف</button>
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
    await fetch(`/plates/${uuid}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        plate_text: newPlate,
        car_type: newCarType,
        car_color: newCarColor,
        car_owner: newCarOwner,
      }),
    });
    showToast("پلاک بروزرسانی شد");
    fetchPlates();
    closePlateImageModal();
  });
}

// Delete Plate with Confirmation
function confirmDeletePlate(uuid) {
  showConfirm(`آیا از حذف پلاک ${uuid} مطمئنید؟`, async () => {
    await fetch(`/plates/${uuid}`, { method: "DELETE" });
    showToast("پلاک حذف شد");
    fetchPlates();
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
  // if (!confirm(`Update record ${id}?`)) return;
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
// add new plate modal

async function deletePlate(uuid) {
  showConfirm(`پلاک ${uuid} برای همیشه حذف شود؟ مطمئنید؟`, async () => {
    await fetch(`/plates/${uuid}`, { method: "DELETE" });
    fetchPlates();
    showToast("پلاک حذف شد", 5000);
  });
}

function showToast(message) {
  let toast = document.getElementById("toast");
  toast.textContent = message;
  toast.className = "show";
  setTimeout(() => {
    toast.className = "hide";
  }, 2500);
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

async function submitAddPlate() {
  const plate = document.getElementById("modal_plate_text").value;
  const carType = document.getElementById("modal_car_type").value;
  const carColor = document.getElementById("modal_car_color").value;
  const carOwner = document.getElementById("modal_car_owner").value;
  if (plate.length < 7) return showToast("پلاک ۸ رقم دارد", 2000);

  try {
    const res = await fetch("/plates", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        plate_text: plate,
        car_type: carType,
        car_color: carColor,
        car_owner: carOwner,
      }),
    });
    const data = await res.json();
    showToast("پلاک با موفقیت افزوده شد");
    closeAddPlateModal();
    fetchPlates();
  } catch (e) {
    console.error(e);
    showToast("خطا در افزودن پلاک");
  }
}

// Close modal if clicking outside modal_content
window.onclick = function (event) {
  const modal = document.getElementById("addPlateModal");
  if (event.target == modal) modal.style.display = "none";
};

// Add plate modal

// plate component
function createPlateComponent(plateText, plateId) {
  const container = document.createElement("div");
  container.className = "plate-component";

  [...plateText].reverse().forEach((char, idx) => {
    const input = document.createElement("label");
    input.textContent = toFarsiNumber(char);
    input.dataset.charIndex = idx;
    input.dataset.plateId = plateId;
    input.className = "plate-glyph";
    container.appendChild(input);
  });

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
  }
  if (start) {
    CURRENT_FILTERS.start_ts = start;
    params.append("start_ts", start);
  }
  if (end) {
    CURRENT_FILTERS.end_ts = end;
    params.append("end_ts", end);
  }

  fetchPlates(params.toString());
}

function clearFilters() {
  document.getElementById("filterPlate").value = "";
  document.getElementById("filterStart").value = "";
  document.getElementById("filterEnd").value = "";
  CURRENT_FILTERS = {};
  toggleFilterBar();
  fetchPlates();
}

// export CSV using current filters
function exportCSV() {
  const params = new URLSearchParams({
    plate_text: CURRENT_FILTERS.plate_text || "",
    start_ts: CURRENT_FILTERS.start_ts || "",
    end_ts: CURRENT_FILTERS.end_ts || "",
  }).toString();

  window.open(`/plates/export?${params}`, "_blank");
}

// initial load
window.onload = () => {
  document.getElementById("perPageSelect").value = String(CURRENT_PER_PAGE);
  fetchPlates();
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
}

function closeSettingsModal() {
  document.getElementById("settingsModal").style.display = "none";
}

async function loadSettings() {
  const response = await fetch("/settings");
  const config = await response.json();
  for (const key in config) {
    const input = document.getElementById(key);
    if (input) {
      input.value = config[key];
    }
  }
  updateVideoStream();
  checkBackendStatus();
}

async function saveSettings() {
  const config = {
    video_path: document.getElementById("video_path").value,
    frame_skip: parseInt(document.getElementById("frame_skip").value),
    car_detection_threshold: parseFloat(
      document.getElementById("car_detection_threshold").value
    ),
    plate_detection_threshold: parseFloat(
      document.getElementById("plate_detection_threshold").value
    ),
    crop_dimension_threshold: parseInt(
      document.getElementById("crop_dimension_threshold").value
    ),
  };

  await fetch("/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });

  showToast("در حال راه‌اندازی مجدد با تنظیمات جدید");
  setTimeout(checkBackendStatus, 2000); // Check status after a delay
  closeSettingsModal();
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
  try {
    const response = await fetch("/status");
    const data = await response.json();
    document.getElementById("backendStatus").textContent = data.status;
  } catch (error) {
    document.getElementById("backendStatus").textContent = "Error";
  }
}

window.addEventListener("load", () => {
  // Load settings on page load if you want to pre-populate or check status
  // loadSettings();

  // Check backend status periodically
  setInterval(checkBackendStatus, 5000);

  const videoWrapper = document.querySelector(".video-preview-wrapper");
  const videoFeed = document.getElementById("videoFeed");

  if (videoWrapper && videoFeed) {
    videoWrapper.addEventListener("dblclick", () => {
      if (!videoWrapper.classList.contains("fullscreen")) {
        // Enter fullscreen on double-click
        videoWrapper.classList.add("fullscreen");
      } else {
        // Exit fullscreen on double-click
        videoWrapper.classList.remove("fullscreen");
        updateVideoStream(); // Resume stream with new timestamp
      }
    });
  }
});

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
// #endregion
