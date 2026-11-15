import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// A deliberately separate build: no inherited middleware, public installers, or cloud assets.
export default defineConfig({
  plugins: [react()],
  publicDir: false,
  build: { outDir: 'dist-bej', rollupOptions: { input: 'bej.html' } },
});
