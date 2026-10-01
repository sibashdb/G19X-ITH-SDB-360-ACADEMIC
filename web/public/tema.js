// Aplica el tema guardado antes del primer render para evitar el destello de tema equivocado.
// Es un archivo externo porque la CSP del gateway no permite scripts en línea.
// Debe decidir lo mismo que aplicarTema() en src/tema.tsx (lo verifica src/tema.test.tsx).
;(function () {
  var tema = "sistema"
  try {
    tema = localStorage.getItem("plataforma-tema") || "sistema"
  } catch (e) {
    // Almacenamiento bloqueado: se usa la preferencia del sistema.
  }
  var oscuro =
    tema === "oscuro" ||
    (tema !== "claro" && window.matchMedia("(prefers-color-scheme: dark)").matches)
  document.documentElement.classList.toggle("dark", oscuro)
  document.documentElement.style.colorScheme = oscuro ? "dark" : "light"
})()
