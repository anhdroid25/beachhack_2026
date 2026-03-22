import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

/**
 * Find the directory that contains `.env` (repo root: beachhack_2026/).
 * Tries parent folders so `envDir` works even if the project layout shifts slightly.
 */
function resolveEnvDir() {
  let dir = __dirname
  for (let i = 0; i < 6; i++) {
    if (fs.existsSync(path.join(dir, '.env'))) {
      return dir
    }
    const parent = path.dirname(dir)
    if (parent === dir) break
    dir = parent
  }
  // Default: two levels up from frontend/ → beachhack_2026/
  return path.resolve(__dirname, '../..')
}

export default defineConfig(({ mode }) => {
  const envDir = resolveEnvDir()
  const loaded = loadEnv(mode, envDir, '')

  // Same names as `beachhack_2026/.env.example`: VITE_* overrides SUPABASE_* for the client bundle
  const supabaseUrl = (
    loaded.VITE_SUPABASE_URL ||
    loaded.SUPABASE_URL ||
    ''
  ).trim()
  const supabaseAnon = (
    loaded.VITE_SUPABASE_ANON_KEY ||
    loaded.SUPABASE_ANON_KEY ||
    ''
  ).trim()

  if (mode === 'development') {
    if (!fs.existsSync(path.join(envDir, '.env'))) {
      console.warn(
        `[vite] No .env found at ${path.join(envDir, '.env')}. Create it or symlink from repo root.`
      )
    } else {
      console.info(`[vite] Loading env from ${envDir}`)
      if (!supabaseUrl) {
        console.warn(
          '[vite] Set SUPABASE_URL or VITE_SUPABASE_URL in root .env for the frontend.'
        )
      }
      if (!supabaseAnon) {
        console.warn(
          '[vite] Set SUPABASE_ANON_KEY or VITE_SUPABASE_ANON_KEY (anon JWT from Supabase Dashboard → API). Do not use SUPABASE_KEY in the browser.'
        )
      }
    }
  }

  return {
    plugins: [react()],
    envDir,
    // Map server-style names to what `import.meta.env` exposes to the client
    define: {
      'import.meta.env.VITE_SUPABASE_URL': JSON.stringify(supabaseUrl),
      'import.meta.env.VITE_SUPABASE_ANON_KEY': JSON.stringify(supabaseAnon),
    },
  }
})
