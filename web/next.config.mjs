import envPackage from '@next/env';
import { dirname, resolve } from 'path';
import { fileURLToPath } from 'url';

// Ensure the Next.js runtime loads environment variables declared in the repo root .env
const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, '..');
const isDevelopment = process.env.NODE_ENV !== 'production';

const { loadEnvConfig } = envPackage;
loadEnvConfig?.(repoRoot, isDevelopment);

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Enable standalone output for Docker
  // This creates a minimal production build with only necessary files
  output: 'standalone',
};

export default nextConfig;
