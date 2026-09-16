import '@testing-library/jest-dom';

// jsdom não implementa ResizeObserver (usado por libs de gráfico/UI).
if (typeof globalThis.ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}
