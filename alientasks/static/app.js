/* Theme toggle. The initial theme is applied by the inline head script. */
(function () {
  var toggle = document.querySelector(".theme-toggle");
  if (!toggle) return;
  function apply(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    toggle.setAttribute("aria-pressed", String(theme === "light"));
    toggle.textContent = theme === "light" ? "Dark mode" : "Light mode";
  }
  apply(document.documentElement.getAttribute("data-theme") || "dark");
  toggle.addEventListener("click", function () {
    var current = document.documentElement.getAttribute("data-theme");
    var next = current === "light" ? "dark" : "light";
    try { localStorage.setItem("alientasks-theme", next); } catch (e) {}
    apply(next);
  });
})();
document.querySelectorAll(".task").forEach(function (form) {
  var box = form.querySelector(".task__check");
  if (!box) return;
  box.addEventListener("change", function () { form.submit(); });
});
