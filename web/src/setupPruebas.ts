import "@testing-library/jest-dom/vitest"

// jsdom no implementa estas APIs del navegador. matchMedia: tema "sistema" y menú lateral
// (useIsMobile); ResizeObserver: gráficas y Radix; punteros y scroll: Select de Radix.
Object.defineProperty(window, "matchMedia", {
  writable: true,
  configurable: true,
  value: (consulta: string) => ({
    matches: false,
    media: consulta,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  }),
})

class ResizeObserverDePrueba {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = ResizeObserverDePrueba as unknown as typeof ResizeObserver

Element.prototype.scrollIntoView = () => {}
Element.prototype.hasPointerCapture = () => false
Element.prototype.releasePointerCapture = () => {}
