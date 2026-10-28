// Row expand/collapse for the review table; everything else is HTMX.
document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-toggle]");
  if (!button) return;
  const group = button.closest("tbody");
  const open = group.classList.toggle("is-open");
  button.setAttribute("aria-expanded", String(open));
});

// Confirmation for destructive plain forms (e.g. deleting a document).
document.addEventListener("submit", (event) => {
  const message = event.target.dataset.confirm;
  if (message && !window.confirm(message)) event.preventDefault();
});
