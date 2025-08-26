window.onload = fetchPlates;

// CRUD
async function fetchPlates() {
  const res = await fetch("/plates");
  const data = await res.json();
  const tbody = document.getElementById("plates_body");
  tbody.innerHTML = "";

  data.forEach((p) => {
    const tr = document.createElement("tr");

    // ID cell
    const idTd = document.createElement("td");
    idTd.textContent = toFarsiNumber(p.id);
    tr.appendChild(idTd);

    // VID cell
    const vidTd = document.createElement("td");
    vidTd.textContent = p.vehicle_id;
    tr.appendChild(vidTd);

    // Image cell
    const imgTd = document.createElement("td");
    imgTd.innerHTML = `<img src="../../${p.image_path}" style="width:128px;height:32px;cursor:pointer;" onclick="openPlateImageModal('${p.image_path}')">`;
    tr.appendChild(imgTd);

    // Plate glyphs cell
    const plateTd = document.createElement("td");
    plateTd.appendChild(createPlateComponent(p.plate_text, p.id));
    tr.appendChild(plateTd);

    // Timestamp cell
    const tsTd = document.createElement("td");
    tsTd.textContent = toFarsiNumber(p.timestamp);
    tr.appendChild(tsTd);

    // Actions cell
    const actTd = document.createElement("td");
    actTd.className = "actions";
    actTd.innerHTML = `<button onclick="deletePlate(${p.id})">حذف</button>`;
    tr.appendChild(actTd);

    tbody.appendChild(tr);
  });
}

function openPlateImageModal(src) {
  document.getElementById("modalImg").src = src;
  document.getElementById("imgModal").style.display = "block";
}
function closePlateImageModal() {
  document.getElementById("imgModal").style.display = "none";
}

// -------------- Plate Modal
async function addPlate() {
  const plate = document.getElementById("plate_text").value;
  if (plate.length < 7) return showToast("پلاک ۸ رقم دارد", 2000);
  await fetch("/plates", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      vehicle_id: 0,
      image_path: "",
      plate_text: plate,
    }),
  });
  fetchPlates();
  document.getElementById("plate_text").value = "";
  showToast("پلاک جدید اضافه شد", 5000);
}

async function updatePlate(id, inputElem) {
  const tr = inputElem.closest("tr");
  const updated = {
    plate_text: tr.children[3].children[0].value,
  };
  if (!confirm(`Update record ${id}?`)) return;
  await fetch(`/plates/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updated),
  });
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

async function deletePlate(id) {
  if (!confirm(`پلاک ${id} برای همیشه حذف شود؟ مطمئنید؟`)) return;
  await fetch(`/plates/${id}`, { method: "DELETE" });
  fetchPlates();
  showToast("پلاک حذف شد", 5000);
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
  document.getElementById("addPlateModal").style.display = "block";
}

function closeAddPlateModal() {
  document.getElementById("addPlateModal").style.display = "none";
  document.getElementById("modal_plate_text").value = "";
}

async function submitAddPlate() {
  const plate = document.getElementById("modal_plate_text").value;
  if (plate.length < 7) return showToast("پلاک ۸ رقم دارد", 2000);

  try {
    const res = await fetch("/plates", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        vehicle_id: 0,
        image_path: "",
        plate_text: plate,
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

// Close modal if clicking outside modal-content
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
