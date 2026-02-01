const searchInput = document.getElementById("product-search");
const statusSelect = document.getElementById("product-status");
const cards = Array.from(document.querySelectorAll(".product-card"));
const categories = Array.from(document.querySelectorAll(".category"));

const stats = {
  categories: document.getElementById("stat-categories"),
  products: document.getElementById("stat-products"),
  active: document.getElementById("stat-active"),
};

const scrollButton = document.getElementById("scroll-to-forms");
const formsSection = document.getElementById("forms");

const updateStats = () => {
  if (stats.categories) {
    stats.categories.textContent = String(categories.length);
  }
  if (stats.products) {
    stats.products.textContent = String(cards.length);
  }
  if (stats.active) {
    const activeCount = cards.filter((card) => card.dataset.active === "active").length;
    stats.active.textContent = String(activeCount);
  }
};

const normalizeText = (text) => (text || "").toLowerCase();

const filterCards = () => {
  const query = normalizeText(searchInput?.value || "");
  const statusFilter = statusSelect?.value || "all";

  cards.forEach((card) => {
    const name = normalizeText(card.dataset.name);
    const description = normalizeText(card.dataset.description);
    const matchesQuery = !query || name.includes(query) || description.includes(query);
    const matchesStatus = statusFilter === "all" || card.dataset.active === statusFilter;

    if (matchesQuery && matchesStatus) {
      card.classList.remove("hidden");
    } else {
      card.classList.add("hidden");
    }
  });
};

if (searchInput) {
  searchInput.addEventListener("input", filterCards);
}

if (statusSelect) {
  statusSelect.addEventListener("change", filterCards);
}

if (scrollButton && formsSection) {
  scrollButton.addEventListener("click", () => {
    formsSection.scrollIntoView({ behavior: "smooth" });
  });
}

updateStats();
